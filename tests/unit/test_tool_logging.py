"""Tests for privacy-preserving tool invocation logging (ADR-016)."""

import io
import json
import logging

import pytest

import laew.tools.base as base
from laew.tools.base import ErrorCode, Tool, ToolLogger, ToolResult, configure_tool_logger
from laew.tools.filesystem import FilesystemTool


class DummyTool(Tool):
    def validate(self, operation, **kwargs):
        return (False, "validation SECRET_MESSAGE") if operation == "fail" else (True, None)

    def execute(self, operation, **kwargs):
        return ToolResult.ok({"response": "SECRET_RESPONSE"})


@pytest.fixture(autouse=True)
def restore_global_logger(monkeypatch):
    monkeypatch.setattr(base, "_tool_logger", base._tool_logger)


EMPTY_SHAPE = {"null": 0, "bool": 0, "number": 0, "string": 0,
               "mapping": 0, "array": 0, "other": 0}


@pytest.mark.parametrize("operation,success", [("success", True), ("fail", False)])
def test_real_logging_and_stream_exclude_content(caplog, operation, success):
    stream = io.StringIO()
    configure_tool_logger(output=stream)
    with caplog.at_level(logging.INFO, logger="laew.tools"):
        result = DummyTool().call(operation, plaintext="SECRET_PLAINTEXT", nested={"SECRET_KEY": ["SECRET_NESTED"]})

    assert result.success is success
    if success:
        assert result.data == {"response": "SECRET_RESPONSE"}
    else:
        assert result.error_message == "validation SECRET_MESSAGE"
        assert result.error_code == ErrorCode.ERR_INVALID_INPUT
    assert len(caplog.records) == 1
    assert stream.getvalue().strip() == caplog.records[0].getMessage()
    text = stream.getvalue()
    assert "SECRET" not in text
    entry = json.loads(text)
    assert set(entry) == {"timestamp", "tool", "operation", "arguments", "success", "error_code", "error_message", "duration_ms", "status"}
    assert entry["tool"] == "UNKNOWN"
    assert entry["operation"] == "UNKNOWN"
    assert entry["arguments"] == EMPTY_SHAPE | {"string": 1, "mapping": 1}
    assert entry["success"] is success
    assert entry["status"] == ("SUCCESS" if success else "FAILURE")
    assert entry["error_code"] == (None if success else "ERR_INVALID_INPUT")
    assert entry["error_message"] is None
    assert isinstance(entry["duration_ms"], int) and entry["duration_ms"] >= 0


def test_real_tool_preserves_allowed_labels():
    stream = io.StringIO()
    configure_tool_logger(output=stream)
    tool = FilesystemTool()
    result = tool.call("view_file", file_path="README.md")
    assert result.success
    entry = json.loads(stream.getvalue())
    assert entry["tool"] == "FilesystemTool"
    assert entry["operation"] == "view_file"
    assert entry["arguments"] == EMPTY_SHAPE | {"string": 1}
    assert "README.md" not in stream.getvalue()


@pytest.mark.parametrize("tool,operation,code", [
    ("SECRET_TOOL", "SECRET_OPERATION", "SECRET_CODE"),
    ("FilesystemTool", "SECRET_OPERATION", "SECRET_CODE"),
    ("FilesystemTool", "git_status", "SECRET_CODE"),
    (["SECRET_TOOL"], {"SECRET_OPERATION": 1}, {"SECRET_CODE": 1}),
])
def test_custom_and_malformed_labels_never_reach_either_sink(caplog, tool, operation, code):
    stream = io.StringIO()
    logger = ToolLogger(output=stream)
    with caplog.at_level(logging.INFO, logger="laew.tools"):
        logger.log_invocation(tool, operation, {"SECRET_KEY": {"nested": "SECRET_VALUE"}},
                              ToolResult.error(code, "SECRET_ERROR"), 1)
    assert len(caplog.records) == 1
    assert caplog.records[0].getMessage() == stream.getvalue().strip()
    assert "SECRET" not in stream.getvalue()
    entry = json.loads(stream.getvalue())
    assert entry["tool"] == ("FilesystemTool" if tool == "FilesystemTool" else "UNKNOWN")
    assert entry["operation"] == "UNKNOWN"
    assert entry["error_code"] is None
    assert entry["error_message"] is None
    assert entry["arguments"] == EMPTY_SHAPE | {"mapping": 1}


def test_argument_shape_is_fixed_bounded_and_does_not_inspect_nested_values():
    stream = io.StringIO()
    logger = ToolLogger(output=stream)
    logger.log_invocation("GitTool", "git_status", {}, ToolResult.ok(), 0)
    logger.log_invocation("GitTool", "git_diff", {
        "a": None, "b": True, "c": 3, "d": 1.5, "e": "SECRET",
        "f": {"SECRET": "SECRET"}, "g": ["SECRET"], "h": object(),
    }, ToolResult.ok(), 0)
    logger.log_invocation("GitTool", "git_diff", {str(i): "SECRET" for i in range(150)}, ToolResult.ok(), 0)
    lines = stream.getvalue().splitlines()
    assert "SECRET" not in stream.getvalue()
    assert json.loads(lines[0])["arguments"] == EMPTY_SHAPE
    assert json.loads(lines[1])["arguments"] == {
        "null": 1, "bool": 1, "number": 2, "string": 1,
        "mapping": 1, "array": 1, "other": 1,
    }
    assert json.loads(lines[2])["arguments"] == EMPTY_SHAPE | {"string": 100}


def test_allowed_operation_labels_match_builtin_schemas():
    from laew.knowledge.tool import KnowledgeProposalTool
    from laew.memory.tool import MemoryTool
    from laew.rag.rag_tool import RagTool
    from laew.tools.git import GitTool
    from laew.tools.terminal import TerminalTool
    from laew.tools.web import WebTool

    for cls in (FilesystemTool, GitTool, TerminalTool, WebTool, RagTool,
                MemoryTool, KnowledgeProposalTool):
        assert base._LOG_OPERATIONS[cls.__name__] == set(cls.operations)


@pytest.mark.parametrize("code", ["ERR_RAG_FAILURE", "ERR_INVALID_OPERATION",
                                    "ERR_MEMORY_DISABLED", "ERR_MEMORY_UNAVAILABLE", "ERR_MEMORY_RECALL"])
def test_known_tool_specific_error_codes_are_retained(code):
    stream = io.StringIO()
    ToolLogger(output=stream).log_invocation("MemoryTool", "recall", {}, ToolResult.error(code, "SECRET"), 0)
    assert json.loads(stream.getvalue())["error_code"] == code
    assert "SECRET" not in stream.getvalue()
