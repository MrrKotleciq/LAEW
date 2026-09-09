"""Terminal command execution tool wrapper (tools/terminal/CONTRACT.md)."""

import subprocess
import time
from pathlib import Path
from typing import Optional

from laew.tools.base import ErrorCode, Tool, ToolResult


class TerminalTool(Tool):
    """
    Terminal execution with security compliance (P8 / ADR-006).

    Implements tools/terminal/CONTRACT.md.

    Operations:
        - run_command: Executes shell commands (allowlisted or approved).
    """

    description = "Run allowlisted shell commands in a confined workspace"

    # Strictly forbidden patterns
    BLACKLIST = {
        "sudo", "su", "doas",
        "rm -rf", "mkfs", "dd if=",
        "chmod", "chown",
        "> /dev/", "nc -e", "/dev/tcp/"
    }

    # Safe read-only inspection commands that bypass approval
    ALLOWLIST = {
        "ls", "cat", "head", "tail", "grep", "find", "pwd",
        "git status", "git diff", "git log",
        "true", "false", "echo"
    }

    def __init__(self, workspace_root: Optional[Path | str] = None):
        """
        Initialize terminal tool.

        Args:
            workspace_root: Workspace confinement path (defaults to current directory)
        """
        super().__init__(requires_approval=False)
        if workspace_root is None:
            self.workspace_root = Path.cwd().resolve()
        else:
            self.workspace_root = Path(workspace_root).resolve()

        self._command_approved = False

    def approve(self):
        """Mark the command execution as approved."""
        self._command_approved = True

    def is_approved(self) -> bool:
        """Check if approved."""
        return self._command_approved

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate command execution."""
        if operation != "run_command":
            return False, f"Unknown operation: {operation}"

        if "command" not in kwargs or not kwargs["command"]:
            return False, "Missing required parameter: command"

        return True, None

    def _is_blacklisted(self, command: str) -> bool:
        """Check if command contains any forbidden patterns."""
        cmd_lower = command.lower()
        for pattern in self.BLACKLIST:
            if pattern in cmd_lower:
                return True
        return False

    def _is_allowlisted(self, command: str) -> bool:
        """
        Check if command matches a safe inspector command.

        The command is allowlisted if it starts with one of the allowed
        inspection tools (e.g. "ls -la" matches "ls").
        """
        cmd_strip = command.strip()
        for safe_cmd in self.ALLOWLIST:
            if cmd_strip == safe_cmd or cmd_strip.startswith(safe_cmd + " "):
                return True
        return False

    def run_command(
        self,
        command: str,
        cwd: str = ".",
        timeout_ms: int = 30000
    ) -> ToolResult:
        """Public interface for execution."""
        return self.call("run_command", command=command, cwd=cwd, timeout_ms=timeout_ms)

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """Execute run_command with security guards."""
        if operation != "run_command":
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, f"Unknown operation: {operation}")

        command = kwargs["command"]
        cwd = kwargs.get("cwd", ".")
        timeout_ms = kwargs.get("timeout_ms", 30000)

        # 1. Blacklist check (programmatic security)
        if self._is_blacklisted(command):
            return ToolResult.error(
                ErrorCode.ERR_COMMAND_BLOCKED,
                "Command violates security blacklist (destructive or forbidden operation)"
            )

        # 2. Allowlist checks vs Approval requirement
        if not self._is_allowlisted(command):
            approval_error = self._check_operation_approval("run_command", True)
            if approval_error:
                return approval_error

        # Execute command
        try:
            start_time = time.time()
            actual_cwd = (self.workspace_root / cwd).resolve()

            # Boundary validation
            try:
                actual_cwd.relative_to(self.workspace_root)
            except ValueError:
                return ToolResult.error(
                    ErrorCode.ERR_PATH_OUT_OF_BOUNDS,
                    "Execution working directory escapes workspace boundary"
                )

            # Convert working directory to string
            cwd_str = str(actual_cwd)

            # Subprocess execution
            process = subprocess.run(
                command,
                shell=True,
                cwd=cwd_str,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_ms / 1000.0
            )

            duration_ms = int((time.time() - start_time) * 1000)

            result_data = {
                "exit_code": process.returncode,
                "stdout": process.stdout,
                "stderr": process.stderr,
                "duration_ms": duration_ms,
            }

            return ToolResult.ok(result_data)

        except subprocess.TimeoutExpired:
            return ToolResult.error(ErrorCode.ERR_TIMEOUT, f"Command execution timed out after {timeout_ms}ms")
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))
