"""Tests for the console REPL session (dispatch, history, exit).

These exercise the cmd.Cmd layer directly — parsing, unknown-command handling,
history replay, and the run_console boot path.  They never touch a live model.
"""

from unittest.mock import patch

import pytest

from laew.console.session import ConsoleSession, run_console
from laew.console.commands import COMMAND_HANDLERS


@pytest.fixture
def session():
    """A console session using the shipped manifest path."""
    return ConsoleSession(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def test_command_handler_registry_flat():
    """The registry exposes every command as a plain name -> handler map."""
    assert set(COMMAND_HANDLERS) == {
        "check", "info", "set", "provider", "prompt", "budget", "tools",
        "tool", "agent", "chat", "trace",
        "rag",
        "workflow", "multiagent", "eval",
    }


def test_default_dispatch_records_and_calls_handler(session, capsys):
    """A registered command line reaches its handler and is recorded."""
    assert session.default("check") is None
    out = capsys.readouterr().out
    assert "[OK] Manifest loaded" in out
    assert session.state.history == ["check"]


def test_default_unknown_command(session, capsys):
    """An unregistered command prints a readable message, not a crash."""
    assert session.default("frobnicate --all") is None
    out = capsys.readouterr().out
    assert "Unknown command: frobnicate" in out
    assert session.state.history == ["frobnicate --all"]


def test_default_unparseable_line(session, capsys):
    """A line that shlex cannot parse fails gracefully."""
    assert session.default('check "unterminated') is None
    out = capsys.readouterr().out
    assert "[FAIL] Could not parse command" in out


def test_default_handler_exception_is_a_net(session, capsys):
    """Exceptions inside handlers surface as [FAIL] instead of crashing."""
    with patch(
        "laew.console.session.COMMAND_HANDLERS",
        {"boom": lambda args, state: (_ for _ in ()).throw(RuntimeError("kaboom"))},
    ):
        session.default("boom")
    out = capsys.readouterr().out
    assert "[FAIL] kaboom" in out


def test_exit_quit_return_true(session):
    """exit/quit end the REPL loop (cmdloop returns when a command is True)."""
    assert session.onecmd("exit") is True
    assert session.onecmd("quit") is True


def test_history_single_and_empty(session, capsys):
    """history prints numbered entries; empty history reports emptiness."""
    session.do_history("")
    assert "(history is empty)" in capsys.readouterr().out

    session.state.history.extend(["check", "info"])
    session.do_history("")
    out = capsys.readouterr().out
    assert "1  check" in out
    assert "2  info" in out


def test_rerepeat_bad_index(session, capsys):
    """!N with a non-numeric or out-of-range index fails gracefully."""
    session.do_rerepeat("x")
    assert "[FAIL] usage" in capsys.readouterr().out
    session.do_rerepeat("99")
    assert "out of range" in capsys.readouterr().out


def test_bang_repeat_replays_command(session, capsys):
    """!N via the !-prefix path re-runs history entry N through dispatch."""
    session.default("set timeout 42")
    capsys.readouterr()
    session.default("!1")
    out = capsys.readouterr().out
    assert "timeout = 42" in out


def test_bang_prefix_invalid(session, capsys):
    """A lone ! without a valid index fails gracefully."""
    session.default("!")
    out = capsys.readouterr().out
    assert "[FAIL] usage" in out


def test_empty_line_is_ignored(session):
    """An empty line does not repeat the previous command (cmd.Cmd default)."""
    session.default("check")
    assert session.emptyline() is None  # must not re-dispatch


def test_run_console_boots_and_exits(capsys):
    """run_console returns 0 when the session exits normally via queued input."""
    with patch("builtins.input", return_value="exit"):
        assert run_console(manifest_path="manifests/SYSTEM_MANIFEST.yaml") == 0


def test_run_console_interruption_returns_1(capsys):
    """Ctrl+C inside the loop yields a clean exit code 1."""
    with patch("builtins.input", side_effect=KeyboardInterrupt):
        assert run_console(manifest_path="manifests/SYSTEM_MANIFEST.yaml") == 1