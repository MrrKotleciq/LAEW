"""Manifest-selection integration tests for the llama.cpp adapters (Milestone 17).

These drive the **real** config-selection code paths (no mocking of the HTTP
layer):

- ``build_embedding_service`` reads ``models.roles.embedding.type`` and dispatches
  to the Ollama or llama.cpp embedding backend.
- Chat provider selection via ``agent.llm.roles.primary`` +
  ``agent.llm.providers`` (the registry fallback chain).
- ``DEFAULT_REGISTRY.register("llama.cpp", build_llamacpp)`` -> ``build_llamacpp``.

They verify the headline invariant from the plan: chat selection and embedding
selection read **disjoint** config trees. Embedding requires an explicit
llama.cpp server endpoint and model ID; no Ollama fallback is provided.
"""

from pathlib import Path

import yaml

from laew.llm.llamacpp import LlamaCppProvider
from laew.llm.registry import DEFAULT_REGISTRY, build_llamacpp, get_provider_for_role
from laew.rag.llamacpp import LlamaCppEmbedding, build_llamacpp_embedding
from laew.runtime import build_embedding_service

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "manifests" / "SYSTEM_MANIFEST.yaml"


# ---------------------------------------------------------------------------
# Embedding selection: models.roles.embedding.type
# ---------------------------------------------------------------------------


def _embedding_manifest(
    *,
    rtype: str = "llamacpp",
    model_name: str = "nomic-embed-text",
    target_dimensions: int = 768,
    base_url: str | None = "http://127.0.0.1:8081",
):
    """A manifest whose embedding role selects the given backend."""
    return {
        "models": {
            "roles": {
                "embedding": {
                    "type": rtype,
                    "model_name": model_name,
                    "target_dimensions": target_dimensions,
                    "base_url": base_url,
                }
            }
        }
    }


def test_repository_manifest_selects_the_dedicated_embedding_model_id():
    """The repository config selects the model exposed by its dedicated server."""
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    section = manifest["models"]["roles"]["embedding"]
    assert section["type"] == "llamacpp"
    assert section["base_url"] == "http://127.0.0.1:8081"
    assert section["model_name"] == "laew-qwen3-embedding"
    assert section["target_dimensions"] == 1024
    embedding = build_embedding_service(manifest)
    assert embedding.model == section["model_name"]
    assert embedding.dimensions == section["target_dimensions"]


def test_repository_manifest_selects_llamacpp_chat_without_ollama_fallback():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    llm = manifest["agent"]["llm"]
    assert [provider["type"] for provider in llm["providers"]] == ["llama.cpp"]
    assert llm["roles"]["primary"] == ["llamacpp_primary"]

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)
    assert isinstance(provider, LlamaCppProvider)
    assert provider.base_url == "http://127.0.0.1:8080/v1"


def test_embedding_type_llamacpp_builds_llamacpp():
    """An explicit type: llamacpp resolves to the llama.cpp embedding backend."""
    manifest = _embedding_manifest(
        rtype="llamacpp",
        model_name="nomic-embed-text",
        target_dimensions=512,
        base_url="http://127.0.0.1:8080/v1",
    )

    service = build_embedding_service(manifest)

    assert isinstance(service, LlamaCppEmbedding)
    assert service.model == "nomic-embed-text"
    assert service.base_url == "http://127.0.0.1:8080/v1"
    assert service.target_dimensions == 512


# ---------------------------------------------------------------------------
# Chat selection: agent.llm.roles.primary + providers
# ---------------------------------------------------------------------------


def _chat_manifest(
    *,
    primary: list[str],
    providers: list[dict],
    embedding_type: str = "llamacpp",
):
    """A manifest with the given chat provider names and provider entries."""
    return {
        "agent": {
            "llm": {
                "roles": {"primary": primary},
                "providers": providers,
            }
        },
        "models": {
            "roles": {
                "embedding": {
                    "type": embedding_type,
                    "model_name": "nomic-embed-text",
                    "target_dimensions": 768,
                    "base_url": "http://127.0.0.1:8081",
                }
            }
        },
    }


def _llamacpp_chat_provider(name="llamacpp_primary", model="gpt-oss-20b-q4"):
    return {
        "name": name,
        "type": "llama.cpp",
        "host": "127.0.0.1",
        "port": 8080,
        "model": model,
    }


def test_chat_default_builds_llamacpp_provider():
    """The configured primary chat provider is llama.cpp."""
    manifest = _chat_manifest(
        primary=["llamacpp_primary"],
        providers=[_llamacpp_chat_provider()],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, LlamaCppProvider)
    assert provider.base_url == "http://127.0.0.1:8080/v1"


def test_chat_provider_chain_selects_first_llamacpp_entry():
    """The configured llama.cpp provider is selected before its fallback."""
    manifest = _chat_manifest(
        primary=["llamacpp_primary", "llamacpp_fallback"],
        providers=[
            _llamacpp_chat_provider(),
            _llamacpp_chat_provider("llamacpp_fallback", "fallback-chat"),
        ],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, LlamaCppProvider)
    assert provider.base_url == "http://127.0.0.1:8080/v1"
    assert provider.model == "gpt-oss-20b-q4"


def test_chat_falls_back_to_next_configured_llamacpp_provider():
    """When the first provider in primary is unavailable, the chain falls to
    the next entry.

    A provider name listed in the role but absent from ``agents.llm.providers``
    raises ``PROVIDER_NOT_FOUND`` during selection, so the chain moves on to the
    next name and builds the llama.cpp fallback. (The provider is lazy —
    it connects only on use, so an unreachable server does not fail selection;
    this exercises the fallback chain a builder failure would trigger.)
    """
    manifest = _chat_manifest(
        primary=["missing_provider", "llamacpp_fallback"],
        providers=[_llamacpp_chat_provider("llamacpp_fallback", "fallback-chat")],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, LlamaCppProvider)
    assert provider.model == "fallback-chat"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_default_registry_registers_llamacpp_builder():
    """DEFAULT_REGISTRY exposes the llama.cpp builder under 'llama.cpp'."""
    assert "llama.cpp" in DEFAULT_REGISTRY.names()


def test_build_llamacpp_factory_returns_chat_provider():
    """build_llamacpp(cfg) returns a LlamaCppProvider with a normalized base URL."""
    cfg = {
        "type": "llama.cpp",
        "model": "gpt-oss-20b-q4",
        "base_url": "http://localhost:8080",
    }
    provider = build_llamacpp(cfg)

    assert isinstance(provider, LlamaCppProvider)
    assert provider.model == "gpt-oss-20b-q4"
    assert provider.base_url == "http://localhost:8080/v1"


# ---------------------------------------------------------------------------
# Independence of chat and embedding selection
# ---------------------------------------------------------------------------


def test_chat_llamacpp_does_not_change_embedding():
    """Chat selection does not change the separately configured embedding.

    The two selections read disjoint config trees: chat uses
    ``agent.llm.roles.primary`` + ``agent.llm.providers``; embedding uses
    ``models.roles.embedding.type``.
    """
    manifest = _chat_manifest(
        primary=["llamacpp_primary", "llamacpp_fallback"],
        providers=[
            _llamacpp_chat_provider(),
            _llamacpp_chat_provider("llamacpp_fallback", "fallback-chat"),
        ],
        embedding_type="llamacpp",
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)
    service = build_embedding_service(manifest)

    assert isinstance(provider, LlamaCppProvider)
    assert isinstance(service, LlamaCppEmbedding)


def test_embedding_llamacpp_does_not_change_chat():
    """Embedding selection does not change the llama.cpp chat provider.

    Embedding selection reads ``models.roles.embedding`` — the same tree the
    runtime uses for ``build_embedding_service`` — independent of chat.
    """
    manifest = _chat_manifest(
        primary=["llamacpp_primary"],
        providers=[_llamacpp_chat_provider()],
        embedding_type="llamacpp",
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)
    service = build_embedding_service(manifest)

    assert isinstance(provider, LlamaCppProvider)
    assert isinstance(service, LlamaCppEmbedding)
