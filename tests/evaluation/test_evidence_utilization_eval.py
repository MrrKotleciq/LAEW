"""Check that source ablations preserve the rest of the captured input."""
import pytest

from laew.eval.evidence_utilization_eval import replay_input
from laew.llm.base import LLMMessage, MessageRole


MEMORY = "Relevant Long-Term Memory:\nMemory excerpt"
KNOWLEDGE = "Relevant Global Knowledge:\nGlobal excerpt"


@pytest.mark.parametrize("variant,expected", [
    ("memory_only", MEMORY),
    ("global_only", KNOWLEDGE),
    ("global_then_memory", KNOWLEDGE + "\n\n" + MEMORY),
])
def test_replay_changes_only_evidence_appendix(variant, expected):
    system = LLMMessage(MessageRole.SYSTEM, "Chief instructions\n\n" + MEMORY + "\n\n" + KNOWLEDGE)
    question = LLMMessage(MessageRole.USER, "Synthetic question")
    result = replay_input([system, question], MEMORY, KNOWLEDGE, variant)
    assert result[0].content == "Chief instructions\n\n" + expected
    assert result[1] is question
    assert system.content.endswith(KNOWLEDGE)


def test_replay_refuses_a_prompt_without_the_original_evidence_blocks():
    messages = [LLMMessage(MessageRole.SYSTEM, "Unexpected context")]
    with pytest.raises(ValueError, match="expected two evidence blocks"):
        replay_input(messages, MEMORY, KNOWLEDGE, "memory_only")
