"""Agent base classes and configuration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from laew.llm.base import LLMMessage, LLMProvider, MessageRole
from laew.prompts.context_budget import ContextBudget
from laew.prompts.loader import LayeredPrompt
from laew.tools.base import Tool


class AgentRole(str, Enum):
    """Supported agent roles per ADR-001."""

    CHIEF = "chief"
    SPECIALIST = "specialist"
    CRITIC = "critic"


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    backoff_base_ms: int = 1000
    max_backoff_ms: int = 5000


@dataclass
class AgentConfig:
    """
    Configuration for an agent instance.

    Attributes:
        name: Unique identifier for the agent
        role: Agent role (chief, specialist, critic)
        model: Model identifier to use
        temperature: Sampling temperature (0.0 - 1.0)
        max_tokens: Maximum tokens in response
        max_iterations: Maximum tool execution loops before forcing stop
        context_budget: Context budget allocation
        system_prompt: System prompt (LayeredPrompt or raw string)
        retry: Retry configuration for transient failures
        history_path: Path to persist conversation history (None = no persistence)
    """

    name: str = "chief"
    role: AgentRole = AgentRole.CHIEF
    model: str = "llama3.1"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    max_iterations: int = 10
    context_budget: ContextBudget = field(default_factory=ContextBudget)
    system_prompt: Optional[LayeredPrompt | str] = None
    retry: RetryConfig = field(default_factory=RetryConfig)
    history_path: Optional[str] = None


class AgentError(Exception):
    """Exception raised for agent execution errors."""

    def __init__(self, message: str, step: Optional[int] = None):
        super().__init__(message)
        self.step = step


class Agent:
    """
    Core agent representation holding state, tools, and LLM provider.

    Attributes:
        config: Agent configuration
        providers: List of LLM provider implementations (primary + fallbacks)
        tools: Registered tools mapped by name
        history: Conversation history as list of LLMMessage
        _current_provider_index: Index of currently active provider
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: Optional[LLMProvider] = None,
        providers: Optional[List[LLMProvider]] = None,
        tools: Optional[List[Tool]] = None,
    ):
        self.config = config

        # Accept either a single provider or a list of providers (primary + fallbacks).
        # The single `provider` argument is kept for backward compatibility.
        if providers is not None:
            self.providers = list(providers)
        elif provider is not None:
            self.providers = [provider]
        else:
            self.providers = []

        self.tools: Dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register_tool(tool)
        self.history: List[LLMMessage] = []
        self._current_provider_index = 0

        # Load history if persistence is configured
        if self.config.history_path:
            self.load_history()

        # Validate we have at least one provider
        if not self.providers:
            raise ValueError("At least one LLM provider must be specified")

        # Find first available provider
        self._ensure_available_provider()

    def register_tool(self, tool: Tool) -> None:
        """Register a tool available to this agent."""
        self.tools[tool.name] = tool

    def get_system_prompt_text(self) -> str:
        """Render system prompt text."""
        if self.config.system_prompt is None:
            return f"You are {self.config.name}, a helpful engineering assistant."
        if isinstance(self.config.system_prompt, LayeredPrompt):
            return self.config.system_prompt.render()
        return str(self.config.system_prompt)

    def reset_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()

    def add_message(self, role: MessageRole, content: str) -> None:
        """Add a message to history."""
        self.history.append(LLMMessage(role=role, content=content))

    def _ensure_available_provider(self) -> None:
        """Ensure we have an available provider, fallback if necessary."""
        original_index = self._current_provider_index
        while self._current_provider_index < len(self.providers):
            provider = self.providers[self._current_provider_index]
            if provider.is_available():
                return
            self._current_provider_index += 1

        # If we get here, no providers are available
        self._current_provider_index = 0  # Reset to first provider anyway
        raise RuntimeError("No LLM providers are available")

    @property
    def provider(self) -> LLMProvider:
        """Get the currently active LLM provider."""
        self._ensure_available_provider()
        return self.providers[self._current_provider_index]

    def save_history(self) -> None:
        """Persist conversation history to disk."""
        if not self.config.history_path:
            return

        import json
        from pathlib import Path

        history_data = [
            {
                "role": msg.role.value,
                "content": msg.content
            }
            for msg in self.history
        ]

        Path(self.config.history_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.history_path, 'w', encoding='utf-8') as f:
            json.dump(history_data, f, indent=2)

    def load_history(self) -> None:
        """Load conversation history from disk."""
        if not self.config.history_path:
            return

        import json
        from pathlib import Path

        history_path = Path(self.config.history_path)
        if not history_path.exists():
            return

        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                history_data = json.load(f)

            self.history = [
                LLMMessage(
                    role=MessageRole(item["role"]),
                    content=item["content"]
                )
                for item in history_data
            ]
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # If history is corrupted, start fresh but log the error
            print(f"Warning: Could not load conversation history from {self.config.history_path}: {e}")
            self.history = []
