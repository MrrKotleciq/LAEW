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
    """

    name: str = "chief"
    role: AgentRole = AgentRole.CHIEF
    model: str = "llama3.1"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    max_iterations: int = 10
    context_budget: ContextBudget = field(default_factory=ContextBudget)
    system_prompt: Optional[LayeredPrompt | str] = None


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
        provider: LLM provider implementation
        tools: Registered tools mapped by name
        history: Conversation history as list of LLMMessage
    """

    def __init__(
        self,
        config: AgentConfig,
        provider: LLMProvider,
        tools: Optional[List[Tool]] = None,
    ):
        self.config = config
        self.provider = provider
        self.tools: Dict[str, Tool] = {}
        if tools:
            for tool in tools:
                self.register_tool(tool)
        self.history: List[LLMMessage] = []

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
