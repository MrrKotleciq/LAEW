"""Manifest-selection integration tests for the llama.cpp adapters (Milestone 17).

These drive the **real** config-selection code paths (no mocking of the HTTP
layer):

- ``build_embedding_service`` reads ``models.roles.embedding.type`` and dispatches
  to the Ollama or llama.cpp embedding backend.
- Chat provider selection via ``agent.llm.roles.primary`` +
  ``agent.llm.providers`` (the registry fallback chain).
- ``DEFAULT_REGISTRY.register("llama.cpp", build_llamacpp)`` -> ``build_llamacpp``.

They verify the headline invariant from the plan: chat selection and embedding
selection read **disjoint** config trees, so switching chat to llama.cpp does not
change the embedding provider and vice versa.  The default manifest is left
unchanged (Ollama chat + Ollama ``bge-m3:latest`` embedding).
"""

from pathlib import Path

import yaml

from laew.llm.llamacpp import LlamaCppProvider
from laew.llm.ollama import OllamaProvider
from laew.llm.registry import DEFAULT_REGISTRY, build_llamacpp, get_provider_for_role
from laew.rag.embedding import OllamaEmbedding
from laew.rag.llamacpp import LlamaCppEmbedding, build_llamacpp_embedding
from laew.runtime import build_embedding_service

MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "manifests" / "SYSTEM_MANIFEST.yaml"


# ---------------------------------------------------------------------------
# Embedding selection: models.roles.embedding.type
# ---------------------------------------------------------------------------


def _embedding_manifest(
    *,
    rtype: str = "ollama",
    model_name: str = "bge-m3:latest",
    target_dimensions: int = 1024,
    base_url: str | None = None,
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


def test_embedding_default_manifest_builds_ollama():
    """The default manifest (no type) resolves to the Ollama embedding backend.

    Loaded from the real manifest so the Ollama defaults are preserved.
    """
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    section = manifest["models"]["roles"]["embedding"]
    assert "type" not in section

    service = build_embedding_service(manifest)

    assert isinstance(service, OllamaEmbedding)
    assert service.model == "bge-m3:latest"


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
    embedding_type: str = "ollama",
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
                    "model_name": "bge-m3:latest",
                    "target_dimensions": 1024,
                }
            }
        },
    }


def _ollama_chat_provider(name="ollama_primary", model="qwen2.5-coder:7b"):
    return {
        "name": name,
        "type": "ollama",
        "host": "localhost",
        "port": 11434,
        "model": model,
    }


def test_chat_default_builds_ollama_provider():
    """The default manifest resolves primary chat to an Ollama provider."""
    manifest = _chat_manifest(
        primary=["ollama_primary", "ollama_fallback"],
        providers=[_ollama_chat_provider(), _ollama_chat_provider("ollama_fallback")],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"


def test_chat_llamacpp_first_with_ollama_fallback():
    """A llama.cpp entry prepended to primary is tried first, with Ollama
    fallback preserved; the first that builds wins."""
    manifest = _chat_manifest(
        primary=["llamacpp_primary", "ollama_primary", "ollama_fallback"],
        providers=[
            _ollama_chat_provider(),
            _ollama_chat_provider("ollama_fallback"),
            {"name": "llamacpp_primary", "type": "llama.cpp", "model": "gpt-oss-20b-q4", "host": "127.0.0.1", "port": 8080},
        ],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, LlamaCppProvider)
    assert provider.base_url == "http://127.0.0.1:8080/v1"
    assert provider.model == "gpt-oss-20b-q4"


def test_chat_falls_back_to_ollama_when_first_unavailable():
    """When the first provider in primary is unavailable, the chain falls to
    the next entry.

    A provider name listed in the role but absent from ``agents.llm.providers``
    raises ``PROVIDER_NOT_FOUND`` during selection, so the chain moves on to the
    next name and builds the Ollama provider.  (The llama.cpp builder is lazy —
    it connects only on use, so an unreachable server does not fail selection;
    this exercises the fallback chain a builder failure would trigger.)
    """
    manifest = _chat_manifest(
        primary=["llamacpp_primary", "ollama_primary"],
        providers=[_ollama_chat_provider()],
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"


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
    """Switching chat to llama.cpp leaves the embedding provider as Ollama.

    The two selections read disjoint config trees: chat uses
    ``agent.llm.roles.primary`` + ``agent.llm.providers``; embedding uses
    ``models.roles.embedding.type``.
    """
    manifest = _chat_manifest(
        primary=["llamacpp_primary", "ollama_primary"],
        providers=[
            {"name": "llamacpp_primary", "type": "llama.cpp", "model": "gpt-oss-20b-q4", "host": "127.0.0.1", "port": 8080},
            _ollama_chat_provider(),
        ],
        embedding_type="ollama",
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)
    service = build_embedding_service(manifest)

    assert isinstance(provider, LlamaCppProvider)
    assert isinstance(service, OllamaEmbedding)


def test_embedding_llamacpp_does_not_change_chat():
    """Switching the embedding to llama.cpp leaves chat as Ollama.

    Embedding selection reads ``models.roles.embedding`` — the same tree the
    runtime uses for ``build_embedding_service`` — independent of chat.
    """
    manifest = _chat_manifest(
        primary=["ollama_primary", "ollama_fallback"],
        providers=[_ollama_chat_provider(), _ollama_chat_provider("ollama_fallback")],
        embedding_type="llamacpp",
    )

    provider = get_provider_for_role("primary", manifest, _registry=DEFAULT_REGISTRY)
    service = build_embedding_service(manifest)

    assert isinstance(provider, OllamaProvider)
    assert isinstance(service, LlamaCppEmbedding)
