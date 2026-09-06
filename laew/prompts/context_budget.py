"""Context budgeting and token estimation for LAEW prompts."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ContextBudget:
    """
    Context budget allocation for different prompt segments.

    Based on ADR-004: Explicit Context Budgeting
    System + Conversation + RAG + Tools = Total Context Window

    Attributes:
        system: Tokens for system instructions and identity
        conversation: Tokens for conversation history
        rag: Tokens for retrieval-augmented generation context
        tools: Tokens for tool outputs and results
        total: Total available tokens in context window
        reserved: Tokens reserved for model response generation (not shown in manifest)
    """

    system: int = 2000
    conversation: int = 4000
    rag: int = 8000
    tools: int = 4000
    total: int = 18000
    reserved: int = 2000  # For model response generation

    def __post_init__(self):
        """Validate budget consistency."""
        allocated = self.system + self.conversation + self.rag + self.tools
        if allocated > self.total:
            raise ValueError(
                f"Context budget mismatch: allocated ({allocated}) > total ({self.total})"
            )
        if self.reserved > self.total:
            raise ValueError(
                f"Context budget mismatch: reserved ({self.reserved}) > total ({self.total})"
            )

    def available_for_prompt(self) -> int:
        """
        Get tokens available for prompt content (excluding response reserve).

        Returns:
            Available tokens for prompt construction
        """
        return self.total - self.reserved

    def used_percentage(self) -> float:
        """
        Get percentage of context window used by allocated segments.

        Returns:
            Usage percentage (0.0-1.0)
        """
        allocated = self.system + self.conversation + self.rag + self.tools
        return allocated / self.total

    def remaining_for_response(self) -> int:
        """
        Get tokens reserved for model response.

        Returns:
            Reserved tokens for response generation
        """
        return self.reserved

    def is_over_budget(self, estimated_tokens: int) -> bool:
        """
        Check if estimated token usage exceeds budget.

        Args:
            estimated_tokens: Estimated token count

        Returns:
            True if over budget
        """
        return estimated_tokens > self.available_for_prompt()


class TokenEstimator:
    """
    Estimate token count for text using heuristic approximations.

    For production use, this would integrate with a tokenizer
    specific to the model in use (e.g., tiktoken for OpenAI models).
    """

    # Rough approximation: ~4 characters per token for English text
    # This varies by model and tokenizer, but serves as a reasonable estimate
    CHARS_PER_TOKEN = 4.0

    @staticmethod
    def estimate(text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        # Simple heuristic: divide character count by chars per token
        # More sophisticated implementations would use actual tokenizers
        return max(1, len(text) // int(TokenEstimator.CHARS_PER_TOKEN))

    @staticmethod
    def estimate_messages(messages: list[dict]) -> int:
        """
        Estimate tokens for a list of message dictionaries.

        Args:
            messages: List of message dicts with 'content' keys

        Returns:
            Estimated token count
        """
        total_chars = sum(len(msg.get("content", "")) for msg in messages)
        return TokenEstimator.estimate(" ".join(msg.get("content", "") for msg in messages))

    @staticmethod
    def estimate_prompt_sections(sections: list[str]) -> int:
        """
        Estimate tokens for concatenated prompt sections.

        Args:
            sections: List of prompt section strings

        Returns:
            Estimated token count
        """
        full_prompt = "\n\n".join(sections)
        return TokenEstimator.estimate(full_prompt)