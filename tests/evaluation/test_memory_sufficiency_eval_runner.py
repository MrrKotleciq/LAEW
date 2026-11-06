"""Checks for the isolated evaluation harness, not model accuracy."""
import json
from pathlib import Path

import pytest

from laew.eval.horizon_strategies import candidate_entailment, RecordedAssessment, Replay
from laew.eval.memory_sufficiency_eval import DATASET, evaluate, local_provider


def test_validation_corpus_and_isolated_baseline():
    cases = json.loads(DATASET.read_text(encoding='utf-8-sig'))
    assert len(cases) == len({case['id'] for case in cases}) >= 20
    assert {case['needs_rag'] for case in cases} == {False, True}
    results = evaluate(cases, {'active': (None, ''), 'dedicated': (None, '')})
    baseline = results['heuristic']
    assert baseline['status'] == 'completed'
    assert len(baseline['cases']) == len(cases)
    assert baseline['metrics']['assessment_calls'] == 0
    assert results['active']['status'] == results['dedicated']['status'] == 'not_run'
    assert all(row['end_to_end_ms'] >= 0 and row['retrieval_ms'] >= 0 for row in baseline['cases'])


@pytest.mark.parametrize('url', ['https://example.com', 'http://example.com', 'http://user@localhost:8080'])
def test_evaluator_refuses_nonlocal_providers(url):
    with pytest.raises(ValueError):
        local_provider('test', url)


@pytest.mark.parametrize("question,contents,expected", [
    ("Where is my recorder?", ["My recorder is inside the cabinet."],
     "My recorder is inside the cabinet."),
    ("Gdzie jest moja latarka?", ["Moja latarka jest w szafie."], "Moja latarka jest w szafie."),
    ("Where is my recorder and who has it?", ["My recorder is inside the cabinet."], None),
    ("Where is my recorder?", ["His recorder is inside the cabinet."], None),
    ("Where is my recorder?", ["My recorder is inside the cabinet if it was returned."], None),
    ("Where is my recorder?", ["My recorder is not in the cabinet."], None),
    ("Where is my recorder?", ["My recorder is in the cabinet.", "My recorder is on the table."], None),
])
def test_candidate_builder_limits_scope_without_generating_answers(question, contents, expected):
    pair = candidate_entailment(question, [{"content": content} for content in contents])
    if expected is None:
        assert pair is None
    else:
        assert pair == {"premise": contents[0], "hypothesis": expected}


def test_hypothetical_gate_replays_only_the_exact_recorded_pair(monkeypatch):
    record = RecordedAssessment(candidate_entailment)
    result = {"status": "completed", "entailment_score": 0.99}
    monkeypatch.setattr(record.assessor, "assess", lambda *_: result)
    question = "Where is my recorder?"
    memories = [{"content": "My recorder is inside the cabinet."}]
    assert "sufficient" not in record.assess(question, memories)
    replay = Replay(record)
    assert replay.assess(question, memories)["sufficient"] is True
    assert replay.assess(question, [])["sufficient"] is False
