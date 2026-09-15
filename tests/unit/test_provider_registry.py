"""Unit tests for the LLM provider registry + factory (Milestone 11).

The registry + ``create_provider`` factory are the provider-selection seam,
shared by the CLI (``laew cli`` and MultiAgent run) and extensible to future
non-Ollama providers. Tests are written first (TDD RED) and must stay green on
Windows + Ubuntu.
"""

from __future__ import annotations

import pytest

from laew.llm import LLMError, OllamaProvider
from laew.llm.registry import (
    DEFAULT_REGISTRY,
    ProviderRegistry,
    build_ollama,
    create_provider,
)


# --------------------------------------------------------------------------- #
# Default registry dispatch
# --------------------------------------------------------------------------- #
def test_build_ollama_returns_ollama_provider():
    """A build_ollama entry returns an OllamaProvider."""
    provider = build_ollama({})
    assert isinstance(provider, OllamaProvider)


def test_registry_creates_ollama_provider_by_type():
    """A 'type': 'ollama' config dispatches to an OllamaProvider."""
    provider = create_provider({"type": "ollama"})
    assert isinstance(provider, OllamaProvider)


def test_registry_unknown_type_raises():
    """An unknown provider type raises LLMError listing supported types."""
    with pytest.raises(LLMError) as excinfo:
        create_provider({"type": "openai"})
    assert excinfo.value.code == "UNSUPPORTED_PROVIDER"
    assert "ollama" in excinfo.value.message


def test_registry_missing_type_raises():
    """A config without a 'type' key raises the same typed error."""
    with pytest.raises(LLMError) as excinfo:
        create_provider({})
    assert excinfo.value.code == "UNSUPPORTED_PROVIDER"


# --------------------------------------------------------------------------- #
# Timeout precedence: arg > env > manifest > default
# --------------------------------------------------------------------------- #
def test_timeout_arg_beats_env(monkeypatch):
    """An explicit timeout argument wins over the environment variable."""
    monkeypatch.setenv("LAEW_TIMEOUT", "30")
    provider = create_provider({"type": "ollama"}, timeout=42)
    assert provider._timeout == 42


def test_timeout_env_beats_manifest(monkeypatch):
    """LAEW_TIMEOUT wins over a manifest-declared timeout."""
    monkeypatch.setenv("LAEW_TIMEOUT", "30")
    cfg = {"type": "ollama", "timeout": 300}
    provider = create_provider(cfg)
    assert provider._timeout == 30


def test_timeout_manifest_beats_default():
    """A manifest-declared timeout wins over the provider default."""
    provider = create_provider({"type": "ollama", "timeout": 300})
    assert provider._timeout == 300


def test_timeout_default_when_unset(monkeypatch):
    """With no arg, env, or manifest timeout, the provider default is used."""
    monkeypatch.delenv("LAEW_TIMEOUT", raising=False)
    provider = create_provider({"type": "ollama"})
    assert provider._timeout == 120


# --------------------------------------------------------------------------- #
# Base URL precedence: arg > env > manifest host/port > default
# --------------------------------------------------------------------------- #
def test_base_url_arg_wins(monkeypatch):
    """An explicit base_url argument wins over env and manifest."""
    monkeypatch.setenv("LAEW_BASE_URL", "http://env:11434")
    provider = create_provider(
        {"type": "ollama", "host": "manifest", "port": 9999},
        base_url="http://arg:11434",
    )
    assert provider.base_url == "http://arg:11434"


def test_base_url_env_beats_manifest(monkeypatch):
    """LAEW_BASE_URL wins over a manifest host/port."""
    monkeypatch.setenv("LAEW_BASE_URL", "http://env:11434")
    provider = create_provider(
        {"type": "ollama", "host": "manifest", "port": 9999}
    )
    assert provider.base_url == "http://env:11434"


def test_base_url_from_manifest_host_port():
    """Manifest host+port build the provider base_url."""
    provider = create_provider({"type": "ollama", "host": "10.0.0.5", "port": 1234})
    assert provider.base_url == "http://10.0.0.5:1234"


def test_base_url_default_when_nothing_set(monkeypatch):
    """With no arg/env/manifest, the provider default base_url is used."""
    monkeypatch.delenv("LAEW_BASE_URL", raising=False)
    provider = create_provider({"type": "ollama"})
    assert provider.base_url == "http://localhost:11434"


# --------------------------------------------------------------------------- #
# Registry seam for future providers
# --------------------------------------------------------------------------- #
def test_registry_names_reflect_registered_providers():
    """registry.names() returns the registered type names."""
    registry = ProviderRegistry()
    registry.register("ollama", build_ollama)
    assert registry.names() == ("ollama",)


def test_registry_create_with_custom_builder():
    """A custom builder can be registered and dispatched (future provider seam)."""
    registry = ProviderRegistry()

    def build_openai(cfg, *, base_url=None, timeout=None):
        return OllamaProvider(base_url=base_url or "http://openai", timeout=timeout or 30)

    registry.register("openai", build_openai)
    provider = registry.create({"type": "openai"}, base_url="http://custom")
    assert provider.base_url == "http://custom"
    assert provider._timeout == 30


def test_registry_custom_builder_receives_config():
    """The custom builder receives the raw provider config mapping."""
    seen = {}

    def build_spy(cfg, **kwargs):
        seen["cfg"] = cfg
        return OllamaProvider()

    registry = ProviderRegistry()
    registry.register("spy", build_spy)
    registry.create({"type": "spy", "model": "test-model"})
    assert seen["cfg"]["model"] == "test-model"


def test_register_override_replaces_builder():
    """Re-registering a type replaces its builder (no duplicate-key error)."""
    registry = ProviderRegistry()
    registry.register("ollama", build_ollama)
    registry.register("ollama", lambda cfg, **kw: OllamaProvider(base_url="http://two"))
    provider = registry.create({"type": "ollama"})
    assert provider.base_url == "http://two"


def test_create_provider_uses_default_registry():
    """create_provider routes through the shared module-level DEFAULT_REGISTRY."""
    assert create_provider.__kwdefaults__["_registry"] is DEFAULT_REGISTRY
