"""Shared context for the LAEW multi-agent runtime.

Provides a single shared-context store that specialist agents and the
chief agent can publish findings into and read back from (ADR-018).
The store is deliberately simple: immutable text items keyed by name,
with source/provenance so downstream agents can attribute where facts
came from (principle P5, source awareness).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SharedContextItem:
    """A single immutable entry in the shared context.

    Attributes:
        key: Stable identifier for the item (e.g. a deliverable name).
        content: Text content contributed by an agent.
        source: Name/role of the contributing agent.
        created_at: ISO-8601 UTC timestamp of insertion.
    """

    key: str
    content: str
    source: str
    created_at: str

    def __str__(self) -> str:
        return f"[{self.key} from {self.source}] {self.content}"


class SharedContext:
    """Append-only journal of shared findings between agents.

    Ordering follows insertion order so the chief/specialists can rely
    on chronological visibility of accumulated context. Data is kept
    outside any runtime/model state, per principle P2.
    """

    def __init__(self) -> None:
        self._items: List[SharedContextItem] = []
        self._index: Dict[str, List[SharedContextItem]] = {}

    def post(self, key: str, content: str, source: str) -> SharedContextItem:
        """Publish a finding into the shared context.

        Args:
            key: Stable identifier for the finding.
            content: Text content of the finding.
            source: Name/role of the contributing agent.

        Returns:
            The created item.
        """
        item = SharedContextItem(
            key=key,
            content=content.strip(),
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._items.append(item)
        self._index.setdefault(key, []).append(item)
        return item

    def get(self, key: str) -> Optional[SharedContextItem]:
        """Return the most recent item for a key, or None if absent."""
        entries = self._index.get(key)
        return entries[-1] if entries else None

    def all_for(self, key: str) -> List[SharedContextItem]:
        """Return every item recorded under a key (oldest first)."""
        return list(self._index.get(key, []))

    def keys(self) -> List[str]:
        """Return distinct keys in first-insertion order."""
        return list(self._index.keys())

    def __len__(self) -> int:
        """Number of stored items."""
        return len(self._items)

    def render(self, header: str = "Shared context:") -> str:
        """Format the context for injection into an agent prompt.

        Args:
            header: Optional leading line for the rendered block.

        Returns:
            Empty string when no items exist; otherwise a formatted
            block listing each item with its key and source.
        """
        if not self._items:
            return ""
        lines = [header]
        for item in self._items:
            lines.append(f"- [{item.key}] (by {item.source}): {item.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Reset the store to empty."""
        self._items.clear()
        self._index.clear()
