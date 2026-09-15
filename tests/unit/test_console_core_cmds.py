"""Tests for core console commands (check, info, set, provider, prompt,
budget, tools).

These exercise the manifest/validation and configuration-precedence surface of
the console.  Provider commands use a stubbed provider so nothing touches a
live model or a network endpoint.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from laew.console.commands.core import (
    cmd_check,
    cmd_info,
    cmd_set,
    cmd_provider,
    cmd_prompt,
    cmd_budget,
    cmd_tools,
)
from laew.console.state import SessionState


MANIFEST = {
    "version": "1.0",
    "workspace": {"root": ".", "allowed_paths": ["docs"], "restricted_paths": [".git"]},
    "tools": {"categories": {"terminal": {"allowlist": ["ls"]}}},
    "agent": {"llm": {"providers": [{"type": "ollama", "model": "llama3.1"}]}},
}


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


@pytest.fixture
def mock_manifest_state(state):
    """A session state whose manifest is stubbed with a fixture dict."""
    with patch.object(state, "load_manifest", return_value=MANIFEST):
        yield state


def test_check_validates_manifest(mock_manifest_state, capsys):
    """check loads the manifest and reports workspace/tool info."""
    assert cmd_check([], mock_manifest_state) == 0
    out = capsys.readouterr().out
    assert "[OK] Manifest loaded" in out
    assert "version: 1.0" in out
    assert "tool categories" in out


def test_check_bad_manifest(state, capsys):
    """A bad manifest nets into a readable failure."""
    from laew.console.state import StateError
    with patch.object(state, "load_manifest", side_effect=StateError("bad file")):
        assert cmd_check([], state) == 1
    assert "bad file" in capsys.readouterr().out


def test_info_shows_resolved_config(mock_manifest_state, capsys):
    """info prints the resolved provider and session overrides."""
    assert cmd_info([], mock_manifest_state) == 0
    out = capsys.readouterr().out
    assert "manifest:" in out
    assert "approval: ask" in out


def test_set_valid_override(mock_manifest_state, capsys):
    """set applies valid session overrides."""
    assert cmd_set(["timeout", "600"], mock_manifest_state) == 0
    assert mock_manifest_state.overrides["timeout"] == "600"
    assert cmd_set(["model", "llama3.2"], mock_manifest_state) == 0
    assert mock_manifest_state.overrides["model"] == "llama3.2"


def test_set_invalid_key(mock_manifest_state, capsys):
    """set rejects unknown keys with the accepted list."""
    assert cmd_set(["nonsense", "1"], mock_manifest_state) == 1
    assert "Unknown setting 'nonsense'" in capsys.readouterr().out


def test_set_invalid_approval(mock_manifest_state, capsys):
    """set rejects invalid approval modes."""
    assert cmd_set(["approval", "maybe"], mock_manifest_state) == 1
    assert "Invalid approval mode" in capsys.readouterr().out


def test_set_invalid_timeout(mock_manifest_state, capsys):
    """set rejects non-numeric or non-positive timeouts."""
    assert cmd_set(["timeout", "abc"], mock_manifest_state) == 1
    assert "timeout must be an integer" in capsys.readouterr().out
    assert cmd_set(["timeout", "0"], mock_manifest_state) == 1


def test_set_requires_key_and_value(mock_manifest_state, capsys):
    """set without key/value is a usage error."""
    assert cmd_set([], mock_manifest_state) == 1
    assert cmd_set(["timeout"], mock_manifest_state) == 1
    assert "usage:" in capsys.readouterr().out


def _fake_provider(**kwargs):
    p = MagicMock()
    p.is_available.return_value = kwargs.get("available", True)
    p.list_models.return_value = kwargs.get("models", ["llama3.1"])
    p.generate.return_value = SimpleNamespace(content="generated text")
    return p


def test_provider_default_is_info(mock_manifest_state, capsys):
    """provider with no subcommand shows resolved provider info."""
    fake = _fake_provider()
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider([], mock_manifest_state) == 0
    out = capsys.readouterr().out
    assert "provider type: ollama" in out
    assert "availability: True" in out


def test_provider_models(mock_manifest_state, capsys):
    """provider models lists the installed model names."""
    fake = _fake_provider(models=["llama3.1", "phi3"])
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider(["models"], mock_manifest_state) == 0
    out = capsys.readouterr().out
    assert "llama3.1" in out and "phi3" in out


def test_provider_models_unreachable(mock_manifest_state, capsys):
    """A live list_models failure nets into a readable failure."""
    fake = _fake_provider()
    fake.list_models.side_effect = RuntimeError("connection refused")
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider(["models"], mock_manifest_state) == 1
    assert "could not list models" in capsys.readouterr().out


def test_provider_health_ok(mock_manifest_state, capsys):
    """provider health is 0 when the provider is reachable."""
    fake = _fake_provider(available=True)
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider(["health"], mock_manifest_state) == 0
    assert "[OK]" in capsys.readouterr().out


def test_provider_health_down(mock_manifest_state, capsys):
    """provider health is non-zero when the provider is unreachable."""
    fake = _fake_provider(available=False)
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider(["health"], mock_manifest_state) == 1
    assert "[FAIL]" in capsys.readouterr().out


def test_provider_generate(mock_manifest_state, capsys):
    """provider generate prints the one-turn response content."""
    fake = _fake_provider()
    with patch("laew.console.commands.core._build_provider", return_value=fake):
        assert cmd_provider(["generate", "hi"], mock_manifest_state) == 0
    out = capsys.readouterr().out
    assert "generated text" in out


def test_provider_unknown_subcommand(mock_manifest_state, capsys):
    """provider with an unknown subcommand is rejected."""
    assert cmd_provider(["transmute"], mock_manifest_state) == 1
    assert "unknown provider subcommand" in capsys.readouterr().out


def test_budget_estimates_tokens(state, capsys):
    """budget estimates tokens for the given text."""
    assert cmd_budget(["hello", "world"], state) == 0
    out = capsys.readouterr().out
    assert "characters: 11" in out
    assert "estimated tokens:" in out


def test_budget_requires_text(state, capsys):
    """budget with no text is a usage error."""
    assert cmd_budget([], state) == 1
    assert "usage:" in capsys.readouterr().out


def test_tools_lists_tool_operations(capsys):
    """tools enumerates the registry tools and their operations offline."""
    state = SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")
    assert cmd_tools([], state) == 0
    out = capsys.readouterr().out
    assert "FilesystemTool:" in out
    assert "operations:" in out


def test_prompt_list_lists_templates(capsys):
    """prompt list enumerates the shipped templates without a model."""
    assert cmd_prompt(["list"], SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")) == 0
    assert capsys.readouterr().out


def test_prompt_unknown_subcommand(capsys):
    """prompt with an unknown subcommand is rejected."""
    state = SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")
    assert cmd_prompt(["compile"], state) == 1
    assert "unknown prompt subcommand" in capsys.readouterr().out