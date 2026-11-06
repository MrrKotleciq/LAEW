"""Bilingual intent probes separate profile lookup from topical similarity."""

import pytest

from laew.knowledge.routing import resolve_turn, route_sources
from laew.llm.base import LLMMessage, MessageRole


@pytest.mark.parametrize("question", [
    "Jakie szkoły i uczelnie ukończyła kierowniczka?",
    "Czy moje narzędzia warto wymienić przed szkoleniem?",
    "Co jest celem szkolenia z komunikacji?",
    "Which degrees and certificates would I need to apply?",
    "How do I configure the tools on my workstation?",
    "Jak skonfigurować narzędzia na moim komputerze?",
    "When is the confirmed university festival in my city?",
    "When is the scheduled delivery for the municipal archive?",
    "Jaki jest zaplanowany termin publicznego przeglądu?",
])
def test_general_and_prospective_questions_skip_automatic_retrieval(question):
    route = route_sources(question, in_project=False)
    assert not route.memory and not route.scopes


@pytest.mark.parametrize("question", [
    "Where did i study before I moved?",
    "Which diplomas have I earned?",
    "What degree am I studying?",
    "Tell me which licenses I hold.",
    "Jaką szkołę ukończyłam?",
    "W jakiej branży pracowałam przed przeprowadzką?",
    "Gdzie studiowalem przed zmianą zawodu?",
    "Czym zajmuję się zawodowo?",
    "Kogo wybrałyśmy na zastępstwo?",
    "Co ustaliliśmy w sprawie wystroju?",
    "Co uznałem, że warto zrobić?",
    "When was I scheduled to speak at the festival?",
    "When is the confirmed date for my appointment at the city library?",
    "Na kiedy przełożono odbiór instrumentu?",
    "What is the address of my workshop?",
])
def test_owned_facts_and_past_actions_still_use_memory(question):
    route = route_sources(question, in_project=False)
    assert route.memory and not route.scopes


def test_public_and_private_schedule_follow_ups_use_the_current_topic():
    for anchor, expected in [
        ("When is the confirmed handover of the props?", True),
        ("When is the confirmed opening of the national film festival?", False),
    ]:
        route, _, bound = resolve_turn(
            "And when was it?", [LLMMessage(MessageRole.USER, anchor)], in_project=False,
        )
        assert route.memory is expected and bound is expected


def test_explicit_memory_selection_overrides_advice_classification():
    route = route_sources("Check Memory. Which certifications should I pursue?", in_project=False)
    assert route.memory
    route = route_sources("Without Memory, which apprenticeship did I choose?", in_project=False)
    assert route.memory_excluded and not route.memory
