"""Tests for LAEW CLI."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from laew.cli import main, cmd_check, cmd_tool
from laew.tools import ToolResult, ErrorCode
from laew.manifest import ManifestError


@pytest.fixture
def temp_manifest():
    """Create a temporary manifest file for testing."""
    manifest_data = {
        "version": "1.0",
        "system_name": "LAEW-TEST",
        "stage": "test",
        "workspace": {
            "root": ".",
            "allowed_paths": ["docs", "tests"],
            "restricted_paths": [".git", "secrets"],
            "ignored_patterns": ["**/.env*", "**/__pycache__/**"],
        },
        "tools": {
            "categories": {
                "filesystem": {
                    "policy": "read_only_by_default",
                    "allowed_operations": ["view_file"],
                },
                "git": {
                    "policy": "inspection_first",
                    "allowed_operations": ["status"],
                },
                "terminal": {
                    "policy": "safe_command_allowlist",
                    "allowlist": ["ls", "git status"],
                },
                "web": {
                    "policy": "read_only",
                    "allowed_operations": ["read_url_content"],
                },
            },
        },
        "models": {
            "roles": {
                "primary": {
                    "description": "Test primary model",
                    "context_budget": {
                        "total": 18000,
                    },
                },
                "embedding": {
                    "description": "Test embedding model",
                },
                "reviewer": {
                    "description": "Test reviewer model",
                },
            },
        },
        "memory": {
            "session": {
                "type": "ephemeral",
                "storage": "runtime/sessions",
            },
            "second_brain": {
                "type": "obsidian_vault",
                "path": "knowledge",
            },
        },
        "rag": {
            "pipeline": {
                "retrieval": "vector_search",
                "top_k": 5,
            },
        },
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(manifest_data, f)
        yield Path(f.name)

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


class TestCheckCommand:
    """Tests for 'laew check' command."""

    def test_check_valid_manifest(self, temp_manifest, capsys):
        """Test check with valid manifest."""
        with patch("sys.argv", ["laew", "check", "--manifest", str(temp_manifest)]):
            exit_code = main()

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Validating manifest" in captured.out
        assert "Manifest loaded successfully" in captured.out
        assert "All checks passed" in captured.out

    def test_check_missing_manifest(self, capsys):
        """Test check with missing manifest file."""
        with patch("sys.argv", ["laew", "check", "--manifest", "nonexistent.yaml"]):
            exit_code = main()

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Manifest file not found" in captured.out

    def test_check_invalid_manifest(self, capsys):
        """Test check with invalid manifest (missing required fields)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"version": "1.0"}, f)  # Missing required fields
            manifest_path = Path(f.name)

        try:
            with patch("sys.argv", ["laew", "check", "--manifest", str(manifest_path)]):
                exit_code = main()

            assert exit_code == 1

            captured = capsys.readouterr()
            assert "validation failed" in captured.out.lower()
        finally:
            manifest_path.unlink(missing_ok=True)

    def test_check_displays_workspace_config(self, temp_manifest, capsys):
        """Test check displays workspace configuration."""
        with patch("sys.argv", ["laew", "check", "--manifest", str(temp_manifest)]):
            exit_code = main()

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Workspace Configuration:" in captured.out
        assert "Allowed Paths:" in captured.out
        assert "Restricted Paths:" in captured.out

    def test_check_displays_tool_registry(self, temp_manifest, capsys):
        """Test check displays tool registry."""
        with patch("sys.argv", ["laew", "check", "--manifest", str(temp_manifest)]):
            exit_code = main()

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Tool Registry:" in captured.out
        assert "filesystem:" in captured.out
        assert "read_only_by_default" in captured.out

    def test_check_displays_model_roles(self, temp_manifest, capsys):
        """Test check displays model roles."""
        with patch("sys.argv", ["laew", "check", "--manifest", str(temp_manifest)]):
            exit_code = main()

        assert exit_code == 0

        captured = capsys.readouterr()
        assert "Model Roles:" in captured.out
        assert "primary:" in captured.out
        assert "18000 tokens" in captured.out


class TestToolCommand:
    """Tests for 'laew tool' command."""

    def test_tool_filesystem_view_file(self, capsys):
        """Test filesystem tool view_file operation."""
        with patch("sys.argv", ["laew", "tool", "filesystem", "view_file", "file_path=README.md"]):
            exit_code = main()

        # Should succeed or fail gracefully (file may not exist in test env)
        assert exit_code in [0, 1]

        captured = capsys.readouterr()
        assert "Executing: filesystem.view_file" in captured.out

    def test_tool_unknown_tool(self, capsys):
        """Test tool command with unknown tool."""
        with patch("sys.argv", ["laew", "tool", "unknown_tool", "some_operation"]):
            with pytest.raises(SystemExit):
                main()

    def test_tool_invalid_argument_format(self, capsys):
        """Test tool command with invalid argument format."""
        with patch("sys.argv", ["laew", "tool", "filesystem", "view_file", "invalid_arg"]):
            exit_code = main()

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "Invalid argument format" in captured.out

    def test_tool_with_log_file(self, capsys):
        """Test tool command with logging to file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = Path(f.name)

        try:
            with patch("sys.argv", [
                "laew", "tool", "filesystem", "view_file",
                "file_path=README.md", "--log", str(log_path)
            ]):
                exit_code = main()

            # Check log file was created and contains data
            log_content = log_path.read_text()
            # Log should contain JSON structure (may be empty if operation failed before logging)
            # We just verify no exception was raised
        finally:
            log_path.unlink(missing_ok=True)

    def test_tool_requires_approval_flag(self, capsys):
        """Test tool command with --require-approval flag on mutating operation."""
        with patch("sys.argv", [
            "laew", "tool", "filesystem", "write_file",
            "file_path=test.txt", "content=hello", "--require-approval"
        ]):
            exit_code = main()

        # Should fail because approval not granted
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "ERR_UNAUTHORIZED" in captured.out or "requires user approval" in captured.out


class TestMainFunction:
    """Tests for main CLI entry point."""

    def test_no_command_shows_help(self, capsys):
        """Test that running without command shows help."""
        with patch("sys.argv", ["laew"]):
            exit_code = main()

        assert exit_code == 1

        captured = capsys.readouterr()
        assert "usage: laew" in captured.out or "Available commands" in captured.out

    def test_version_flag(self, capsys):
        """Test --version flag."""
        with patch("sys.argv", ["laew", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "laew 0.1.0" in captured.out

    def test_invalid_command(self, capsys):
        """Test invalid command handling."""
        with patch("sys.argv", ["laew", "invalid_command"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # argparse exits with code 2 for invalid command
            assert exc_info.value.code == 2


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_check_then_tool_workflow(self, temp_manifest, capsys):
        """Test typical workflow: check manifest, then execute tool."""
        # Step 1: Check manifest
        with patch("sys.argv", ["laew", "check", "--manifest", str(temp_manifest)]):
            exit_code = main()

        assert exit_code == 0

        # Step 2: Execute tool
        with patch("sys.argv", ["laew", "tool", "filesystem", "list_dir", "directory_path=."]):
            exit_code = main()

        # Should complete (success or failure depends on directory existing)
        assert exit_code in [0, 1]

    def test_git_tool_operations(self, capsys):
        """Test git tool operations via CLI."""
        with patch("sys.argv", ["laew", "tool", "git", "git_status"]):
            exit_code = main()

        # Should succeed if in git repo, fail otherwise
        assert exit_code in [0, 1]

        captured = capsys.readouterr()
        assert "Executing: git.git_status" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
