"""Base LLM provider interface (ADR-001: Model Abstraction and Roles)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class LLMError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(f"{code}: {message}" if code else message)


class MessageRole(str, Enum):
    """Message roles for conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class LLMMessage:
    """
    A single message in a conversation.

    Attributes:
        role: Message role (system, user, assistant)
        content: Message text content
    """

    role: MessageRole
    content: str

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary format."""
        return {"role": self.role.value, "content": self.content}


@dataclass
class LLMResponse:
    """
    Response from LLM inference.

    Attributes:
        content: Generated text content
        model: Model name that generated the response
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total tokens used
        finish_reason: Reason inference stopped (e.g., 'stop', 'length')
    """

    content: str
    model: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    finish_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "content": self.content,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
        }


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers (ADR-001).

    Providers implement model inference for different backends:
    - Ollama (local models)
    - OpenAI API
    - Anthropic API
    - etc.

    All providers must implement the same interface to ensure
    model-agnostic operation.
    """

    @abstractmethod
    def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> LLMResponse:
        """
        Generate a completion from messages.

        Args:
            messages: Conversation history
            model: Model name/identifier
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content and metadata

        Raises:
            LLMError: If generation fails
        """

    @abstractmethod
    def list_models(self) -> list[str]:
        """
        List available models.

        Returns:
            List of model names

        Raises:
            LLMError: If listing fails
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if provider is available and healthy.

        Returns:
            True if provider can accept requests
        """

    def create_message(self, role: MessageRole, content: str) -> LLMMessage:
        """
        Helper to create a message.

        Args:
            role: Message role
            content: Message content

        Returns:
            LLMMessage instance
        """
        return LLMMessage(role=role, content=content)
