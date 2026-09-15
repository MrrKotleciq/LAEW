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

from pathlib import Path
from typing import List, Optional

from laew.llm.base import LLMProvider
from laew.llm.registry import create_provider
from laew.tools import (
    FilesystemTool,
    GitTool,
    TerminalTool,
    WebTool,
)


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


def resolve_model_name(
    cli_model: Optional[str],
    manifest_model: Optional[str],
    provider: LLMProvider,
) -> str:
    """
    Resolve the model to use for a session.

    An explicit CLI/session ``--model`` always wins. Otherwise the requested
    model comes from the manifest primary provider; if that model is not
    installed, fall back to a close match from the same family. If nothing
    matches, use a sensible default with a notice.
    """
    requested = cli_model or manifest_model

    # Explicit choice: trust it and let Ollama report a missing model.
    if cli_model:
        return requested

    try:
        installed = provider.list_models()
    except Exception:
        installed = []
    if not installed:
        return requested or "llama3.1"

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


def build_shared_tools(terminal_allowlist: Optional[list] = None) -> List[object]:
    """
    Build the standard shared tool suite for an agent session.

    Args:
        terminal_allowlist: Optional manifest terminal allowlist; ``None`` lets
            ``TerminalTool`` use its built-in default allowlist.

    Returns:
        A list of the four workspace tools (filesystem, git, terminal, web).
    """
    return [
        FilesystemTool(),
        GitTool(),
        TerminalTool(allowlist=terminal_allowlist),
        WebTool(),
    ]