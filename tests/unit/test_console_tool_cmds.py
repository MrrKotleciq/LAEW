"""Tests for the ``tool`` console command (approval gates, arg parsing).

The P8 boundary itself (traversal denial, mutation gates) is covered by the
dedicated tool tests; here we verify the console wiring: k=v parsing, the
ask/auto/deny approval modes, and faithful surfacing of ToolResult.
"""

import pytest
from unittest.mock import patch

from laew.tools import ToolResult, ErrorCode
from laew.console.commands.tool import cmd_tool, _parse_kv_args
from laew.console.state import SessionState


@pytest.fixture
def state():
    """A bare session state (rarely needs a real manifest for these paths)."""
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def test_parse_kv_args():
    """key=value pairs parse to a dict; malformed items are rejected."""
    args, err = _parse_kv_args(["path=a.txt", "content=hello world"])
    assert err is None
    assert args == {"path": "a.txt", "content": "hello world"}

    args, err = _parse_kv_args(["lone-flag"])
    assert args == {}
    assert err and "expected key=value" in err


def test_tool_requires_name_and_operation(state, capsys):
    """Missing arguments produce a usage error, not a crash."""
    assert cmd_tool([], state) == 1
    assert "usage:" in capsys.readouterr().out
    assert cmd_tool(["filesystem"], state) == 1


def test_tool_unknown_name(state, capsys):
    """An unknown tool name lists the valid choices."""
    assert cmd_tool(["database", "query", "x=1"], state) == 1
    out = capsys.readouterr().out
    assert "unknown tool 'database'" in out
    assert "filesystem" in out and "web" in out  # choices shown


def _success_result(data="ok"):
    return ToolResult(success=True, data=data)


def _denied_result():
    return ToolResult(
        success=False,
        error_code=ErrorCode.ERR_UNAUTHORIZED,
        error_message="Operation requires approval",
    )


class StubTool:
    """Minimal tool stand-in the handler drives (name, approve, call)."""

    def __init__(self, result, name="filesystem"):
        self.name = name
        self._result = result
        self.approved = False
        self.calls = []

    def approve(self):
        self.approved = True

    def call(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        return self._result


def test_tool_auto_mode_approves_and_succeeds(state, capsys):
    """auto mode approves before the mutation and surfaces result data."""
    stub = StubTool(_success_result())
    with patch("laew.console.commands.tool.TOOL_FACTORIES", {"filesystem": lambda a: stub}):
        state.approval = "auto"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 0
    assert stub.approved is True
    assert stub.calls == [("write_file", {"path": "x.txt", "content": "hi"})]
    assert "ok" in capsys.readouterr().out


def test_tool_ask_mode_yes_approves(state, capsys):
    """ask mode with a 'y' answer approves and runs the mutation."""
    stub = StubTool(_success_result())
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories), \
         patch("builtins.input", return_value="y"):
        state.approval = "ask"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 0
    assert stub.approved is True


def test_tool_ask_mode_no_skips(state, capsys):
    """ask mode with a 'n' answer skips the call entirely (returns 1)."""
    stub = StubTool(_success_result())
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories), \
         patch("builtins.input", return_value="n"):
        state.approval = "ask"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 1
    assert stub.calls == []
    assert "not approved" in capsys.readouterr().out


def test_tool_deny_mode_leaves_gate_armed(state, capsys):
    """deny mode never approves; the tool's own gate rejects the mutation."""
    stub = StubTool(_denied_result())
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories):
        state.approval = "deny"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 1
    assert stub.approved is False
    assert len(stub.calls) == 1  # gate armed -> call still made, fails
    assert "ERR_UNAUTHORIZED" in capsys.readouterr().out


def test_tool_failure_surfaces_error_code(state, capsys):
    """A returned error sets the exit code and prints the code/message."""
    stub = StubTool(
        ToolResult(success=False, error_code="E_SOMETHING", error_message="boom"),
        name="git",
    )
    factories = {"git": lambda allowlist: stub}
    state.approval = "auto"
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories):
        code = cmd_tool(["git", "push", "remote=origin", "branch=main"], state)
    assert code == 1
    out = capsys.readouterr().out
    assert "E_SOMETHING" in out
    assert "boom" in out


def test_tool_nonstring_data_json_dumped(state, capsys):
    """Structured (non-str) result data is printed as indented JSON."""
    stub = StubTool(
        ToolResult(success=True, data={"files": ["a.md", "b.md"]}),
    )
    factories = {"filesystem": lambda allowlist: stub}
    state.approval = "auto"
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories):
        assert cmd_tool(["filesystem", "list_dir", "directory_path=@project"], state) == 0
    out = capsys.readouterr().out
    assert '"files"' in out and "a.md" in out