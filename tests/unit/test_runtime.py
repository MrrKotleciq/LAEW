"""Tests for shared runtime composition helpers (laew/runtime.py).

These helpers were moved verbatim out of laew/cli.py so both the one-shot CLI
and the interactive console resolve configuration and build tools through the
same code path. The expectations below mirror the original CLI tests.
"""

from unittest.mock import patch, MagicMock

import pytest

from laew.runtime import (
    build_explicit_provider,
    provider_cfg_from_manifest,
    terminal_allowlist_from_manifest,
    build_shared_tools,
    build_provider,
    build_embedding_service,
    context_budget_from_manifest,
    resolve_model_name,
    resolve_llamacpp_model,
)
from laew.llm.base import LLMError


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


def test_build_shared_tools_adds_project_scoped_rag_tool_when_manifest_supplied(tmp_path):
    project = tmp_path / "Projects" / "LAEW"
    project.mkdir(parents=True)
    vault = tmp_path / "Knowledge"
    vault.mkdir()
    embedding = MagicMock()
    manifest = {
        "memory": {"second_brain": {"path": "@knowledge"}},
        "rag": {"pipeline": {"top_k": 3, "max_context_tokens": 400},
                "vector_store": {"enabled": False},
                "project_sources": {"allowlist": ["README.md", "knowledge/**/*.md"]}},
    }

    tools = build_shared_tools(
        ["python"],
        project_root=project,
        projects_root=project.parent,
        knowledge_root=vault,
        manifest=manifest,
        rag_embedding_service=embedding,
    )

    names = {tool.name for tool in tools}
    assert names == {"FilesystemTool", "GitTool", "TerminalTool", "WebTool", "RagTool"}
    rag = next(tool for tool in tools if tool.name == "RagTool")
    assert rag._pipeline.knowledge_base.project_root == project.resolve()
    assert rag._pipeline.knowledge_base.knowledge_root == vault.resolve()
    assert rag._pipeline.knowledge_base.project_source_allowlist == (
        "README.md", "knowledge/**/*.md"
    )
    assert rag._pipeline.top_k == 3
    assert rag._pipeline.max_context_tokens == 400
    assert rag._context_budget is not None


def test_build_embedding_service_requires_explicit_llamacpp_configuration():
    with pytest.raises(ValueError, match="type='llamacpp'"):
        build_embedding_service({})

    manifest = {"models": {"roles": {"embedding": {
        "type": "llamacpp", "base_url": "http://127.0.0.1:8081",
        "model_name": "embed-model", "target_dimensions": 1024, "timeout": 19,
    }}}}
    service = build_embedding_service(manifest)
    assert service.model == "embed-model"
    assert service.base_url == "http://127.0.0.1:8081/v1"
    assert service.dimensions == 1024
    assert service.timeout == 19


def test_build_embedding_service_does_not_infer_chat_endpoint_or_model():
    manifest = {"models": {"roles": {"embedding": {
        "type": "llamacpp",
    }}}}
    with pytest.raises(ValueError, match="model_name"):
        build_embedding_service(manifest)

    manifest["models"]["roles"]["embedding"]["model_name"] = "dedicated-model"
    manifest["models"]["roles"]["embedding"]["base_url"] = "http://127.0.0.1:8081"
    with pytest.raises(LLMError, match="target_dimensions"):
        build_embedding_service(manifest)


def test_missing_embedding_model_does_not_block_chat_tool_construction(tmp_path):
    project = tmp_path / "project"
    vault = tmp_path / "global"
    project.mkdir()
    vault.mkdir()
    manifest = {
        "memory": {"second_brain": {"path": "@knowledge"}},
        "models": {"roles": {"embedding": {
            "type": "llamacpp", "base_url": "http://127.0.0.1:8081",
            "target_dimensions": 1024,
        }}},
    }
    tools = build_shared_tools(
        project_root=project,
        projects_root=tmp_path,
        knowledge_root=vault,
        manifest=manifest,
    )
    rag = next(tool for tool in tools if tool.name == "RagTool")

    result = rag.execute("query", query="hello", scope="project")

    assert result.success is False
    assert result.error_code == "ERR_RAG_FAILURE"
    assert "model_name" in result.error_message


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


def test_build_explicit_provider_does_not_require_manifest_entry():
    """An explicit provider type is sent directly to the registry."""
    fake = MagicMock()
    with patch("laew.runtime.create_provider", return_value=fake) as factory:
        assert build_explicit_provider(
            "llama.cpp", model="server-model", base_url="http://127.0.0.1:8080", timeout=42
        ) is fake
    factory.assert_called_once_with(
        {"type": "llama.cpp", "model": "server-model"},
        base_url="http://127.0.0.1:8080",
        timeout=42,
    )


def test_resolve_llamacpp_model_discovers_first_server_id():
    provider = MagicMock(base_url="http://127.0.0.1:8080/v1")
    provider.list_models.return_value = ["C:/models/local.gguf"]

    assert resolve_llamacpp_model(None, provider) == "C:/models/local.gguf"
    assert provider.model == "C:/models/local.gguf"


def test_resolve_llamacpp_model_explicit_value_skips_discovery():
    provider = MagicMock()
    assert resolve_llamacpp_model("selected", provider) == "selected"
    provider.list_models.assert_not_called()


def test_resolve_llamacpp_model_reports_unavailable_models_endpoint():
    provider = MagicMock(base_url="http://127.0.0.1:8080/v1")
    provider.list_models.side_effect = LLMError("connection refused", code="CONNECTION_ERROR")

    with pytest.raises(LLMError, match=r"GET /v1/models") as exc_info:
        resolve_llamacpp_model(None, provider)
    assert exc_info.value.code == "CONNECTION_ERROR"


def test_resolve_llamacpp_model_rejects_empty_models_response():
    provider = MagicMock(base_url="http://127.0.0.1:8080/v1")
    provider.list_models.return_value = []

    with pytest.raises(LLMError, match="no usable model IDs") as exc_info:
        resolve_llamacpp_model(None, provider)
    assert exc_info.value.code == "MODEL_DISCOVERY_FAILED"


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


CONTEXT_BUDGET_MANIFEST = {
    "models": {
        "roles": {
            "primary": {
                "context_budget": {
                    "system": 1000,
                    "conversation": 2000,
                    "rag": 3000,
                    "tools": 1500,
                    "total": 8000,
                }
            }
        }
    }
}


def test_context_budget_from_manifest_parses():
    """Full context_budget section is parsed into a ContextBudget."""
    budget = context_budget_from_manifest(CONTEXT_BUDGET_MANIFEST)
    assert budget is not None
    assert budget.system == 1000
    assert budget.conversation == 2000
    assert budget.rag == 3000
    assert budget.tools == 1500
    assert budget.total == 8000
    assert budget.available_for_prompt() == 8000 - budget.reserved


def test_context_budget_from_manifest_returns_none_when_absent():
    """No context_budget section -> None (AgentConfig default is used)."""
    assert context_budget_from_manifest({}) is None
    assert context_budget_from_manifest({"models": {}}) is None
    assert (
        context_budget_from_manifest(
            {"models": {"roles": {"primary": {"model": "qwen2.5-coder:7b"}}}}
        )
        is None
    )


def test_context_budget_from_manifest_applies_defaults():
    """Missing keys fall back to ContextBudget field defaults."""
    budget = context_budget_from_manifest(
        {"models": {"roles": {"primary": {"context_budget": {"total": 20000}}}}}
    )
    assert budget is not None
    assert budget.system == 2000
    assert budget.conversation == 4000
    assert budget.rag == 8000
    assert budget.tools == 4000
    assert budget.total == 20000
