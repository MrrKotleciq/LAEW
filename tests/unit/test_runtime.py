"""Tests for shared runtime composition helpers (laew/runtime.py).

These helpers were moved verbatim out of laew/cli.py so both the one-shot CLI
and the interactive console resolve configuration and build tools through the
same code path. The expectations below mirror the original CLI tests.
"""

from unittest.mock import patch, MagicMock

import pytest

from laew.runtime import (
    provider_cfg_from_manifest,
    terminal_allowlist_from_manifest,
    build_shared_tools,
    build_provider,
    resolve_model_name,
)


MANIFEST_WITH_PROVIDERS = {
    "agent": {
        "llm": {
            "providers": [
                {"type": "ollama", "model": "llama3.1"},
                {"type": "openai", "model": "gpt-4o", "host": "api.openai.com"},
            ]
        }
    },
    "tools": {
        "categories": {"terminal": {"allowlist": ["ls", "git status"]}}
    },
}


@pytest.mark.parametrize(
    "provider_type,expected_type",
    [
        (None, "ollama"),
        ("ollama", "ollama"),
        ("openai", "openai"),
    ],
)
def test_provider_cfg_from_manifest(provider_type, expected_type):
    """Select the manifest provider by type, defaulting to the first."""
    cfg = provider_cfg_from_manifest(MANIFEST_WITH_PROVIDERS, provider_type)
    assert cfg["type"] == expected_type


def test_provider_cfg_from_manifest_falls_back_to_first_for_unknown_type():
    """An unknown requested type falls back to the first provider."""
    cfg = provider_cfg_from_manifest(MANIFEST_WITH_PROVIDERS, "anthropic")
    assert cfg["type"] == "ollama"


def test_provider_cfg_from_manifest_defaults_when_no_providers():
    """No providers declared: default to Ollama."""
    cfg = provider_cfg_from_manifest({})
    assert cfg == {"type": "ollama"}


def test_terminal_allowlist_from_manifest():
    """Extract the terminal allowlist, or None when absent."""
    assert terminal_allowlist_from_manifest(MANIFEST_WITH_PROVIDERS) == [
        "ls", "git status"
    ]
    assert terminal_allowlist_from_manifest({}) is None


def test_build_shared_tools_contains_four_registry_tools():
    """The shared tool suite exposes the four security-gated tools."""
    tools = build_shared_tools(["ls"])
    names = {t.name for t in tools}
    assert names == {"FilesystemTool", "GitTool", "TerminalTool", "WebTool"}


def test_build_provider_uses_registry():
    """build_provider delegates to the provider registry with overrides."""
    fake = MagicMock()

    with patch("laew.runtime.create_provider", return_value=fake) as factory:
        provider = build_provider(
            MANIFEST_WITH_PROVIDERS, base_url="http://localhost:11434", timeout=42
        )
    factory.assert_called_once_with(
        {"type": "ollama", "model": "llama3.1"},
        base_url="http://localhost:11434",
        timeout=42,
    )
    assert provider is fake


def test_resolve_model_name_explicit_cli_wins():
    """An explicit CLI/session model is returned untrusted and unmodified."""
    provider = MagicMock()
    assert resolve_model_name("llama3.2", "llama3.1", provider) == "llama3.2"
    provider.list_models.assert_not_called()


def test_resolve_model_name_manifest_model_installed():
    """A requested model installed on the provider is used as-is."""
    provider = MagicMock()
    provider.list_models.return_value = ["llama3.1", "llama3.2"]
    assert resolve_model_name(None, "llama3.1", provider) == "llama3.1"


def test_resolve_model_name_falls_back_to_family_match():
    """A missing manifest model falls back to a close family match."""
    provider = MagicMock()
    provider.list_models.return_value = ["llama3.2", "phi3"]
    resolved = resolve_model_name(None, "llama3.1", provider)
    assert resolved == "llama3.2"


def test_resolve_model_name_unavailable_returns_requested_default():
    """Provider unreachable: return the requested model or llama3.1."""
    provider = MagicMock()
    provider.list_models.side_effect = RuntimeError("connection refused")
    assert resolve_model_name(None, "llama3.1", provider) == "llama3.1"
    assert resolve_model_name(None, None, provider) == "llama3.1"