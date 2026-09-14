"""Tests for the multi-agent communication message protocol (ADR-018)."""

import dataclasses

import pytest

from laew.multiagent.message import AgentMessage, MessageKind


class TestMessageKind:
    def test_kind_values(self):
        """All message kinds have the expected string values."""
        assert MessageKind.TASK.value == "task"
        assert MessageKind.RESULT.value == "result"
        assert MessageKind.CONTEXT.value == "context"
        assert MessageKind.ERROR.value == "error"
        assert MessageKind.SYNTHESIS.value == "synthesis"
        assert MessageKind.QUERY.value == "query"

    def test_kind_is_str_enum(self):
        """MessageKind is JSON-serializable via its string value."""
        assert MessageKind("task") is MessageKind.TASK
        assert MessageKind.TASK == "task"


class TestAgentMessage:
    def test_creates_message_with_defaults(self):
        """A basic agent message defaults recipient and ids to None."""
        msg = AgentMessage(
            kind=MessageKind.TASK,
            content="Do the work",
            sender="chief",
        )
        assert msg.recipient is None
        assert msg.correlation_id is None
        assert msg.parent_id is None
        assert msg.metadata == {}

    def test_message_is_immutable(self):
        """AgentMessage should be a frozen dataclass."""
        msg = AgentMessage(
            kind=MessageKind.RESULT,
            content="done",
            sender="researcher",
        )
        assert dataclasses.is_dataclass(msg)
        assert msg.__dataclass_params__.frozen

    def test_to_dict_roundtrip(self):
        """to_dict -> from_dict preserves all fields."""
        original = AgentMessage(
            kind=MessageKind.CONTEXT,
            content="Found a precedent",
            sender="researcher",
            recipient="architect",
            correlation_id="research-1",
            parent_id="task-0",
            metadata={"deliverable": "finding"},
        )
        data = original.to_dict()
        restored = AgentMessage.from_dict(data)

        assert restored == original
        assert restored.kind is MessageKind.CONTEXT

    def test_to_dict_uses_string_kind(self):
        """Serialized kind is the plain enum value, JSON-safe."""
        msg = AgentMessage(
            kind=MessageKind.SYNTHESIS,
            content="final",
            sender="chief",
        )
        assert msg.to_dict()["kind"] == "synthesis"

    def test_metadata_copied_not_shared(self):
        """Serialized metadata is a copy; mutating it does not affect the message."""
        msg = AgentMessage(
            kind=MessageKind.RESULT,
            content="done",
            sender="reviewer",
            metadata={"score": 3},
        )
        data = msg.to_dict()
        data["metadata"]["score"] = 99
        assert msg.metadata["score"] == 3

    def test_from_dict_rejects_missing_kind(self):
        """Deserialization fails cleanly when required fields are absent."""
        with pytest.raises(ValueError):
            AgentMessage.from_dict({"content": "no kind", "sender": "chief"})

    def test_from_dict_rejects_bad_kind(self):
        """Deserialization fails when the kind value is unknown."""
        with pytest.raises(ValueError):
            AgentMessage.from_dict(
                {
                    "kind": "not-a-kind",
                    "content": "x",
                    "sender": "chief",
                }
            )

    def test_str_is_compact(self):
        """__str__ gives a compact trace line with sender -> recipient."""
        msg = AgentMessage(
            kind=MessageKind.RESULT,
            content="Completed",
            sender="reviewer",
            recipient="chief",
        )
        text = str(msg)
        assert "result" in text
        assert "reviewer -> chief" in text
        assert "Completed" in text

    def test_broadcast_string_uses_star(self):
        """A message without a recipient renders as a broadcast (*)."""
        msg = AgentMessage(
            kind=MessageKind.CONTEXT,
            content="note",
            sender="debugger",
        )
        assert "*" in str(msg)