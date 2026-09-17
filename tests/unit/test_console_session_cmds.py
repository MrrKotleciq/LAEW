"""Tests for the session command handlers (session save/load/list/show/delete).

Exercises the ``cmd_session`` dispatcher and its subcommand handlers via a
mocked session store rooted in a temporary directory, so no real manifest or
session directory is touched.
"""

import pytest
from unittest.mock import patch

from laew.console.commands.sessions import cmd_session
from laew.console.session_store import (
    PAYLOAD_SCHEMA,
    PAYLOAD_VERSION,
    SessionStore,
)
from laew.console.state import SessionState


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
def _make_console_payload(
    *,
    manifest_path="manifests/SYSTEM_MANIFEST.yaml",
    overrides=None,
    approval="ask",
    trace=True,
    history=None,
    conversation=None,
):
    """Build a minimal console payload envelope."""
    return {
        "schema": PAYLOAD_SCHEMA,
        "version": PAYLOAD_VERSION,
        "kind": "console",
        "manifest_path": manifest_path,
        "overrides": overrides or {},
        "approval": approval,
        "trace": trace,
        "history": history or [],
        "conversation": conversation or [],
    }


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #
@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


@pytest.fixture
def store(tmp_path):
    """A SessionStore rooted in a temporary directory."""
    return SessionStore(tmp_path / "sessions")


@pytest.fixture
def state_with_store(state, store):
    """Yield (state, store) with _resolve_store patched to use tmp store."""
    with patch(
        "laew.console.commands.sessions._resolve_store",
        return_value=store,
    ):
        yield state, store


# ------------------------------------------------------------------ #
# Dispatcher: cmd_session
# ------------------------------------------------------------------ #
class TestCmdSessionDispatcher:
    """The top-level dispatcher rejects bad input and routes subcommands."""

    def test_no_args_returns_usage_error(self, state, capsys):
        """Empty args prints usage and returns 1."""
        assert cmd_session([], state) == 1
        out = capsys.readouterr().out
        assert "usage:" in out

    def test_unknown_subcommand_returns_error(self, state, capsys):
        """Unknown subcommand prints an error and returns 1."""
        assert cmd_session(["bogus"], state) == 1
        out = capsys.readouterr().out
        assert "unknown session subcommand" in out


# ------------------------------------------------------------------ #
# session list
# ------------------------------------------------------------------ #
class TestSessionList:
    """session list shows saved sessions or reports none."""

    def test_list_empty(self, state_with_store, capsys):
        """An empty store prints '(no saved sessions)'."""
        state, store = state_with_store
        assert cmd_session(["list"], state) == 0
        assert "(no saved sessions)" in capsys.readouterr().out

    def test_list_shows_saved_session(self, state_with_store, capsys):
        """A saved session appears in the listing with metadata."""
        state, store = state_with_store
        store.save("research", _make_console_payload(history=["check", "info"]))
        assert cmd_session(["list"], state) == 0
        out = capsys.readouterr().out
        assert "1 saved session" in out
        assert "research" in out
        assert "console" in out
        assert "history=2" in out


# ------------------------------------------------------------------ #
# session save
# ------------------------------------------------------------------ #
class TestSessionSave:
    """session save <name> persists state to disk."""

    def test_save_no_name_returns_error(self, state_with_store, capsys):
        """session save without a name prints usage."""
        state, _store = state_with_store
        assert cmd_session(["save"], state) == 1
        assert "usage:" in capsys.readouterr().out

    def test_save_creates_session(self, state_with_store, store, capsys):
        """session save <name> creates a .json file and prints OK."""
        state, _store = state_with_store
        state.history = ["check", "info"]
        state.overrides["model"] = "llama3.1"
        state.conversation = [{"role": "user", "content": "hello"}]
        assert cmd_session(["save", "research"], state) == 0
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert "research" in out
        assert store.exists("research")

    def test_save_invalid_name_returns_error(self, state_with_store, capsys):
        """session save with an invalid name prints a failure."""
        state, _store = state_with_store
        assert cmd_session(["save", "../evil"], state) == 1
        assert "[FAIL]" in capsys.readouterr().out


# ------------------------------------------------------------------ #
# session load
# ------------------------------------------------------------------ #
class TestSessionLoad:
    """session load <name> restores a saved session."""

    def test_load_no_name_returns_error(self, state_with_store, capsys):
        """session load without a name prints usage."""
        state, _store = state_with_store
        assert cmd_session(["load"], state) == 1
        assert "usage:" in capsys.readouterr().out

    def test_load_missing_session_returns_error(self, state_with_store, capsys):
        """session load for a nonexistent name prints a failure."""
        state, _store = state_with_store
        assert cmd_session(["load", "nonexistent"], state) == 1
        assert "no saved session named 'nonexistent'" in capsys.readouterr().out

    def test_load_restores_state(self, state_with_store, store, capsys):
        """session load <name> restores history, overrides, approval, and conversation."""
        state, _store = state_with_store
        payload = _make_console_payload(
            overrides={"model": "llama3.1", "timeout": "300"},
            approval="auto",
            trace=False,
            history=["check", "set timeout 300"],
            conversation=[
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "hello"},
            ],
        )
        store.save("research", payload)
        assert cmd_session(["load", "research"], state) == 0
        out = capsys.readouterr().out
        assert "[OK]" in out
        assert state.overrides["model"] == "llama3.1"
        assert state.overrides["timeout"] == "300"
        assert state.approval == "auto"
        assert state.trace is False
        assert len(state.history) == 2
        assert len(state.conversation) == 2


# ------------------------------------------------------------------ #
# session show
# ------------------------------------------------------------------ #
class TestSessionShow:
    """session show <name> displays metadata without restoring."""

    def test_show_no_name_returns_error(self, state_with_store, capsys):
        """session show without a name prints usage."""
        state, _store = state_with_store
        assert cmd_session(["show"], state) == 1
        assert "usage:" in capsys.readouterr().out

    def test_show_missing_session_returns_error(self, state_with_store, capsys):
        """session show for a nonexistent name prints a failure."""
        state, _store = state_with_store
        assert cmd_session(["show", "nonexistent"], state) == 1
        assert "no saved session named 'nonexistent'" in capsys.readouterr().out

    def test_show_displays_metadata(self, state_with_store, store, capsys):
        """session show <name> prints kind, manifest, conversation count, etc."""
        state, _store = state_with_store
        payload = _make_console_payload(
            history=["check"],
            conversation=[{"role": "user", "content": "hello"}],
        )
        store.save("research", payload)
        assert cmd_session(["show", "research"], state) == 0
        out = capsys.readouterr().out
        assert "session: research" in out
        assert "kind: console" in out
        assert "history entries: 1" in out
        assert "conversation turns: 1" in out
        assert "approval: ask" in out

    def test_show_does_not_alter_state(self, state_with_store, store):
        """session show does not mutate the current session state."""
        state, _store = state_with_store
        store.save("research", _make_console_payload(history=["old"]))
        cmd_session(["show", "research"], state)
        # state should remain unchanged
        assert state.history == []
        assert state.overrides == {}


# ------------------------------------------------------------------ #
# session delete
# ------------------------------------------------------------------ #
class TestSessionDelete:
    """session delete <name> removes a saved session."""

    def test_delete_no_name_returns_error(self, state_with_store, capsys):
        """session delete without a name prints usage."""
        state, _store = state_with_store
        assert cmd_session(["delete"], state) == 1
        assert "usage:" in capsys.readouterr().out

    def test_delete_missing_session_returns_error(self, state_with_store, capsys):
        """session delete for a nonexistent name prints a failure."""
        state, _store = state_with_store
        assert cmd_session(["delete", "nonexistent"], state) == 1
        assert "no saved session named 'nonexistent'" in capsys.readouterr().out

    def test_delete_removes_session(self, state_with_store, store, capsys):
        """session delete <name> removes the file and prints OK."""
        state, _store = state_with_store
        store.save("research", _make_console_payload())
        assert cmd_session(["delete", "research"], state) == 0
        assert "[OK]" in capsys.readouterr().out
        assert not store.exists("research")


# ------------------------------------------------------------------ #
# ADR-012 compliance: load re-verifies manifest, not trusting stored path
# ------------------------------------------------------------------ #
class TestADR012ManifestReverification:
    """On load, the stored manifest path is re-verified — if unloadable,
    the current manifest is kept and a warning is printed."""

    def test_load_warns_on_bad_manifest_and_keeps_original(self, state_with_store, store, capsys):
        """Saved session with a non-loadable manifest keeps the current one."""
        state, _store = state_with_store
        state.manifest_path = "manifests/SYSTEM_MANIFEST.yaml"
        payload = _make_console_payload(
            manifest_path="/nonexistent/MANIFEST.yaml",
            overrides={"model": "test-model"},
        )
        store.save("research", payload)
        assert cmd_session(["load", "research"], state) == 0
        out = capsys.readouterr().out
        assert "not loadable" in out
        assert "keeping current" in out
        # The manifest_path should be the original, not the stored bad one
        assert state.manifest_path == "manifests/SYSTEM_MANIFEST.yaml"
        # But overrides should still be restored
        assert state.overrides["model"] == "test-model"
