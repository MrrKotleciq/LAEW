"""Tests for the ``agent``/``chat``/``trace`` console commands.

The agent-loop behaviour itself is covered by tests/unit/test_agent.py; here we
verify the console wiring: argument handling, trace emission, and failure nets.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from laew.console.commands.agent import cmd_agent_run, cmd_agent_chat, cmd_trace
from laew.console.state import SessionState


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def _result(success=True, steps=None, final_response="done", error=None):
    return SimpleNamespace(
        success=success,
        steps=steps or [],
        total_steps=len(steps or []),
        final_response=final_response,
        error=error,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
    )


def _step(step_number=1, thought=None, tool_name=None, operation=None,
          tool_result=None, response=None):
    return SimpleNamespace(
        step_number=step_number, thought=thought, tool_name=tool_name,
        operation=operation, tool_result=tool_result, response=response,
    )


def test_agent_run_short_form_and_run_prefix(state, capsys):
    """Both `agent "<prompt>"` and `agent run "<prompt>"` execute."""
    for form in (["say hi"], ["run", "say hi"]):
        with patch(
            "laew.console.commands.agent._build_agent",
            return_value=(MagicMock(), "test-model"),
        ), patch(
            "laew.agent.executor.AgentExecutor.run",
            return_value=_result(final_response="hello back"),
        ):
            assert cmd_agent_run(form, state) == 0
        assert "hello back" in capsys.readouterr().out


def test_agent_run_missing_prompt(state, capsys):
    """No prompt yields a usage error rather than a run."""
    assert cmd_agent_run(["run"], state) == 1
    assert "usage:" in capsys.readouterr().out


def test_agent_run_failure_path(state, capsys):
    """A failed execution reports the error and returns 1."""
    with patch(
        "laew.console.commands.agent._build_agent",
        return_value=(MagicMock(), "test-model"),
    ), patch(
        "laew.agent.executor.AgentExecutor.run",
        return_value=_result(success=False, error="repetition guard hit"),
    ):
        assert cmd_agent_run(["run", "do it"], state) == 1
    out = capsys.readouterr().out
    assert "[FAIL]" in out and "repetition guard hit" in out


def test_agent_run_built_error_net(state, capsys):
    """A failure while building the agent nets into a readable error."""
    with patch(
        "laew.console.commands.agent._build_agent",
        side_effect=RuntimeError("no provider"),
    ):
        assert cmd_agent_run(["run", "do it"], state) == 1
    assert "could not build agent" in capsys.readouterr().out


def test_agent_run_emits_trace_lines_when_enabled(state, capsys):
    """With trace on, tool steps and thoughts are printed."""
    step = _step(
        step_number=1,
        thought="I should list the files",
        tool_name="filesystem",
        operation="list_dir",
        tool_result=SimpleNamespace(success=True),
    )
    step2 = _step(step_number=2, response="I found 3 files.")
    with patch(
        "laew.console.commands.agent._build_agent",
        return_value=(MagicMock(), "test-model"),
    ), patch(
        "laew.agent.executor.AgentExecutor.run",
        return_value=_result(steps=[step, step2], final_response="I found 3 files."),
    ):
        assert cmd_agent_run(["run", "list docs"], state) == 0
    out = capsys.readouterr().out
    assert "filesystem.list_dir" in out
    assert "found 3 files" in out


def test_agent_run_suppresses_trace_when_off(state, capsys):
    """With trace off, step output is omitted from the console."""
    state.trace = False
    step = _step(step_number=1, tool_name="filesystem", operation="list_dir")
    with patch(
        "laew.console.commands.agent._build_agent",
        return_value=(MagicMock(), "test-model"),
    ), patch(
        "laew.agent.executor.AgentExecutor.run",
        return_value=_result(steps=[step], final_response="3 files"),
    ):
        assert cmd_agent_run(["run", "list docs"], state) == 0
    out = capsys.readouterr().out
    assert "filesystem.list_dir" not in out
    assert "3 files" in out


def test_trace_toggle_valid(state, capsys):
    """trace on/off flips the session flag and prints confirmation."""
    assert cmd_trace(["off"], state) == 0
    assert state.trace is False
    assert "trace off" in capsys.readouterr().out
    assert cmd_trace(["on"], state) == 0
    assert state.trace is True


def test_trace_toggle_invalid(state, capsys):
    """trace with a bad value is rejected."""
    assert cmd_trace(["maybe"], state) == 1
    assert "usage: trace on|off" in capsys.readouterr().out


def test_agent_chat_loop_exits_after_reply(state, capsys):
    """chat runs one turn then exits on 'exit' input."""
    with patch(
        "laew.console.commands.agent._build_agent",
        return_value=(MagicMock(), "test-model"),
    ), patch(
        "laew.agent.executor.AgentExecutor.run",
        return_value=_result(final_response="agent reply"),
    ), patch("builtins.input", side_effect=["hello", "exit"]):
        assert cmd_agent_chat([], state) == 0
    out = capsys.readouterr().out
    assert "agent> agent reply" in out


def test_agent_chat_eof_terminates(state, capsys):
    """EOF on stdin ends the chat loop cleanly."""
    with patch(
        "laew.console.commands.agent._build_agent",
        return_value=(MagicMock(), "test-model"),
    ), patch(
        "laew.agent.executor.AgentExecutor.run",
        return_value=_result(),
    ), patch("builtins.input", side_effect=EOFError):
        assert cmd_agent_chat([], state) == 0