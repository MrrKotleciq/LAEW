"""Durable session storage for the LAEW console (Milestone 13).

Sessions are JSON files under the manifest's ``memory.session.storage``
directory (default ``runtime/sessions``).  A session file holds user-facing
state only — command history, session overrides and the agent conversation
memory — never a copy of the manifest, tool results, or other project state.
That separation is deliberate (ADR-012): the stored payload is *memory and
preferences*, while current project state is always re-verified from the
manifest and filesystem when a session is loaded.

Security properties maintained here:

- session names are validated against a strict pattern, so ``load``/``save``/
  ``delete`` can never traverse outside the session directory;
- files are written atomically (temp file + ``os.replace``) so a crash cannot
  leave a half-written session;
- the storage directory is created with owner-only permissions where the
  platform allows; JSON payloads are validated on read.
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Payload schema marker (shared by console and CLI chat session files).
PAYLOAD_SCHEMA = "laew.session.state"
#: Current on-disk payload format version.
PAYLOAD_VERSION = 1

#: Default session storage directory (manifest ``memory.session.storage``).
DEFAULT_SESSION_STORAGE = "runtime/sessions"

#: Allowed storage kinds written by the various surfaces.
PAYLOAD_KINDS = ("console", "chat")

#: Session file suffix.
SESSION_FILE_SUFFIX = ".json"

# Names must be a plain identifier: alphanumeric start, then letters, digits,
# ``.``, ``-`` and ``_``.  Anything else (``/``, ``\\``, ``..``, leading dot,
# whitespace, NUL) is rejected to keep session names filesystem-safe.
_VALID_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

#: Multi-turn conversation roles persisted in a session.
CONVERSATION_ROLES = ("user", "assistant")


class SessionStoreError(Exception):
    """Base error for session-storage failures."""


class InvalidSessionName(SessionStoreError):
    """Raised when a session name is empty, malformed, or a traversal attempt."""


def utc_now() -> str:
    """ISO-8601 UTC timestamp used for session lifecycle timestamps.

    Microsecond precision so that back-to-back saves produce distinct
    ``updated_at`` values, making the "always refreshed" guarantee provable.
    """
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_session_name(name: str) -> str:
    """
    Validate a session name for filesystem safety.

    Rejects empty names, path separators, traversal components (``.``/``..``),
    leading dots, and any character outside ``[A-Za-z0-9._-]`` after the first
    alphanumeric character.

    Returns:
        The validated name (unchanged).

    Raises:
        InvalidSessionName: Name is unsafe or malformed.
    """
    if not isinstance(name, str) or not name:
        raise InvalidSessionName("session name must be a non-empty string")
    if name in (".", ".."):
        raise InvalidSessionName(f"session name {name!r} is not allowed")
    if not _VALID_NAME.match(name):
        raise InvalidSessionName(
            f"invalid session name {name!r} (use letters, digits, '.', '-', '_')"
        )
    return name


def validate_conversation(conversation: list) -> list:
    """
    Validate a persisted conversation into a normalized ``[{role, content}]``
    list.

    Only ``user`` and ``assistant`` turns are persisted (tool observations live
    inside a single agent run and are deliberately not recalled as memory).

    Args:
        conversation: Raw ``conversation`` value from a session payload.

    Returns:
        A new list of validated message dicts (role/content only).

    Raises:
        SessionStoreError: The conversation is malformed.
    """
    if not isinstance(conversation, list):
        raise SessionStoreError("conversation must be a list")
    normalized = []
    for i, msg in enumerate(conversation):
        if not isinstance(msg, dict):
            raise SessionStoreError(f"conversation[{i}] must be an object")
        role = msg.get("role")
        content = msg.get("content")
        if role not in CONVERSATION_ROLES:
            raise SessionStoreError(
                f"conversation[{i}] has invalid role {role!r} (user|assistant)"
            )
        if not isinstance(content, str):
            raise SessionStoreError(f"conversation[{i}] content must be a string")
        normalized.append({"role": role, "content": content})
    return normalized


def validate_payload(doc: dict) -> dict:
    """
    Validate the cross-surface session payload envelope.

    Validates the schema marker, version, storage kind and conversation — the
    fields shared by console and CLI chat sessions.  Console-specific fields
    (overrides, approval, trace, history) are validated by
    :class:`SessionState`.

    Returns:
        The validated payload.

    Raises:
        SessionStoreError: The payload violates the session schema.
    """
    if not isinstance(doc, dict):
        raise SessionStoreError("session payload must be an object")
    if doc.get("schema") != PAYLOAD_SCHEMA:
        raise SessionStoreError(
            f"invalid session schema {doc.get('schema')!r} "
            f"(expected {PAYLOAD_SCHEMA!r})"
        )
    if doc.get("version") != PAYLOAD_VERSION:
        raise SessionStoreError(f"unsupported session version {doc.get('version')!r}")
    kind = doc.get("kind", "console")
    if kind not in PAYLOAD_KINDS:
        raise SessionStoreError(f"invalid session kind {kind!r}")
    manifest_path = doc.get("manifest_path")
    if not isinstance(manifest_path, str) or not manifest_path:
        raise SessionStoreError("session payload must carry a manifest_path")
    return {
        "schema": PAYLOAD_SCHEMA,
        "version": PAYLOAD_VERSION,
        "kind": kind,
        "manifest_path": manifest_path,
        "conversation": validate_conversation(doc.get("conversation", [])),
    }


def make_chat_payload(manifest_path: str, conversation: list) -> dict:
    """
    Build a CLI-chat session payload (no console state fields).

    Args:
        manifest_path: Manifest path the conversation belongs to.
        conversation: List of ``{role, content}`` turns.

    Returns:
        A validated chat payload dict.
    """
    return {
        "schema": PAYLOAD_SCHEMA,
        "version": PAYLOAD_VERSION,
        "kind": "chat",
        "manifest_path": manifest_path,
        "conversation": validate_conversation(conversation),
    }


@dataclass(frozen=True)
class SessionRecord:
    """Metadata about one saved session (no conversation content)."""

    name: str
    kind: str
    created_at: str
    updated_at: str
    manifest_path: str
    history_count: int
    conversation_count: int
    size_bytes: int


class SessionStore:
    """
    On-disk, per-name session persistence.

    Each session is one JSON file (``<name>.json``) inside ``directory``.
    Created implicitly by :meth:`save`.  Listing reads only metadata, never
    conversation content, so ``session list`` stays cheap at any history size.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    # ------------------------------------------------------------------ #
    # Naming & paths
    # ------------------------------------------------------------------ #
    def path_for(self, name: str) -> Path:
        """Path for a validated session name (never escapes ``directory``)."""
        return self.directory / f"{validate_session_name(name)}{SESSION_FILE_SUFFIX}"

    def exists(self, name: str) -> bool:
        """Whether a session with this name is stored."""
        return _safe_isfile(self.path_for(name))

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def save(self, name: str, payload: dict) -> SessionRecord:
        """
        Atomically save a session payload under *name*.

        ``created_at`` is preserved from an existing file (or set to now for a
        new session); ``updated_at`` is always refreshed.  The write goes to a
        temp file in the same directory and is moved into place with
        ``os.replace``, so a reader can never observe a partially-written
        session.

        Returns:
            The :class:`SessionRecord` describing the saved session.

        Raises:
            InvalidSessionName: Bad session name.
            SessionStoreError: Payload fails :func:`validate_payload`.
        """
        validate_session_name(name)
        validate_payload(payload)
        self.directory.mkdir(parents=True, exist_ok=True)
        _harden_dir(self.directory)

        path = self.path_for(name)
        existing = self._read_raw(path)
        if existing is None:
            created_at = utc_now()
        else:
            created_at = existing.get("created_at", utc_now())
        updated_at = utc_now()

        document = dict(payload)
        document["created_at"] = created_at
        document["updated_at"] = updated_at

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(self.directory),
            prefix=f".{validate_session_name(name)}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(document, tmp, indent=2, ensure_ascii=False)
            tmp.write("\n")
            tmp_path = Path(tmp.name)
        try:
            _harden_file(tmp_path)
            os.replace(tmp_path, path)
        finally:
            tmp_path.unlink(missing_ok=True)

        return self._record_for(path, document)

    def load(self, name: str) -> dict:
        """
        Load and validate a saved session payload.

        Returns:
            The validated payload dict (with lifecycle timestamps).

        Raises:
            InvalidSessionName: Bad session name.
            FileNotFoundError: No session with this name.
            SessionStoreError: File exists but the payload is corrupt/invalid.
        """
        path = self.path_for(name)
        if not _safe_isfile(path):
            raise FileNotFoundError(f"no saved session named {name!r}")
        raw = self._read_raw(path)
        if raw is None:
            raise SessionStoreError(f"session {name!r} could not be read")
        try:
            validate_payload(raw)
        except SessionStoreError as e:
            raise SessionStoreError(f"corrupt session {name!r}: {e}") from e
        # Return the full stored payload — validate_payload only checks the
        # shared envelope and strips optional fields (overrides, approval, …).
        result = dict(raw)
        result["created_at"] = raw.get("created_at", "")
        result["updated_at"] = raw.get("updated_at", "")
        return result

    def list_sessions(self) -> List[SessionRecord]:
        """
        List saved sessions, newest first.

        Returns:
            Metadata records; corrupt files are skipped rather than aborting
            the listing.
        """
        if not self.directory.is_dir():
            return []
        records = []
        # Newest first. Equal mtimes (rapid saves within filesystem clock
        # resolution) would otherwise leave order to glob iteration, which is
        # nondeterministic; the name tiebreaker keeps ties stable.
        for path in sorted(
            self.directory.glob(f"*{SESSION_FILE_SUFFIX}"),
            key=lambda p: (_safe_mtime(p), p.name),
            reverse=True,
        ):
            if not _safe_isfile(path):
                continue
            raw = self._read_raw(path)
            if raw is None:
                continue
            try:
                validate_payload(raw)
            except SessionStoreError:
                continue  # skip corrupt entry, keep the listing useful
            # Merge back fields stripped by validate_payload so _record_for
            # can compute correct history_count and timestamps.
            doc = dict(raw)
            doc["created_at"] = raw.get("created_at", "")
            doc["updated_at"] = raw.get("updated_at", "")
            records.append(self._record_for(path, doc))
        return records

    def delete(self, name: str) -> bool:
        """
        Delete a saved session.

        Returns:
            True if a file was removed, False if no such session existed.
        """
        path = self.path_for(name)
        if not _safe_isfile(path):
            return False
        try:
            path.unlink()
        except OSError as e:
            raise SessionStoreError(f"could not delete session {name!r}: {e}") from e
        return True

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    @staticmethod
    def _read_raw(path: Path) -> Optional[dict]:
        """Read a session file into a dict, or None if unreadable/corrupt."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _record_for(path: Path, doc: dict) -> SessionRecord:
        conversation = doc.get("conversation", [])
        history = doc.get("history", [])
        return SessionRecord(
            name=path.stem,
            kind=doc.get("kind", "console"),
            created_at=doc.get("created_at", ""),
            updated_at=doc.get("updated_at", ""),
            manifest_path=str(doc.get("manifest_path", "")),
            history_count=history if isinstance(history, int) else len(history),
            conversation_count=len(conversation),
            size_bytes=_safe_size(path),
        )


def session_store_from_manifest(manifest: dict) -> SessionStore:
    """
    Build a :class:`SessionStore` for the session storage the manifest declares.

    Arguments:
        manifest: Loaded system manifest.

    Returns:
        A store rooted at ``memory.session.storage`` (default
        ``runtime/sessions``), interpreted relative to the current directory.
    """
    storage = (
        manifest.get("memory", {})
        .get("session", {})
        .get("storage", DEFAULT_SESSION_STORAGE)
    )
    if not isinstance(storage, str) or not storage:
        storage = DEFAULT_SESSION_STORAGE
    return SessionStore(storage)


def _safe_isfile(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _harden_file(path: Path) -> None:
    """Best-effort owner-only permissions (no-op where the platform refuses)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _harden_dir(path: Path) -> None:
    """Best-effort owner-only permissions on the session directory."""
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass