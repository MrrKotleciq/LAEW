"""Terminal command execution tool wrapper (tools/terminal/CONTRACT.md)."""

import shlex
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

    operations = {
        "run_command": {
            "params": ["command", "cwd", "timeout_ms"],
            "description": "Execute a shell command with optional working directory and timeout."
        }
    }

    # Strictly forbidden patterns
    BLACKLIST = {
        "sudo", "su", "doas",
        "rm -rf", "mkfs", "dd if=",
        "chmod", "chown",
        "> /dev/", "nc -e", "/dev/tcp/"
    }

    # Safe read-only inspection commands that bypass approval
    ALLOWLIST = {
        "ls", "dir", "cat", "head", "tail", "grep", "find", "pwd",
        "git status", "git diff", "git log",
        "true", "false", "echo"
    }

    # Shell operators that chain, redirect, or substitute commands.
    # Allowing any of these defeats the allowlist boundary, so any command
    # containing one is never treated as an allowlisted inspector.
    SHELL_METACHARACTERS = (";", "|", "&", "`", ">", "<", "\n", "\r")

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

    def _contains_shell_metacharacters(self, command: str) -> bool:
        """
        Check if a command uses shell chaining, redirection, or substitution.

        These operators (";", "|", "&&", "(`", ">", "<", "$(") could let a
        command escape its intended execution, so presence of any of them
        disqualifies the command from allowlist treatment.
        """
        for meta in self.SHELL_METACHARACTERS:
            if meta in command:
                return True
        # Command substitution ($( ... ) or ${ ... })
        return "$(" in command or "${" in command

    def _is_allowlisted(self, command: str) -> bool:
        """
        Check if command matches a safe inspector command.

        Matching is token-based on the whole command line (after shell-style
        splitting), not a raw string prefix.  This prevents prefix-injection
        bypasses such as "ls; rm -rf /" and "echo > /etc/passwd" from being
        treated as the allowlisted inspector while still allowing safe
        argument forms like "ls -la" or "git status --porcelain".
        """
        if self._contains_shell_metacharacters(command):
            return False

        try:
            argv = shlex.split(command)
        except ValueError:
            # Unbalanced quotes -> not a well-formed command we can vet.
            return False

        if not argv:
            return False

        for safe_cmd in self.ALLOWLIST:
            safe_tokens = shlex.split(safe_cmd)
            if len(argv) >= len(safe_tokens) and argv[: len(safe_tokens)] == safe_tokens:
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

            # Split the command into an argument vector and execute without a
            # shell (shell=False).  Even if a metacharacter slips through, it
            # becomes an ordinary argument instead of shell syntax.
            try:
                argv = shlex.split(command)
            except ValueError as e:
                return ToolResult.error(
                    ErrorCode.ERR_INVALID_INPUT,
                    f"Invalid command syntax: {e}"
                )

            # Subprocess execution
            process = subprocess.run(
                argv,
                shell=False,
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
