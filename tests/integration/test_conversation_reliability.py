"""Small, offline probes of conversation routing and recall assessment."""
from types import SimpleNamespace

import pytest

from laew.knowledge.routing import assess_memory, resolve_turn, route_sources
from laew.llm.base import MessageRole


def user(text):
    return SimpleNamespace(role=MessageRole.USER, content=text)


@pytest.mark.parametrize("followup", ["A co jeszcze?", "Sprawdz dokladniej.", "What else?"])
def test_continuation_uses_recent_user_topic(followup):
    history = [user("Opisz moje środowisko lokalnych modeli AI.")]
    route, query, bound = resolve_turn(followup, history, in_project=False)
    assert bound and route.memory and "środowisko" in query


def test_topic_change_does_not_reuse_old_topic():
    history = [user("Opisz moje środowisko lokalnych modeli AI."), user("Napisz życzenia urodzinowe.")]
    route, query, bound = resolve_turn("A co jeszcze?", history, in_project=False)
    assert not bound and not route.memory and query == "A co jeszcze?"


def test_possessive_typo_still_considers_memory():
    decision = route_sources("Opisz moeje srodowisko AI", in_project=False)
    assert decision.memory and decision.scopes == ("global",)


def test_conflicting_prose_is_not_a_concrete_candidate():
    status, reason, _ = assess_memory(
        "Jakie miasto chciałbym odwiedzić?", "Jakie miasto chciałbym odwiedzić?",
        {"status": "completed", "prepared": 2},
        [{"content": "Użytkownik chciałby odwiedzić Kioto."},
         {"content": "Użytkownik chciałby odwiedzić Oslo."}],
    )
    assert status == "unverified" and "concrete" not in reason


def test_natural_language_fact_is_not_treated_as_proven_complete():
    status, reason, needs_search = assess_memory(
        "Jakie miasto chciałbym odwiedzić?", "Jakie miasto chciałbym odwiedzić?",
        {"status": "completed", "prepared": 1},
        [{"content": "Użytkownik chciałby odwiedzić Kioto."}],
    )
    assert status == "unverified" and not needs_search and "concrete" in reason
