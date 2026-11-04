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
import uuid
from contextlib import contextmanager
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

_SENSITIVE_KEY = re.compile(r"(?:password|secret|token|api[_-]?key|authorization|credential|private[_-]?key|passphrase)", re.I)
_SENSITIVE_TEXT = re.compile(
    r"(?i)(\b(?:authorization|password|secret|token|api[_-]?key|credential|passphrase)\b[\"']?\s*[:=]\s*[\"']?)(?:bearer\s+)?[^\s,;\"']+"
    r"|\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,})\b"
)


def _redact_conversation_value(value):
    """Remove recognizable credentials recursively before persistence."""
    if isinstance(value, str):
        return _SENSITIVE_TEXT.sub(lambda match: (match.group(1) or "") + "[REDACTED]", value)
    if isinstance(value, list):
        return [_redact_conversation_value(item) for item in value]
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == "provider_data":
                result[key] = _safe_provider_data(item)
            else:
                result[key] = "[REDACTED]" if _SENSITIVE_KEY.search(str(key)) else _redact_conversation_value(item)
        return result
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise SessionStoreError("conversation event contains unsupported data")


def _valid_turn_diagnostics(value):
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        return False
    if any(not isinstance(value.get(key), list) or any(not isinstance(item, dict) for item in value[key])
           for key in ("requests", "tools")):
        return False
    for tool in value["tools"]:
        recall = tool.get("memory_recall")
        if recall is not None and (not isinstance(recall, dict)
                                   or not isinstance(recall.get("scopes", []), list)
                                   or not isinstance(recall.get("ids", []), list)):
            return False
    routing = value.get("routing")
    if routing is None:
        return True
    if not isinstance(routing, dict) or not isinstance(routing.get("scopes"), list):
        return False
    hints = routing.get("hints", [])
    if not isinstance(hints, list) or any(
        not isinstance(hint, dict) or hint.get("kind") not in ("missing", "weak", "incomplete", "uncertain", "unavailable")
        or not isinstance(hint.get("scopes"), list) or any(scope not in ("global", "project") for scope in hint["scopes"])
        or type(hint.get("after_order")) is not int or hint["after_order"] < 0
        or type(hint.get("supplied")) is not bool
        for hint in hints
    ):
        return False
    recall = routing.get("memory_recall")
    if recall is not None and (not isinstance(recall, dict) or not isinstance(recall.get("scopes"), list)
                               or not isinstance(recall.get("ids", []), list)):
        return False
    for key in ("prefetch", "follow_up"):
        if not isinstance(routing.get(key), list):
            return False
        for item in routing[key]:
            if not isinstance(item, dict):
                return False
            fragments = item.get("fragments", [])
            if not isinstance(fragments, list) or any(not isinstance(fragment, dict) for fragment in fragments):
                return False
    return True


def _safe_provider_data(value):
    """Retain only Gemini continuation signatures, never raw transport payloads."""
    if not isinstance(value, dict) or not isinstance(value.get("scope"), str):
        return {}
    scope = value["scope"]
    if not re.fullmatch(r"gemini:[0-9a-f]{64}:[A-Za-z0-9._/-]{1,200}", scope):
        return {}
    message = value.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return {}
    safe_message = {"role": "assistant", "content": _redact_conversation_value(message.get("content") or "")}
    calls = []
    for call in message.get("tool_calls", []):
        if not isinstance(call, dict) or not isinstance(call.get("function"), dict):
            return {}
        function = call["function"]
        if not all(isinstance(value, str) for value in (call.get("id"), function.get("name"), function.get("arguments"))):
            return {}
        safe_call = {"id": call["id"], "type": "function", "function": {
            "name": function["name"], "arguments": _redact_conversation_value(function["arguments"])}}
        extra = call.get("extra_content")
        google = extra.get("google", {}) if isinstance(extra, dict) else {}
        signature = google.get("thought_signature") if isinstance(google, dict) else None
        if isinstance(signature, str) and len(signature) <= 65536:
            safe_call["extra_content"] = {"google": {"thought_signature": signature}}
        calls.append(safe_call)
    if calls:
        safe_message["tool_calls"] = calls
    return {"scope": scope, "message": safe_message}


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

    # Versioned conversation records share this store's directory but never
    # overwrite legacy named sessions. The legacy reader remains unchanged.
    @staticmethod
    def _conversation_id(value):
        try:
            parsed = uuid.UUID(value)
        except (TypeError, ValueError, AttributeError):
            raise SessionStoreError("invalid conversation ID") from None
        if str(parsed) != value:
            raise SessionStoreError("invalid conversation ID")
        return value

    def _conversation_path(self, conversation_id):
        return self.directory / f"conversation-{self._conversation_id(conversation_id)}.json"

    @contextmanager
    def _conversation_lock(self, conversation_id):
        from laew.rag.process_lock import CollectionLock
        self._conversation_id(conversation_id)
        lock = CollectionLock("conversation:" + conversation_id)
        lock.path = self.directory / ".locks" / f"{conversation_id}.write.lock"
        lock.acquire()
        try:
            yield
        finally:
            lock.release()

    @contextmanager
    def conversation_run(self, conversation_id):
        """Hold a process-wide exclusive lease while a run is executing."""
        from laew.rag.process_lock import CollectionLock
        self._conversation_id(conversation_id)
        lock = CollectionLock("conversation-run:" + conversation_id, timeout=0)
        lock.path = self.directory / ".locks" / f"{conversation_id}.run.lock"
        try:
            lock.acquire()
        except TimeoutError:
            raise SessionStoreError("conversation is busy") from None
        try:
            yield
        finally:
            lock.release()

    def _write_conversation(self, document):
        self.directory.mkdir(parents=True, exist_ok=True)
        _harden_dir(self.directory)
        path = self._conversation_path(document["id"])
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.directory,
                                             prefix=".conversation-", suffix=".tmp", delete=False) as tmp:
                tmp_path = Path(tmp.name)
                json.dump(document, tmp, ensure_ascii=False, indent=2)
                tmp.write("\n")
                tmp.flush()
                os.fsync(tmp.fileno())
            _harden_file(tmp_path)
            os.replace(tmp_path, path)
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_conversation_record(doc, expected_id):
        if (not isinstance(doc, dict) or doc.get("schema") != "laew.conversation"
                or doc.get("version") != 1 or doc.get("id") != expected_id):
            raise SessionStoreError("invalid conversation record")
        scope, project = doc.get("scope_type"), doc.get("project_id")
        if not ((scope == "general" and project is None) or
                (scope == "project" and isinstance(project, str) and bool(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project)))):
            raise SessionStoreError("invalid conversation scope")
        if (not isinstance(doc.get("title"), str) or not doc["title"].strip() or len(doc["title"]) > 200
                or not isinstance(doc.get("events"), list) or doc.get("status") != "active"
                or not isinstance(doc.get("created_at"), str) or not isinstance(doc.get("updated_at"), str)):
            raise SessionStoreError("invalid conversation content")
        seen = set()
        for index, event in enumerate(doc["events"]):
            if (not isinstance(event, dict) or type(event.get("sequence")) is not int or event.get("sequence") != index
                    or not isinstance(event.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", event["id"])
                    or event["id"] in seen or event.get("kind") not in {"user", "assistant", "tool_call", "tool_result", "run"}
                    or event.get("status") not in {"pending", "running", "completed", "failed", "cancelled", "denied"}
                    or not isinstance(event.get("content"), str) or not isinstance(event.get("created_at"), str)):
                raise SessionStoreError("invalid conversation event sequence")
            seen.add(event["id"])
        return doc

    def create_conversation(self, scope_type, project_id, title="New conversation"):
        conversation_id = str(uuid.uuid4())
        now = utc_now()
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise SessionStoreError("invalid conversation title")
        document = {"schema": "laew.conversation", "version": 1, "id": conversation_id,
                    "title": _redact_conversation_value(title.strip()), "scope_type": scope_type, "project_id": project_id,
                    "created_at": now, "updated_at": now, "status": "active", "events": []}
        self._validate_conversation_record(document, conversation_id)
        with self._conversation_lock(conversation_id):
            if self._conversation_path(conversation_id).exists():
                raise SessionStoreError("conversation ID already exists")
            self._write_conversation(document)
        return document

    def load_conversation(self, conversation_id):
        path = self._conversation_path(conversation_id)
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise SessionStoreError("conversation path cannot be a link")
        if not path.is_file():
            raise FileNotFoundError(f"conversation {conversation_id!r} not found")
        doc = self._read_raw(path)
        return self._validate_conversation_record(doc, conversation_id)

    def list_conversations(self):
        records = []
        for path in self.directory.glob("conversation-*.json"):
            try:
                doc = self.load_conversation(path.stem.removeprefix("conversation-"))
                records.append({key: value for key, value in doc.items() if key != "events"})
            except (OSError, SessionStoreError):
                continue
        return sorted(records, key=lambda item: item["updated_at"], reverse=True)

    def conversation_messages(self, conversation_id):
        """Rehydrate events and pair interrupted calls without executing them."""
        from laew.llm.base import LLMMessage, MessageRole
        document = self.load_conversation(conversation_id)
        messages = []
        pending = {}
        def finish_pending():
            for call_id, native in pending.items():
                text = "Execution was interrupted; the tool outcome is unknown. Do not repeat it automatically."
                messages.append(LLMMessage(MessageRole.TOOL if native else MessageRole.USER,
                                           text, tool_call_id=call_id if native else None))
            pending.clear()
        for event in document["events"]:
            kind = event.get("kind")
            if kind == "run":
                finish_pending()
            elif kind == "tool_call":
                call_id = event.get("call_id")
                if call_id and call_id not in pending:
                    pending[call_id] = False
            elif kind in {"user", "assistant", "tool_result"} and isinstance(event.get("message"), dict):
                try:
                    message = LLMMessage.from_dict(event["message"])
                except (ValueError, KeyError, TypeError):
                    raise SessionStoreError("invalid stored provider-neutral message") from None
                if kind in {"user", "assistant"}:
                    finish_pending()
                messages.append(message)
                if kind == "assistant":
                    pending.update({call.id: True for call in message.tool_calls})
                elif kind == "tool_result":
                    pending.pop(event.get("call_id"), None)
        finish_pending()
        return messages

    def recover_interrupted_runs(self, conversation_id):
        """Mark abandoned runs after their exclusive lease has been acquired."""
        document = self.load_conversation(conversation_id)
        running = {}
        for event in document["events"]:
            if event.get("kind") != "run" or not event.get("run_id"):
                continue
            if event["status"] in {"pending", "running"}:
                running[event["run_id"]] = event
            else:
                running.pop(event["run_id"], None)
        for run_id, event in running.items():
            self.append_conversation_event(conversation_id, {
                "id": uuid.uuid4().hex, "kind": "run", "status": "failed", "run_id": run_id,
                **({"diagnostics": event["diagnostics"]} if _valid_turn_diagnostics(event.get("diagnostics")) else {}),
                **({"user_event_id": event["user_event_id"]} if "user_event_id" in event else {}),
                "content": "Run interrupted; unfinished tool outcomes may be unknown."})

    def checkpoint_turn(self, conversation_id, run_id, diagnostics):
        if not _valid_turn_diagnostics(diagnostics):
            raise SessionStoreError("invalid turn diagnostics")
        with self._conversation_lock(conversation_id):
            document = self.load_conversation(conversation_id)
            for event in reversed(document["events"]):
                if event["kind"] == "run" and event.get("run_id") == run_id:
                    if event["status"] != "running":
                        break
                    event["diagnostics"] = _redact_conversation_value(diagnostics)
                    self._write_conversation(document)
                    return
            raise SessionStoreError("diagnostic checkpoint requires a running turn")

    def append_conversation_event(self, conversation_id, event):
        if (not isinstance(event, dict) or not isinstance(event.get("id"), str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", event["id"])
                or event.get("kind") not in {"user", "assistant", "tool_call", "tool_result", "run"}
                or event.get("status") not in {"pending", "running", "completed", "failed", "cancelled", "denied"}
                or not isinstance(event.get("content"), str) or "sequence" in event):
            raise SessionStoreError("invalid conversation event")
        if "diagnostics" in event and (event["kind"] != "run" or not _valid_turn_diagnostics(event["diagnostics"])):
            raise SessionStoreError("invalid turn diagnostics")
        event = _redact_conversation_value(event)
        with self._conversation_lock(conversation_id):
            document = self.load_conversation(conversation_id)
            for existing in document["events"]:
                if existing["id"] == event["id"]:
                    if {k: v for k, v in existing.items() if k not in {"sequence", "created_at"}} != {k: v for k, v in event.items() if k != "created_at"}:
                        raise SessionStoreError("event ID already has different content")
                    return existing
            stored = {**event, "created_at": event.get("created_at", utc_now()), "sequence": len(document["events"])}
            document["events"].append(stored)
            document["updated_at"] = utc_now()
            self._write_conversation(document)
            return stored

    def rename_conversation(self, conversation_id, title):
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise SessionStoreError("invalid conversation title")
        with self.conversation_run(conversation_id), self._conversation_lock(conversation_id):
            document = self.load_conversation(conversation_id)
            document["title"] = _redact_conversation_value(title.strip())
            document["updated_at"] = utc_now()
            self._write_conversation(document)
            return document

    def delete_conversation(self, conversation_id):
        with self.conversation_run(conversation_id), self._conversation_lock(conversation_id):
            path = self._conversation_path(conversation_id)
            if not path.is_file():
                return False
            path.unlink()
            return True

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
        if re.fullmatch(r"conversation-[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", name):
            raise InvalidSessionName("session name is reserved for conversation records")
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


def conversation_store_from_manifest(manifest: dict, manifest_path: str | Path) -> SessionStore:
    """Resolve the same session directory for every application surface."""
    from laew.rag.config import manifest_base_dir
    existing = session_store_from_manifest(manifest)
    directory = existing.directory.expanduser()
    if not directory.is_absolute():
        directory = manifest_base_dir(manifest_path) / directory
    return SessionStore(directory.resolve())


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
