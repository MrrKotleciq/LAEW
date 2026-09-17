"""Session state for the LAEW testing console.

Holds the manifest reference, per-session overrides (provider, model, base-url,
timeout), the approval gate mode, and command history. Handlers receive a
:class:`SessionState` and resolve configuration live so that :code:`set`
changes take effect on the next command (session > env > manifest > default).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from laew.manifest import load_manifest, ManifestError
from laew.console.session_store import (
    PAYLOAD_SCHEMA,
    PAYLOAD_VERSION,
    SessionStoreError,
    validate_conversation,
)

DEFAULT_MANIFEST = "manifests/SYSTEM_MANIFEST.yaml"

APPROVAL_CHOICES = ("ask", "auto", "deny")

# Session override keys accepted by the ``set`` command.
OVERRIDE_KEYS = ("provider", "model", "base-url", "timeout", "approval", "trace")


class StateError(Exception):
    """Raised for invalid console state transitions (e.g. bad ``set`` value)."""


@dataclass
class SessionState:
    """
    Runtime configuration for one console session.

    Attributes:
        manifest_path: Path of the system manifest in use
        overrides: Per-session values that beat the manifest (provider config)
        approval: Approval-gate mode (ask | auto | deny)
        trace: Whether agent step traces are printed
        history: In-session command log for ``history`` / ``!N``
        exit_requested: Set by ``exit``/``quit`` to stop the REPL
    """

    manifest_path: str = DEFAULT_MANIFEST
    overrides: Dict[str, str] = field(default_factory=dict)
    approval: str = "ask"
    trace: bool = True
    history: List[str] = field(default_factory=list)
    exit_requested: bool = False
    # Agent conversation memory as ``{role, content}`` turns (user/assistant).
    # Persisted so a session can be resumed across restarts (Milestone 13).
    conversation: List[Dict[str, str]] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Manifest
    # ------------------------------------------------------------------ #
    def load_manifest(self) -> dict:
        """Load and validate the configured manifest.

        Returns:
            The manifest dictionary.

        Raises:
            StateError: Manifest file missing or invalid.
        """
        try:
            return load_manifest(Path(self.manifest_path))
        except (FileNotFoundError, ManifestError) as e:
            raise StateError(
                f"Could not load manifest '{self.manifest_path}': {e}"
            ) from e

    # ------------------------------------------------------------------ #
    # Configuration resolution (session > env > manifest > default)
    # ------------------------------------------------------------------ #
    def provider_cfg(self) -> dict:
        """Resolve the active provider configuration.

        The session ``provider`` override selects an entry from the manifest
        provider list by ``type``. When no override is set, the first manifest
        provider is used.

        Returns:
            A provider config dict (at minimum ``{"type": "ollama"}``).
        """
        manifest = self.load_manifest()
        providers_cfg = (
            manifest.get("agent", {}).get("llm", {}).get("providers", [])
        )
        if not providers_cfg:
            return {"type": "ollama"}

        provider_type = self.overrides.get("provider")
        if provider_type is None:
            return providers_cfg[0]
        for provider in providers_cfg:
            if provider.get("type") == provider_type:
                return provider
        return providers_cfg[0]

    def terminal_allowlist(self) -> Optional[list]:
        """Extract the manifest's terminal command allowlist (or None)."""
        categories = self.load_manifest().get("tools", {}).get("categories", {})
        allowlist = categories.get("terminal", {}).get("allowlist")
        return list(allowlist) if allowlist else None

    def manifest_model(self) -> Optional[str]:
        """Default model declared by the primary manifest provider, if any."""
        return self.provider_cfg().get("model")

    # ------------------------------------------------------------------ #
    # ``set`` command support
    # ------------------------------------------------------------------ #
    def set_override(self, key: str, value: str) -> None:
        """
        Apply a session override.

        Args:
            key: One of :data:`OVERRIDE_KEYS`.
            value: The value to set.

        Raises:
            StateError: Unknown key, invalid approval mode, or non-numeric
                timeout.
        """
        key = key.lower()
        if key not in OVERRIDE_KEYS:
            raise StateError(f"Unknown setting '{key}' (settable: {', '.join(OVERRIDE_KEYS)})")

        if key == "approval":
            value = value.lower()
            if value not in APPROVAL_CHOICES:
                raise StateError(
                    f"Invalid approval mode '{value}' (choose: {', '.join(APPROVAL_CHOICES)})"
                )
            self.approval = value
        elif key == "trace":
            value = value.lower()
            if value not in ("on", "off"):
                raise StateError("trace accepts 'on' or 'off'")
            self.trace = value == "on"
        elif key == "timeout":
            try:
                timeout = int(value)
            except ValueError as e:
                raise StateError(f"timeout must be an integer, got '{value}'") from e
            if timeout <= 0:
                raise StateError("timeout must be a positive integer")
            self.overrides[key] = value
        elif key == "manifest":
            self.manifest_path = value
        elif key == "base-url":
            self.overrides[key] = value
        else:  # provider, model
            self.overrides[key] = value

    # ------------------------------------------------------------------ #
    # Command history
    # ------------------------------------------------------------------ #
    def record(self, line: str) -> None:
        """Record a console command line for ``history`` / ``!N``."""
        if line.strip():
            self.history.append(line)

    def resolved_timeout(self) -> Optional[str]:
        """The session timeout override, if any."""
        return self.overrides.get("timeout")

    def resolved_model(self) -> Optional[str]:
        """The session model override, if any."""
        return self.overrides.get("model")

    def resolved_base_url(self) -> Optional[str]:
        """The session base-url override, if any."""
        return self.overrides.get("base-url")

    # ------------------------------------------------------------------ #
    # Persistence (Milestone 13) — durable, resumable sessions
    # ------------------------------------------------------------------ #
    def to_payload(self) -> dict:
        """
        Serialize the session's user-facing state for storage.

        Only memory and preferences are exported — manifest contents, tool
        results, and other current project state are never persisted, keeping
        the session file decoupled from ground-truth (ADR-012).  Lifecycle
        timestamps are stamped by :class:`SessionStore`, not here.

        Returns:
            A ``laew.session.state`` version-1 payload dict.
        """
        manifest_path = self.manifest_path
        if isinstance(self.manifest_path, Path):
            manifest_path = str(self.manifest_path)
        return {
            "schema": PAYLOAD_SCHEMA,
            "version": PAYLOAD_VERSION,
            "kind": "console",
            "manifest_path": manifest_path,
            "overrides": dict(self.overrides),
            "approval": self.approval,
            "trace": bool(self.trace),
            "history": list(self.history),
            "conversation": validate_conversation(self.conversation),
        }

    @classmethod
    def from_payload(cls, payload: dict) -> "SessionState":
        """
        Restore a :class:`SessionState` from a validated session payload.

        Does not touch the manifest — the caller re-verifies the restored
        manifest path against the authoritative manifest on load (ADR-012).

        Args:
            payload: A ``laew.session.state`` payload (as loaded by
                :class:`SessionStore`).

        Returns:
            A new :class:`SessionState` reflecting the saved state.

        Raises:
            StateError: The payload is malformed for console state.
        """
        try:
            envelope = validate_conversation(payload.get("conversation", []))
            history = payload.get("history", [])
            overrides = payload.get("overrides", {})
        except SessionStoreError as e:
            raise StateError(str(e)) from e

        if not isinstance(history, list) or not all(
            isinstance(entry, str) for entry in history
        ):
            raise StateError("session payload: history must be a list of strings")
        if not isinstance(overrides, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in overrides.items()
        ):
            raise StateError("session payload: overrides must be a string map")

        manifest_path = payload.get("manifest_path") or DEFAULT_MANIFEST
        approval = payload.get("approval", "ask")
        if approval not in APPROVAL_CHOICES:
            raise StateError(
                f"session payload: invalid approval mode {approval!r}"
                f" (choose: {', '.join(APPROVAL_CHOICES)})"
            )
        trace = payload.get("trace", True)
        if not isinstance(trace, bool):
            raise StateError("session payload: trace must be a boolean")

        return cls(
            manifest_path=manifest_path,
            overrides=overrides,
            approval=approval,
            trace=trace,
            history=history,
            conversation=envelope,
        )

    def restore(self, other: "SessionState") -> None:
        """
        Replace this session's per-session state with *other*'s, in place.

        Keeps the caller's object identity (handlers receive ``state`` by
        reference) while adopting the saved overrides, approval mode, trace
        flag, command history, and conversation memory from *other*.

        Args:
            other: The restored state (typically from :meth:`from_payload`).
        """
        self.manifest_path = other.manifest_path
        self.overrides = dict(other.overrides)
        self.approval = other.approval
        self.trace = other.trace
        self.history = list(other.history)
        self.conversation = [dict(m) for m in other.conversation]

    def conversation_to_messages(self) -> List["LLMMessage"]:
        """
        Convert the persisted conversation memory into provider messages.

        Returns:
            A list of user/assistant :class:`LLMMessage` to seed agent history,
            or an empty list when there is no saved conversation.
        """
        from laew.llm.base import LLMMessage, MessageRole

        return [
            LLMMessage(role=MessageRole(msg["role"]), content=msg["content"])
            for msg in validate_conversation(self.conversation)
        ]