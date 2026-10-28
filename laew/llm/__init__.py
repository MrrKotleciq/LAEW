"""LLM provider abstraction layer (ADR-001: Model Abstraction and Roles)."""

from laew.llm.base import LLMProvider, LLMMessage, LLMResponse, LLMError
from laew.llm.llamacpp import LlamaCppProvider
from laew.llm.ollama import OllamaProvider
from laew.llm.registry import (
    ProviderRegistry,
    create_provider,
    get_provider_for_role,
    build_ollama,
    build_llamacpp,
)

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMError",
    "LlamaCppProvider",
    "OllamaProvider",
    "ProviderRegistry",
    "create_provider",
    "get_provider_for_role",
    "build_ollama",
    "build_llamacpp",
]
