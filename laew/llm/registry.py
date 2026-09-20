"""LLM provider registry and factory (Milestone 11: Production Hardening).

The registry is the provider-selection seam, shared by the CLI and the
multi-agent coordinator.  Adding a future provider is additive: implement
an ``LLMProvider`` subclass and register a builder.  Only ``"ollama"`` is
registered now (YAGNI).
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from laew.llm.base import LLMError, LLMProvider
from laew.llm.ollama import OllamaProvider

# --------------------------------------------------------------------------- #
# Builder type: (cfg, *, base_url, timeout) → LLMProvider
# --------------------------------------------------------------------------- #

Builder = Callable[..., LLMProvider]


# --------------------------------------------------------------------------- #
# Built-in builders
# --------------------------------------------------------------------------- #

def build_ollama(
    cfg: dict,
    *,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
) -> OllamaProvider:
    """Create an :class:`OllamaProvider` from *cfg* and resolved overrides.

    Parameters are expected to have been resolved by the caller (env, manifest,
    CLI args) before reaching this builder.  ``None`` means *use provider
    default*.
    """
    return OllamaProvider(
        base_url=base_url or "http://localhost:11434",
        timeout=timeout or 120,
    )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #

class ProviderRegistry:
    """Type-keyed registry of provider builders.

    The *type* string comes from the manifest ``agent.llm.providers[].type``
    field and is used as the dispatch key.
    """

    def __init__(self) -> None:
        self._builders: dict[str, Builder] = {}

    # -- public API -------------------------------------------------------- #

    def register(self, provider_type: str, builder: Builder) -> None:
        """Register (or replace) a builder for *provider_type*."""
        self._builders[provider_type] = builder

    def create(
        self,
        cfg: dict,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> LLMProvider:
        """Dispatch on ``cfg["type"]`` and build the provider.

        Config precedence (resolved here, *before* calling the builder):
        - ``base_url``: explicit arg > ``LAEW_BASE_URL`` env > manifest
          ``host``/``port`` > ``None`` (builder default).
        - ``timeout``: explicit arg > ``LAEW_TIMEOUT`` env > manifest
          ``timeout`` > ``None`` (builder default).

        Raises:
            LLMError: with code ``UNSUPPORTED_PROVIDER`` when the type is
                unknown or missing.
        """
        provider_type = cfg.get("type")

        if not provider_type:
            supported = ", ".join(sorted(self._builders)) or "(none)"
            raise LLMError(
                f"Provider config must include a 'type' field. Supported: {supported}",
                code="UNSUPPORTED_PROVIDER",
            )

        builder = self._builders.get(provider_type)
        if builder is None:
            supported = ", ".join(sorted(self._builders))
            raise LLMError(
                f"Unsupported provider type: '{provider_type}'. Supported: {supported}",
                code="UNSUPPORTED_PROVIDER",
            )

        resolved_timeout = self._resolve_timeout(cfg, timeout)
        resolved_base_url = self._resolve_base_url(cfg, base_url)

        return builder(cfg, base_url=resolved_base_url, timeout=resolved_timeout)

    def names(self) -> tuple[str, ...]:
        """Return the registered type names in sorted order."""
        return tuple(sorted(self._builders))

    # -- private helpers --------------------------------------------------- #

    @staticmethod
    def _resolve_timeout(cfg: dict, timeout: Optional[int]) -> Optional[int]:
        if timeout is not None:
            return timeout
        env = os.environ.get("LAEW_TIMEOUT")
        if env is not None:
            return int(env)
        manifest_timeout = cfg.get("timeout")
        if manifest_timeout is not None:
            return int(manifest_timeout)
        return None  # let the builder use its own default

    @staticmethod
    def _resolve_base_url(cfg: dict, base_url: Optional[str]) -> Optional[str]:
        if base_url is not None:
            return base_url
        env = os.environ.get("LAEW_BASE_URL")
        if env is not None:
            return env
        host = cfg.get("host")
        if host is not None:
            port = cfg.get("port")
            if port is not None:
                return f"http://{host}:{port}"
            return f"http://{host}"
        return None  # let the builder use its own default

    # -- role-based provider selection ---------------------------------------- #

    def get_provider_for_role(
        self,
        role: str,
        manifest: dict,
        *,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> LLMProvider:
        """Get a provider for the given *role* by trying the list of provider names
        in the manifest's ``agent.llm.roles[role]`` in order.

        Raises LLMError if no provider can be built for the role.
        """
        roles_cfg = manifest.get("agent", {}).get("llm", {}).get("roles", {})
        provider_names = roles_cfg.get(role)
        if not provider_names:
            raise LLMError(
                f"No provider list found for role '{role}' in manifest.",
                code="NO_PROVIDER_FOR_ROLE",
            )

        providers_cfg = manifest.get("agent", {}).get("llm", {}).get("providers", [])
        provider_by_name = {p.get("name"): p for p in providers_cfg if p.get("name")}

        last_error = None
        for name in provider_names:
            cfg = provider_by_name.get(name)
            if not cfg:
                last_error = LLMError(
                    f"Provider '{name}' not found in manifest for role '{role}'.",
                    code="PROVIDER_NOT_FOUND",
                )
                continue

            try:
                return self.create(cfg, base_url=base_url, timeout=timeout)
            except LLMError as e:
                last_error = e
                # Try the next provider in the list
                continue

        # If we got here, all providers for the role failed.
        raise LLMError(
            f"Failed to build any provider for role '{role}'. Last error: {last_error}",
            code="ALL_PROVIDERS_FAILED",
        ) from last_error


# --------------------------------------------------------------------------- #
# Default (module-level) registry
# --------------------------------------------------------------------------- #

DEFAULT_REGISTRY = ProviderRegistry()
DEFAULT_REGISTRY.register("ollama", build_ollama)


# --------------------------------------------------------------------------- #
# Public convenience factory
# --------------------------------------------------------------------------- #

def create_provider(
    cfg: dict,
    *,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    _registry: ProviderRegistry = DEFAULT_REGISTRY,
) -> LLMProvider:
    """Create a provider from *cfg* using the default registry.

    This is the main entry-point for CLI and multi-agent code.
    Keyword arguments override values from env vars and the manifest.
    """
    return _registry.create(cfg, base_url=base_url, timeout=timeout)


def get_provider_for_role(
    role: str,
    manifest: dict,
    *,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    _registry: ProviderRegistry = DEFAULT_REGISTRY,
) -> LLMProvider:
    """Get a provider for *role* using the default registry."""
    return _registry.get_provider_for_role(role, manifest, base_url=base_url, timeout=timeout)
