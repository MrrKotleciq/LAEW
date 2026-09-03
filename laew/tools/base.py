"""Base class for LAEW tool runtime wrappers (P8 - Security Below Model Layer)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


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


class Tool(ABC):
    """
    Abstract base class for LAEW tool wrappers.

    All tools implement:
    - Security enforcement (P8)
    - User approval gates
    - Standardized error codes (CONTRACT.md)
    - Logging and traceability
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
        Call a tool operation with validation and approval checks.

        Args:
            operation: Operation name
            **kwargs: Operation-specific parameters

        Returns:
            ToolResult
        """
        # Validate
        is_valid, error_msg = self.validate(operation, **kwargs)
        if not is_valid:
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT, error_msg or "Invalid operation"
            )

        # Check approval
        if self._requires_approval and not self.is_approved():
            return ToolResult.error(
                ErrorCode.ERR_UNAUTHORIZED,
                f"Operation '{operation}' requires user approval",
            )

        # Execute
        return self.execute(operation, **kwargs)
