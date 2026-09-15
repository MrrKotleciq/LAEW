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