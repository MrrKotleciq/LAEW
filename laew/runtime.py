"""Shared runtime composition helpers for the LAEW CLI and testing console.

Centralizes configuration resolution and object building so that the one-shot
CLI and the interactive console dispatch through the same code path (DRY):

- Provider selection from the manifest (session > env > manifest > default).
- Terminal allowlist extraction.
- Model-name resolution against installed models.
- Tool-suite construction honouring workspace security.

This module is deliberately small and pure; keep it free of argparse, REPL,
and I/O orchestration so both entry points share it without leaking concerns.
"""

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

from laew.llm.base import LLMError, LLMProvider
from laew.prompts.context_budget import ContextBudget
from laew.rag.embedding import EmbeddingService
from laew.rag.config import resolve_knowledge_root
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline
from laew.rag.rag_tool import RagTool
from laew.security.path_resolver import PathResolver
from laew.llm.registry import create_provider, get_provider_for_role
from laew.prompts.context_budget import ContextBudget
from laew.tools import (
    FilesystemTool,
    GitTool,
    TerminalTool,
    WebTool,
)


class _UnavailableEmbeddingService(EmbeddingService):
    """Keep chat available while making a missing RAG setup fail on retrieval."""

    def __init__(self, reason: str):
        self.reason = reason

    def embed(self, text: str) -> list[float]:
        raise RuntimeError(self.reason)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError(self.reason)

    @property
    def dimensions(self) -> int:
        raise RuntimeError(self.reason)


def provider_cfg_from_manifest(
    manifest: dict, provider_type: Optional[str] = None
) -> dict:
    """
    Extract provider configuration from a manifest for the provider factory.

    Args:
        manifest: Loaded manifest dictionary
        provider_type: If specified, filter providers by this type; otherwise
            use the first provider

    Returns:
        Provider configuration dictionary, or ``{"type": "ollama"}`` when the
        manifest declares no providers.
    """
    providers_cfg = (
        manifest.get("agent", {}).get("llm", {}).get("providers", [])
    )

    if not providers_cfg:
        return {"type": "ollama"}

    if provider_type is None:
        # Use first provider if no specific type requested
        return providers_cfg[0]

    # Find provider matching the requested type
    for provider in providers_cfg:
        if provider.get("type") == provider_type:
            return provider

    # If not found, fall back to first provider (will raise appropriate error in factory)
    return providers_cfg[0] if providers_cfg else {"type": "ollama"}


def terminal_allowlist_from_manifest(manifest: dict) -> Optional[list]:
    """
    Extract the terminal command allowlist declared in a manifest.

    Returns None when the manifest declares no terminal allowlist, in which
    case callers keep ``TerminalTool``'s built-in default allowlist.
    """
    categories = manifest.get("tools", {}).get("categories", {})
    allowlist = categories.get("terminal", {}).get("allowlist")
    return list(allowlist) if allowlist else None


def context_budget_from_manifest(manifest: dict) -> Optional["ContextBudget"]:
    """
    Build a :class:`ContextBudget` from the manifest's primary model role.

    Reads ``models.roles.primary.context_budget`` (system/conversation/rag/
    tools/total).  Returns ``None`` when the manifest declares no budget, so
    callers fall back to ``AgentConfig``'s default budget.
    """
    from laew.prompts.context_budget import ContextBudget

    section = (
        manifest.get("models", {})
        .get("roles", {})
        .get("primary", {})
        .get("context_budget")
    )
    if not section:
        return None

    return ContextBudget(
        system=int(section.get("system", 2000)),
        conversation=int(section.get("conversation", 4000)),
        rag=int(section.get("rag", 8000)),
        tools=int(section.get("tools", 4000)),
        total=int(section.get("total", 18000)),
    )


def resolve_model_name(
    cli_model: Optional[str],
    manifest_model: Optional[str],
    provider: LLMProvider,
) -> Optional[str]:
    """
    Resolve the model to use for a session.

    An explicit CLI/session ``--model`` always wins. Otherwise the requested
    model comes from the manifest primary provider; if that model is not
    installed, fall back to a close match from the same family. If nothing
    matches, use a sensible default with a notice.

    Returns:
        The resolved model name, or None if no model is specified.
    """
    requested: Optional[str] = cli_model or manifest_model

    # Explicit choice: trust it and let Ollama report a missing model.
    if cli_model:
        return requested

    try:
        installed = provider.list_models()
    except (ConnectionError, ConnectionRefusedError, TimeoutError, RuntimeError, LLMError) as e:
        logger.debug("Failed to list provider models: %s", e)
        installed = []
    if not installed:
        return requested or "llama3.1"

    # If no manifest model, use the first installed model.
    if requested is None:
        return installed[0]

    # Manifest-specified model is installed: use it as-is.
    if requested in installed:
        return requested

    # Otherwise pick a close family match (e.g. request llama3.1, have llama3.2).
    family = requested.split(":")[0].split(".")
    family_prefix = family[0] if family else requested
    for candidate in installed:
        if candidate.split(":")[0].startswith(family_prefix):
            print(f"[!] '{requested}' not installed; using '{candidate}' instead.")
            return candidate

    # No close match: use the first installed model with a notice.
    print(f"[!] '{requested}' not installed; using '{installed[0]}' instead.")
    return installed[0]


def build_provider(
    manifest: dict,
    provider_type: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> LLMProvider:
    """
    Build an LLM provider from a manifest using the shared registry.

    Args:
        manifest: Loaded manifest dictionary
        provider_type: Optional provider ``type`` to select (defaults to the
            primary manifest provider)
        base_url: Optional base-URL override (highest precedence)
        timeout: Optional timeout override in seconds (highest precedence)

    Returns:
        A configured :class:`LLMProvider`.
    """
    cfg = provider_cfg_from_manifest(manifest, provider_type)
    return create_provider(cfg, base_url=base_url, timeout=timeout)


def build_explicit_provider(
    provider_type: str,
    *,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> LLMProvider:
    """Build a provider explicitly requested on the command line.

    Unlike manifest role resolution, this deliberately does not fall back to a
    manifest provider.  It permits registered providers such as ``llama.cpp``
    to be selected without adding a manifest entry, while the registry still
    validates unknown provider types.
    """
    cfg = {"type": provider_type}
    if model:
        cfg["model"] = model
    return create_provider(cfg, base_url=base_url, timeout=timeout)


def resolve_llamacpp_model(
    cli_model: Optional[str], provider: LLMProvider
) -> str:
    """Resolve a llama.cpp model, discovering it from ``/v1/models`` if needed.

    Discovery is intentionally strict: an explicitly selected llama.cpp
    provider must not silently inherit an Ollama model name or fall back to a
    different provider when its server is unavailable.
    """
    if cli_model:
        return cli_model

    endpoint = f"{provider.base_url.rstrip('/')}/models"
    try:
        models = provider.list_models()
    except LLMError as e:
        raise LLMError(
            f"Could not discover a llama.cpp model from {endpoint}: {e.message}. "
            "Check that the llama.cpp server is running and that GET /v1/models is reachable.",
            code=e.code or "MODEL_DISCOVERY_FAILED",
        ) from e

    model = next((item for item in models if isinstance(item, str) and item.strip()), None)
    if not model:
        raise LLMError(
            f"llama.cpp returned no usable model IDs from {endpoint}. "
            "Check the server's GET /v1/models response or pass --model explicitly.",
            code="MODEL_DISCOVERY_FAILED",
        )

    # Keep the adapter's configured model aligned with the discovered server
    # ID as well as passing it to AgentConfig/generate().
    provider.model = model
    return model


def build_provider_for_role(
    manifest: dict,
    role: str,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    _registry: Optional[ProviderRegistry] = None,
) -> LLMProvider:
    """
    Build an LLM provider for the given *role* using the registry's fallback chain.

    The manifest's ``agent.llm.roles[role]`` list gives the ordered provider
    names to try.  The first one that builds successfully is returned.  Raises
    :exc:`LLMError` (``code="ALL_PROVIDERS_FAILED"``) if every option fails.

    Args:
        manifest: Loaded manifest dictionary.
        role: Abstract model role (e.g. ``"primary"``, ``"embedding"``, ``"reviewer"``).
        base_url: Optional base-URL override (highest precedence).
        timeout: Optional timeout override in seconds (highest precedence).
        _registry: Optional provider registry to use (defaults to the global registry).

    Returns:
        A configured :class:`LLMProvider`.
    """
    if _registry is not None:
        return get_provider_for_role(role, manifest, base_url=base_url, timeout=timeout, _registry=_registry)
    return get_provider_for_role(role, manifest, base_url=base_url, timeout=timeout)


def build_embedding_service(
    manifest: dict,
    *,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> "EmbeddingService":
    """
    Build an embedding service from the manifest's ``models.roles.embedding`` role.

    M17 requires the ``llamacpp`` backend so the embedding endpoint remains
    independently configurable from chat.

    Selection is independent of chat: chat is chosen by
    ``agent.llm.roles.primary`` (the provider registry), embedding by
    ``models.roles.embedding.type`` here.  Switching chat has no effect on the
    embedding and vice versa.

    ``models.roles.embedding`` must explicitly declare ``type: "llamacpp"``,
    a llama.cpp embedding model ID, a dedicated ``base_url``, and its vector
    dimensionality. A chat model endpoint is never used as an implicit fallback.

    Args:
        manifest: Loaded manifest dictionary.
        base_url: Optional llama.cpp base-URL override (highest precedence) for
            the ``llamacpp`` backend.
        timeout: Optional timeout override in seconds (highest precedence).

    Returns:
        A configured :class:`EmbeddingService`.
    """
    from laew.rag.llamacpp import build_llamacpp_embedding

    section = (
        manifest.get("models", {})
        .get("roles", {})
        .get("embedding", {})
        or {}
    )
    role_type = section.get("type")
    if role_type != "llamacpp":
        raise ValueError(
            "M17 embeddings require models.roles.embedding.type='llamacpp'; "
            f"got {role_type!r}. Configure a dedicated llama.cpp embeddings server."
        )
    model = section.get("model_name")
    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            "Configure models.roles.embedding.model_name with the model ID "
            "reported by the dedicated llama.cpp embeddings server."
        )
    endpoint = base_url or section.get("base_url")
    if not endpoint:
        raise ValueError(
            "Configure models.roles.embedding.base_url for the dedicated "
            "llama.cpp embeddings server."
        )
    return build_llamacpp_embedding(
        model=model.strip(),
        base_url=endpoint,
        target_dimensions=section.get("target_dimensions"),
        timeout=timeout or section.get("timeout"),
    )


def build_rag_tool(
    manifest: dict,
    *,
    project_root: Optional[Path | str] = None,
    projects_root: Optional[Path | str] = None,
    knowledge_root: Optional[Path | str] = None,
    embedding_service=None,
) -> RagTool:
    """Build the read-only, manifest-configured RAG tool for the Chief Agent."""
    resolver = PathResolver(
        project_root=project_root,
        projects_root=projects_root,
        knowledge_root=knowledge_root,
    )
    scoped_project_root = resolver.project_root
    scoped_knowledge_root = resolve_knowledge_root(
        manifest,
        project_root=scoped_project_root,
        projects_root=resolver.projects_root,
        knowledge_root=resolver.knowledge_root,
    )
    if embedding_service is not None:
        embedding = embedding_service
    else:
        try:
            embedding = build_embedding_service(manifest)
        except (ValueError, LLMError) as e:
            # A dedicated embedding model is a RAG prerequisite, not a chat
            # startup prerequisite. Keep the tool registered and report the
            # configuration error when it is invoked.
            embedding = _UnavailableEmbeddingService(str(e))
    rag_config = manifest.get("rag", {}) or {}
    pipeline_config = rag_config.get("pipeline", {}) or {}
    knowledge_base = KnowledgeBase(
        project_root=str(scoped_project_root),
        knowledge_root=str(scoped_knowledge_root),
        embedding_service=embedding,
        vector_store_config=rag_config.get("vector_store", {}) or {},
        project_source_allowlist=(rag_config.get("project_sources", {}) or {}).get("allowlist"),
    )
    pipeline = RAGPipeline(
        knowledge_base=knowledge_base,
        embedding_service=embedding,
        top_k=int(pipeline_config.get("top_k", 5)),
        max_context_tokens=int(pipeline_config.get("max_context_tokens", 8000)),
        similarity_threshold=float(pipeline_config.get("similarity_threshold", 0.3)),
    )
    return RagTool(
        pipeline=pipeline,
        context_budget=context_budget_from_manifest(manifest) or ContextBudget(),
    )


def build_shared_tools(
    terminal_allowlist: Optional[list] = None,
    *,
    project_root: Optional[Path | str] = None,
    projects_root: Optional[Path | str] = None,
    knowledge_root: Optional[Path | str] = None,
    manifest: Optional[dict] = None,
    rag_embedding_service=None,
) -> List[object]:
    """
    Build the standard shared tool suite for an agent session.

    Args:
        terminal_allowlist: Optional manifest terminal allowlist; ``None`` lets
            ``TerminalTool`` use its built-in default allowlist.
        project_root: Active project root shared by filesystem, Git, and terminal tools.
        projects_root: Trusted Projects directory used by the filesystem path resolver.
        knowledge_root: Shared local knowledge root used by the filesystem path resolver.
        manifest: Runtime manifest. When supplied, adds the on-demand read-only RAG tool.
        rag_embedding_service: Optional embedding implementation, primarily useful for tests.

    Returns:
        The workspace tools, plus read-only RAG when a manifest is supplied.
    """
    resolver = PathResolver(project_root=project_root, projects_root=projects_root, knowledge_root=knowledge_root)
    tools = [
        FilesystemTool(resolver=resolver),
        GitTool(repo_root=project_root),
        TerminalTool(workspace_root=project_root, allowlist=terminal_allowlist),
        WebTool(),
    ]
    if manifest is not None:
        tools.append(build_rag_tool(
            manifest,
            project_root=resolver.project_root,
            projects_root=resolver.projects_root,
            knowledge_root=resolver.knowledge_root,
            embedding_service=rag_embedding_service,
        ))
    return tools
