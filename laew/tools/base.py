"""Base class for LAEW tool runtime wrappers (P8 - Security Below Model Layer)."""

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, IO


class ToolError(Exception):
    """Base exception for tool execution errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class ErrorCode(str, Enum):
    """Standard error codes for tool operations (CONTRACT.md compliance)."""

    # Common errors
    ERR_INVALID_INPUT = "ERR_INVALID_INPUT"
    ERR_UNAUTHORIZED = "ERR_UNAUTHORIZED"
    ERR_TIMEOUT = "ERR_TIMEOUT"

    # Filesystem errors
    ERR_FILE_NOT_FOUND = "ERR_FILE_NOT_FOUND"
    ERR_PATH_DENIED = "ERR_PATH_DENIED"
    ERR_PATH_OUT_OF_BOUNDS = "ERR_PATH_OUT_OF_BOUNDS"
    ERR_FILE_EXISTS = "ERR_FILE_EXISTS"
    ERR_MUTATION_FORBIDDEN = "ERR_MUTATION_FORBIDDEN"
    ERR_BINARY_FILE = "ERR_BINARY_FILE"
    ERR_TARGET_NOT_FOUND = "ERR_TARGET_NOT_FOUND"
    ERR_DIR_NOT_FOUND = "ERR_DIR_NOT_FOUND"

    # Git errors
    ERR_NOTHING_TO_COMMIT = "ERR_NOTHING_TO_COMMIT"
    ERR_DIRTY_WORKING_TREE = "ERR_DIRTY_WORKING_TREE"

    # Terminal errors
    ERR_COMMAND_BLOCKED = "ERR_COMMAND_BLOCKED"
    ERR_NON_ZERO_EXIT = "ERR_NON_ZERO_EXIT"

    # Web errors
    ERR_INVALID_PROTOCOL = "ERR_INVALID_PROTOCOL"
    ERR_FETCH_FAILED = "ERR_FETCH_FAILED"


@dataclass
class ToolResult:
    """Result of a tool operation."""

    success: bool
    data: Optional[Any] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def ok(cls, data: Any = None) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def error(cls, code: str, message: str) -> "ToolResult":
        """Create an error result."""
        return cls(success=False, error_code=code, error_message=message)

    def to_dict(self) -> dict:
        """Convert result to dictionary for logging (sanitized)."""
        return {
            "success": self.success,
            "error_code": self.error_code,
            "error_message": self.error_message,
            # Note: data is intentionally excluded from logs to prevent leaking sensitive content
        }


@dataclass
class ToolInvocationLog:
    """Structured log entry for a tool invocation (ADR-016)."""

    timestamp: str
    tool: str
    operation: str
    arguments: dict
    success: bool
    error_code: Optional[str]
    error_message: Optional[str]
    duration_ms: int
    status: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class ToolLogger:
    """
    Logger for tool invocations implementing ADR-016.

    Writes structured logs with timestamp, tool name, operation, arguments,
    result status, duration, and error codes.
    """

    def __init__(self, output: Optional[IO[str]] = None, log_level: int = logging.INFO):
        """
        Initialize tool logger.

        Args:
            output: Optional output stream for logs (defaults to stderr via logging)
            log_level: Logging level (defaults to INFO)
        """
        self._output = output
        self._logger = logging.getLogger("laew.tools")
        self._logger.setLevel(log_level)

        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)
            formatter = logging.Formatter('%(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    def log_invocation(
        self,
        tool: str,
        operation: str,
        arguments: dict,
        result: ToolResult,
        duration_ms: int,
    ) -> None:
        """
        Log a tool invocation.

        Args:
            tool: Tool name
            operation: Operation name
            arguments: Operation arguments (will be sanitized)
            result: Tool result
            duration_ms: Duration in milliseconds
        """
        # Determine status
        status = "SUCCESS" if result.success else "FAILURE"

        # Sanitize arguments (remove potentially sensitive data)
        sanitized_args = self._sanitize_arguments(arguments)

        # Create log entry
        log_entry = ToolInvocationLog(
            timestamp=datetime.now(timezone.utc).isoformat(),
            tool=tool,
            operation=operation,
            arguments=sanitized_args,
            success=result.success,
            error_code=result.error_code,
            error_message=result.error_message,
            duration_ms=duration_ms,
            status=status,
        )

        # Output to stream if provided
        if self._output:
            self._output.write(log_entry.to_json() + "\n")
            self._output.flush()

        # Always log to logging infrastructure
        self._logger.info(log_entry.to_json())

    def _sanitize_arguments(self, arguments: dict) -> dict:
        """
        Sanitize arguments for logging (remove sensitive data).

        Args:
            arguments: Raw arguments dictionary

        Returns:
            Sanitized arguments dictionary
        """
        sanitized = {}
        sensitive_keys = {
            "password", "secret", "token", "api_key", "auth",
            "credential", "private_key", "passphrase"
        }

        for key, value in arguments.items():
            key_lower = key.lower()

            # Check for sensitive keys
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            # Truncate large values
            elif isinstance(value, str) and len(value) > 200:
                sanitized[key] = value[:199] + "...[TRUNCATED]"
            else:
                sanitized[key] = value

        return sanitized


# Global tool logger instance (can be configured by application)
_tool_logger: Optional[ToolLogger] = None


def get_tool_logger() -> ToolLogger:
    """Get the global tool logger instance."""
    global _tool_logger
    if _tool_logger is None:
        _tool_logger = ToolLogger()
    return _tool_logger


def configure_tool_logger(output: Optional[IO[str]] = None, log_level: int = logging.INFO) -> None:
    """
    Configure the global tool logger.

    Args:
        output: Optional output stream for logs
        log_level: Logging level
    """
    global _tool_logger
    _tool_logger = ToolLogger(output=output, log_level=log_level)


class Tool(ABC):
    """
    Abstract base class for LAEW tool wrappers.

    All tools implement:
    - Security enforcement (P8)
    - User approval gates
    - Standardized error codes (CONTRACT.md)
    - Logging and traceability (ADR-016)
    """

    def __init__(self, requires_approval: bool = False):
        """
        Initialize tool.

        Args:
            requires_approval: Whether this tool requires user approval by default
        """
        self._requires_approval = requires_approval
        self._approved = False

    @property
    def name(self) -> str:
        """Return tool name."""
        return self.__class__.__name__

    def approve(self):
        """Mark this tool operation as user-approved."""
        self._approved = True

    def is_approved(self) -> bool:
        """Check if operation is approved."""
        return self._approved or not self._requires_approval

    @abstractmethod
    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """
        Validate an operation before execution.

        Args:
            operation: Operation name (e.g., 'view_file', 'write_file')
            **kwargs: Operation-specific parameters

        Returns:
            Tuple of (is_valid, error_message)
        """

    @abstractmethod
    def execute(self, operation: str, **kwargs) -> ToolResult:
        """
        Execute a tool operation.

        Args:
            operation: Operation name
            **kwargs: Operation-specific parameters

        Returns:
            ToolResult with success flag, data, or error code
        """

    def call(self, operation: str, **kwargs) -> ToolResult:
        """
        Call a tool operation with validation, approval checks, and logging.

        Args:
            operation: Operation name
            **kwargs: Operation-specific parameters

        Returns:
            ToolResult
        """
        # Record start time
        start_time = time.perf_counter()

        # Validate
        is_valid, error_msg = self.validate(operation, **kwargs)
        if not is_valid:
            result = ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT, error_msg or "Invalid operation"
            )
            self._log_invocation(operation, kwargs, result, start_time)
            return result

        # Check approval
        if self._requires_approval and not self.is_approved():
            result = ToolResult.error(
                ErrorCode.ERR_UNAUTHORIZED,
                f"Operation '{operation}' requires user approval",
            )
            self._log_invocation(operation, kwargs, result, start_time)
            return result

        # Execute
        result = self.execute(operation, **kwargs)

        # Log invocation
        self._log_invocation(operation, kwargs, result, start_time)

        return result

    def _log_invocation(
        self,
        operation: str,
        arguments: dict,
        result: ToolResult,
        start_time: float,
    ) -> None:
        """
        Log tool invocation (ADR-016).

        Args:
            operation: Operation name
            arguments: Operation arguments
            result: Tool result
            start_time: Start time from perf_counter()
        """
        # Calculate duration
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        # Get logger and log invocation
        logger = get_tool_logger()
        logger.log_invocation(
            tool=self.name,
            operation=operation,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
        )
