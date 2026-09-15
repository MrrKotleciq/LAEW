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


def test_tool_help_is_intercepted(state, capsys):
    """`tool help` prints the operation table and never reaches a tool call."""
    stub = StubTool(_success_result())
    with patch("laew.console.commands.tool.TOOL_FACTORIES", {"filesystem": lambda a: stub}):
        assert cmd_tool(["help"], state) == 0
        assert cmd_tool(["-h"], state) == 0
    out = capsys.readouterr().out
    assert "Available tools and their operations" in out
    assert "list_dir" in out  # a real declared operation is listed
    assert stub.calls == []  # nothing was dispatched as an operation


def test_tool_name_help_is_intercepted(state, capsys):
    """`tool filesystem help` prints that tool's operations, no call."""
    stub = StubTool(_success_result())
    with patch("laew.console.commands.tool.TOOL_FACTORIES", {"filesystem": lambda a: stub}):
        assert cmd_tool(["filesystem", "help"], state) == 0
    out = capsys.readouterr().out
    assert "Available tools and their operations" in out
    assert stub.calls == []


def test_tool_failure_prints_bare_error_code_not_enum_repr(state, capsys):
    """An ErrorCode member renders as 'ERR_...' without the enum repr prefix."""
    stub = StubTool(
        ToolResult(
            success=False,
            error_code=ErrorCode.ERR_INVALID_INPUT,
            error_message="Unknown operation: ls",
        ),
    )
    factories = {"filesystem": lambda allowlist: stub}
    state.approval = "auto"
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories):
        assert cmd_tool(["filesystem", "ls"], state) == 1
    out = capsys.readouterr().out
    assert "[FAIL] ERR_INVALID_INPUT" in out
    assert "ErrorCode.ERR_INVALID_INPUT" not in out  # Python 3.11 str(Enum) leak


def test_tool_unknown_operation_lists_available_ops(state, capsys):
    """A failed operation with an 'operation' message suggests real ops."""
    stub = StubTool(
        ToolResult(
            success=False,
            error_code=ErrorCode.ERR_INVALID_INPUT,
            error_message="Unknown operation: ls",
        ),
    )
    factories = {"filesystem": lambda allowlist: stub}
    state.approval = "auto"
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories):
        assert cmd_tool(["filesystem", "ls"], state) == 1
    out = capsys.readouterr().out
    assert "available filesystem operations:" in out
    assert "run_command" in out  # points at the terminal path for shell commands
    assert "tool terminal run_command command=..." in out


def _success_result(data="ok"):
    return ToolResult(success=True, data=data)


def _denied_result():
    return ToolResult(
        success=False,
        error_code=ErrorCode.ERR_UNAUTHORIZED,
        error_message="Operation requires approval",
    )


class StubTool:
    """Minimal tool stand-in the handler drives (name, approve, call).

    Accepts a single fixed result, or a queue of results consumed one per
    ``call`` — ask mode runs the mutation ungated first (normally denied),
    then again after approval, so a two-element queue mirrors the real flow.
    """

    def __init__(self, result, name="filesystem", results=None):
        self.name = name
        self._result = result
        self._results = list(results) if results is not None else None
        self.approved = False
        self.calls = []
        # Tool.operations is used by the tool command to list operations.
        # For the tests we provide a minimal dict; the real tools have more.
        self.operations = {
            "list_dir": {"params": ["directory_path"], "description": "List directory", "read_only": True},
            "write_file": {"params": ["path", "content"], "description": "Write file", "read_only": False},
        }

    def approve(self):
        self.approved = True

    def call(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        if self._results is not None:
            return self._results.pop(0)
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


def test_tool_ask_mode_no_prompt_for_read(state, capsys):
    """ask mode never prompts for read operations that pass ungated."""
    stub = StubTool(_success_result())
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories), \
         patch("builtins.input", side_effect=AssertionError("input must not be called")) as inp:
        state.approval = "ask"
        code = cmd_tool(["filesystem", "list_dir", "directory_path=@project"], state)
    assert code == 0
    inp.assert_not_called()
    assert stub.approved is False  # not needed for reads
    assert stub.calls == [("list_dir", {"directory_path": "@project"})]


def test_tool_ask_mode_yes_approves_after_denial(state, capsys):
    """ask mode: mutation denied ungated, 'y' approves and re-runs it."""
    stub = StubTool(_denied_result(), results=[_denied_result(), _success_result()])
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories), \
         patch("builtins.input", return_value="y"):
        state.approval = "ask"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 0
    assert stub.approved is True
    assert stub.calls == [
        ("write_file", {"path": "x.txt", "content": "hi"}),
        ("write_file", {"path": "x.txt", "content": "hi"}),
    ]


def test_tool_ask_mode_no_refuses_denied_mutation(state, capsys):
    """ask mode: 'n' on a denied mutation returns 1 and does not re-run."""
    stub = StubTool(_denied_result())
    factories = {"filesystem": lambda allowlist: stub}
    with patch("laew.console.commands.tool.TOOL_FACTORIES", factories), \
         patch("builtins.input", return_value="n"):
        state.approval = "ask"
        code = cmd_tool(["filesystem", "write_file", "path=x.txt", "content=hi"], state)
    assert code == 1
    assert stub.approved is False
    assert len(stub.calls) == 1  # ungated call only; no re-run after refusal
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