"""Context budgeting and token estimation for LAEW prompts."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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

    def __post_init__(self) -> None:
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
    def estimate(text: str, chars_per_token: Optional[float] = None) -> int:
        """
        Estimate token count for text.

        Args:
            text: Input text
            chars_per_token: Override the ``4.0`` heuristic with a calibrated
                ratio (e.g. from ``TokenCalibrator``); ``None`` uses the default.

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        ratio = TokenEstimator.CHARS_PER_TOKEN if chars_per_token is None else chars_per_token
        if ratio <= 0:
            raise ValueError("chars_per_token must be > 0")

        # Simple heuristic: divide character count by chars per token
        # More sophisticated implementations would use actual tokenizers
        return max(1, int(len(text) // ratio))

    @staticmethod
    def estimate_messages(
        messages: list[dict[str, Any]], chars_per_token: Optional[float] = None
    ) -> int:
        """
        Estimate tokens for a list of message dictionaries.

        Args:
            messages: List of message dicts with 'content' keys
            chars_per_token: Optional calibrated ratio override

        Returns:
            Estimated token count
        """
        combined = " ".join(msg.get("content", "") for msg in messages)
        return TokenEstimator.estimate(combined, chars_per_token)

    @staticmethod
    def estimate_prompt_sections(
        sections: list[str], chars_per_token: Optional[float] = None
    ) -> int:
        """
        Estimate tokens for concatenated prompt sections.

        Args:
            sections: List of prompt section strings
            chars_per_token: Optional calibrated ratio override

        Returns:
            Estimated token count
        """
        full_prompt = "\n\n".join(sections)
        return TokenEstimator.estimate(full_prompt, chars_per_token)


@dataclass
class CalibrationSample:
    """
    A single (observed length, actual tokens) measurement for calibration.

    Attributes:
        char_count: Character length of the measured text
        actual_tokens: Token count reported by the real tokenizer
    """

    char_count: int
    actual_tokens: int


class TokenCalibrator:
    """
    Fit a ``chars_per_token`` ratio from observed (length, token) pairs.

    Used to tune ``TokenEstimator`` against a real model tokenizer (e.g. via
    Ollama's ``/api/tokenize``) so budget enforcement uses a data-driven ratio
    rather than the fixed 4.0 heuristic.  ``best_chars_per_token()`` returns the
    mean observed ratio across recorded samples; it raises ``RuntimeError``
    before any sample has been recorded.
    """

    def __init__(self) -> None:
        self._samples: List[CalibrationSample] = []

    @staticmethod
    def _ratio(sample: CalibrationSample) -> float:
        return sample.char_count / sample.actual_tokens

    def record(self, char_count: int, actual_tokens: int) -> None:
        """
        Record one (length, tokens) measurement.

        Args:
            char_count: Character length of the measured text
            actual_tokens: Actual token count for the text (must be > 0)

        Raises:
            ValueError: If ``actual_tokens`` is not a positive integer
        """
        if actual_tokens <= 0:
            raise ValueError("actual_tokens must be > 0")
        if char_count < 0:
            raise ValueError("char_count must be >= 0")
        self._samples.append(CalibrationSample(char_count, actual_tokens))

    def best_chars_per_token(self) -> float:
        """
        Best-fit characters-per-token ratio from recorded samples.

        Returns:
            Mean observed ratio, clamped to a sane minimum of 1.0

        Raises:
            RuntimeError: No samples have been recorded yet
        """
        if not self._samples:
            raise RuntimeError("TokenCalibrator has no samples; call record() first")
        mean = sum(self._ratio(s) for s in self._samples) / len(self._samples)
        return max(1.0, mean)

    @property
    def sample_count(self) -> int:
        """Number of recorded samples."""
        return len(self._samples)