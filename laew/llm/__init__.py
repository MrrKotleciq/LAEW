"""LLM provider abstraction layer (ADR-001: Model Abstraction and Roles)."""

from laew.llm.base import LLMProvider, LLMMessage, LLMResponse, LLMError
from laew.llm.ollama import OllamaProvider
from laew.llm.registry import ProviderRegistry, create_provider, build_ollama

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMError",
    "OllamaProvider",
    "ProviderRegistry",
    "create_provider",
    "build_ollama",
]
