"""Tests for tool invocation logging (ADR-016)."""

import json
import io
import tempfile
from pathlib import Path

import pytest

from laew.tools.base import (
    Tool,
    ToolResult,
    ErrorCode,
    configure_tool_logger,
    get_tool_logger,
)
from laew.tools.filesystem import FilesystemTool


class DummyTool(Tool):
    """Dummy tool for testing logging."""

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        if operation == "fail":
            return False, "Test failure"
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        if operation == "fail":
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT, "Test failure"
            )
        elif operation == "success":
            return ToolResult.ok(data={"result": "success"})
        else:
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT, f"Unknown operation: {operation}"
            )


def test_tool_logging_success():
    """Test that successful tool invocations are logged."""
    # Create string buffer to capture logs
    log_buffer = io.StringIO()

    # Configure logger to use our buffer
    configure_tool_logger(output=log_buffer)

    # Create and use dummy tool
    tool = DummyTool()
    tool.approve()  # Bypass approval for testing

    result = tool.call("success", test_arg="test_value")

    # Verify result
    assert result.success
    assert result.data["result"] == "success"

    # Get log output
    log_output = log_buffer.getvalue().strip()
    assert log_output

    # Parse JSON log entry
    log_entry = json.loads(log_output)

    # Verify log structure
    assert log_entry["tool"] == "DummyTool"
    assert log_entry["operation"] == "success"
    assert log_entry["arguments"]["test_arg"] == "test_value"
    assert log_entry["success"] is True
    assert log_entry["error_code"] is None
    assert log_entry["error_message"] is None
    assert log_entry["status"] == "SUCCESS"
    assert isinstance(log_entry["duration_ms"], int)
    assert log_entry["duration_ms"] >= 0
    assert "timestamp" in log_entry


def test_tool_logging_failure():
    """Test that failed tool invocations are logged."""
    # Create string buffer to capture logs
    log_buffer = io.StringIO()

    # Configure logger to use our buffer
    configure_tool_logger(output=log_buffer)

    # Create and use dummy tool
    tool = DummyTool()
    tool.approve()  # Bypass approval for testing

    result = tool.call("fail", test_arg="test_value")

    # Verify result
    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_INPUT
    assert result.error_message == "Test failure"

    # Get log output
    log_output = log_buffer.getvalue().strip()
    assert log_output

    # Parse JSON log entry
    log_entry = json.loads(log_output)

    # Verify log structure
    assert log_entry["tool"] == "DummyTool"
    assert log_entry["operation"] == "fail"
    assert log_entry["arguments"]["test_arg"] == "test_value"
    assert log_entry["success"] is False
    assert log_entry["error_code"] == ErrorCode.ERR_INVALID_INPUT
    assert log_entry["error_message"] == "Test failure"
    assert log_entry["status"] == "FAILURE"
    assert isinstance(log_entry["duration_ms"], int)
    assert log_entry["duration_ms"] >= 0
    assert "timestamp" in log_entry


def test_tool_logging_argument_sanitization():
    """Test that sensitive arguments are sanitized in logs."""
    # Create string buffer to capture logs
    log_buffer = io.StringIO()

    # Configure logger to use our buffer
    configure_tool_logger(output=log_buffer)

    # Create and use dummy tool
    tool = DummyTool()
    tool.approve()  # Bypass approval for testing

    result = tool.call(
        "success",
        normal_arg="visible",
        password="secret123",
        api_key="key_abc",
        long_string="x" * 300
    )

    # Get log output
    log_output = log_buffer.getvalue().strip()
    assert log_output

    # Parse JSON log entry
    log_entry = json.loads(log_output)

    # Verify sanitization
    assert log_entry["arguments"]["normal_arg"] == "visible"
    assert log_entry["arguments"]["password"] == "[REDACTED]"
    assert log_entry["arguments"]["api_key"] == "[REDACTED]"
    assert "...[TRUNCATED]" in log_entry["arguments"]["long_string"]
    assert len(log_entry["arguments"]["long_string"]) <= 213  # 200 + "...[TRUNCATED]"


def test_real_tool_logging_filesystem():
    """Test that real filesystem tools produce logs."""
    # Create string buffer to capture logs
    log_buffer = io.StringIO()

    # Configure logger to use our buffer
    configure_tool_logger(output=log_buffer)

    # Use real filesystem tool
    tool = FilesystemTool()
    tool.approve()  # Bypass approval for testing

    # Test successful operation
    result = tool.call("view_file", file_path="README.md")

    # Verify we get a result (might fail if file doesn't exist, but should still log)
    # The important part is that logging happened

    # Get log output
    log_output = log_buffer.getvalue().strip()
    assert log_output

    # Parse JSON log entry
    log_entry = json.loads(log_output)

    # Verify log structure
    assert log_entry["tool"] == "FilesystemTool"
    assert log_entry["operation"] == "view_file"
    assert log_entry["arguments"]["file_path"] == "README.md"
    assert "timestamp" in log_entry
    assert isinstance(log_entry["duration_ms"], int)
    assert log_entry["duration_ms"] >= 0
    assert log_entry["status"] in ["SUCCESS", "FAILURE"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])