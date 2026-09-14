"""Agent communication protocol for the LAEW multi-agent runtime.

Defines a single, model-agnostic message envelope used for all
inter-agent communication (ADR-018). Messages travel between a
sender and an optional recipient (``None`` = broadcast), and carry a
kind plus a ``correlation_id`` so that task/result message chains can
be traced back to the subtask that produced them.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MessageKind(str, Enum):
    """Categories of messages exchanged between agents."""

    TASK = "task"              # A delegated subtask (chief -> specialist)
    RESULT = "result"          # A completed subtask deliverable (specialist -> chief)
    CONTEXT = "context"        # Shared-context contribution
    ERROR = "error"            # A failed delegation or synthesis
    SYNTHESIS = "synthesis"    # Final chief-merged response
    QUERY = "query"            # A question between agents (unused reserve)


@dataclass(frozen=True)
class AgentMessage:
    """An immutable message in the multi-agent communication protocol.

    Attributes:
        kind: Message category (TASK, RESULT, CONTEXT, ERROR, SYNTHESIS)
        content: Text payload of the message
        sender: Name/role of the sending agent
        recipient: Name of the intended recipient (None = broadcast)
        correlation_id: Identifier tying together a task/result message chain
        parent_id: Identifier of the message this one answers (if any)
        metadata: Extra structured fields (e.g. tool results, error codes)
    """

    kind: MessageKind
    content: str
    sender: str
    recipient: Optional[str] = None
    correlation_id: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dictionary (JSON-safe)."""
        return {
            "kind": self.kind.value,
            "content": self.content,
            "sender": self.sender,
            "recipient": self.recipient,
            "correlation_id": self.correlation_id,
            "parent_id": self.parent_id,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """Deserialize from a plain dictionary produced by ``to_dict``.

        Raises:
            ValueError: If required fields are missing or malformed.
        """
        try:
            return cls(
                kind=MessageKind(data["kind"]),
                content=data["content"],
                sender=data["sender"],
                recipient=data.get("recipient"),
                correlation_id=data.get("correlation_id"),
                parent_id=data.get("parent_id"),
                metadata=data.get("metadata", {}),
            )
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Invalid AgentMessage payload: {exc}")

    def __str__(self) -> str:
        """Compact one-line representation for logging."""
        recipient = self.recipient or "*"
        return f"[{self.kind.value}] {self.sender} -> {recipient}: {self.content}"