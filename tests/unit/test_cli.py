"""Tests for LAEW CLI."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from laew.cli import cmd_check, main
from laew.runtime import resolve_model_name


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
        "agent": {
            "llm": {
                "providers": [
                    {"name": "ollama_primary", "type": "ollama", "model": "llama3.1"},
                ],
                "retry": {
                    "max_attempts": 1,
                    "backoff_base_ms": 100,
                    "max_backoff_ms": 200,
                },
                "roles": {
                    "primary": ["ollama_primary"],
                    "embedding": ["ollama_primary"],
                    "reviewer": ["ollama_primary"],
                }
            }
        }
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


@pytest.mark.parametrize("command", ["console", "chat", "tool", "memory", "workflow", "multiagent", "rag-migrate"])
def test_retired_entry_points_are_rejected_without_starting_services(command, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["laew", command])
    with patch("laew.backup.writer.enroll_writer_process") as enroll, patch("laew.web.serve") as serve:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
        enroll.assert_not_called()
        serve.assert_not_called()
    assert "invalid choice" in capsys.readouterr().err


def test_workbench_launcher_preserves_options_and_fence(monkeypatch):
    monkeypatch.setattr("sys.argv", ["laew", "ui", "--manifest", "fixture.yaml", "--port", "18765",
                                    "--workspace-root", "fixture", "--projects-root", "projects", "--no-browser"])
    with patch("laew.backup.writer.enroll_writer_process") as enroll, patch("laew.web.serve") as serve:
        def start(*_args, **_kwargs):
            enroll.assert_called_once_with()
        serve.side_effect = start
        assert main() == 0
    serve.assert_called_once_with("fixture.yaml", 18765, open_browser=False,
                                  workspace_root="fixture", projects_root="projects")


class TestModelResolution:
    """Tests for chat model fallback when the requested model is not installed."""

    def test_explicit_cli_model_wins(self):
        """An explicit --model is used verbatim, no fallback."""
        provider = MagicMock()
        result = resolve_model_name(
            cli_model="qwen2.5",
            manifest_model="llama3.1",
            provider=provider,
        )
        assert result == "qwen2.5"
        provider.list_models.assert_not_called()

    def test_installed_model_used_as_is(self):
        """Manifest model that is installed is used unchanged (exact tag match)."""
        provider = MagicMock()
        provider.list_models.return_value = ["llama3.1:latest", "nomic-embed-text"]
        result = resolve_model_name(None, "llama3.1:latest", provider)
        assert result == "llama3.1:latest"

    def test_installed_model_without_tag_resolves_via_family(self):
        """Untagged request matches an installed tagged model of the same family."""
        provider = MagicMock()
        provider.list_models.return_value = ["llama3.1:latest"]
        result = resolve_model_name(None, "llama3.1", provider)
        assert result == "llama3.1:latest"

    def test_family_fallback_to_installed(self):
        """Missing llama3.1 falls back to installed llama3.2 with a notice."""
        provider = MagicMock()
        provider.list_models.return_value = ["llama3.2:latest"]
        result = resolve_model_name(None, "llama3.1", provider)
        assert result == "llama3.2:latest"

    def test_first_installed_model_fallback(self):
        """No family match falls back to the first installed model."""
        provider = MagicMock()
        provider.list_models.return_value = ["mistral:latest"]
        result = resolve_model_name(None, "llama3.1", provider)
        assert result == "mistral:latest"

    def test_no_installed_models_uses_requested(self):
        """If Ollama has no models, keep the requested model name."""
        provider = MagicMock()
        provider.list_models.return_value = []
        result = resolve_model_name(None, "llama3.1", provider)
        assert result == "llama3.1"

    def test_provider_error_uses_requested(self):
        """If listing models fails, keep the requested model name."""
        provider = MagicMock()
        provider.list_models.side_effect = RuntimeError("Ollama down")
        result = resolve_model_name(None, "llama3.1", provider)
        assert result == "llama3.1"
