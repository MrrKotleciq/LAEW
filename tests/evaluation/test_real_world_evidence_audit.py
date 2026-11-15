"""Evaluation diagnostics and generator/scoring separation regressions."""
import copy
import hashlib

import pytest

from laew.eval.real_world_evidence_audit import diagnose, refine_label, visible_fraction
from laew.eval.real_world_answer_plan import prepare, serialize


def fixture_data():
    text = 'Required. Unrelated.'
    spans = {'p': dict(source_id='manual-v1', start=0, end=len(text))}
    label = dict(positive_evidence_recall_applicable=True,
                 required_answer_facts=[dict(id='F1', evidence_alternatives=[['p']])],
                 minimal_sufficient_evidence_sets=[['p']])
    refinements = {'F1/p': dict(
        origin='agent', rationale='Only first sentence establishes this fact.',
        normalized_sha256=hashlib.sha256(text.encode()).hexdigest(),
        segments=[dict(start=0, end=9, text_sha256=hashlib.sha256(b'Required.').hexdigest())])}
    return text, spans, label, refinements


def test_partial_is_not_full_semantic_credit_and_ranges_are_unioned():
    text, spans, label, _ = fixture_data()
    fraction = visible_fraction(spans['p'], {'manual-v1': [(0, 5), (3, 9)]}, {'manual-v1': text})
    assert fraction == 9 / 19
    result = diagnose(label, spans, {'manual-v1': text}, {'manual-v1': [(0, 9)]})
    assert result['diagnostic']['fact_recall'] == result['original']['fact_recall'] == 0
    assert result['partial_spans']['F1'][0]['fractions']['p'] == fraction


def test_reviewed_atom_diagnostic_preserves_inputs_and_original_score():
    text, spans, label, refinements = fixture_data()
    before = copy.deepcopy((spans, label, refinements))
    result = diagnose(label, spans, {'manual-v1': text}, {'manual-v1': [(0, 9)]}, refinements)
    assert result['original']['complete'] is False
    assert result['diagnostic']['complete'] is True
    assert (spans, label, refinements) == before


@pytest.mark.parametrize('failure', ['version', 'excerpt', 'bounds', 'empty', 'unused'])
def test_bad_refinements_fail_closed(failure):
    text, spans, label, refinements = fixture_data()
    spec = refinements['F1/p']
    if failure == 'version':
        spec['normalized_sha256'] = '0' * 64
    elif failure == 'excerpt':
        spec['segments'][0]['text_sha256'] = '0' * 64
    elif failure == 'bounds':
        spec['segments'][0]['end'] = len(text) + 1
    elif failure == 'empty':
        spec['segments'] = []
    else:
        refinements['F1/nonexistent'] = spec
    with pytest.raises(ValueError):
        refine_label(label, spans, {'manual-v1': text}, refinements)


def test_source_identity_and_conjunctive_segments_are_required():
    text, spans, label, refinements = fixture_data()
    refinements['F1/p']['segments'].append(dict(
        start=10, end=len(text), text_sha256=hashlib.sha256(text[10:].encode()).hexdigest()))
    result = diagnose(label, spans, {'manual-v1': text}, {'manual-v1': [(0, 9)]}, refinements)
    assert result['diagnostic']['fact_recall'] == 0
    assert visible_fraction(spans['p'], {'manual-v2': [(0, len(text))]}, {'manual-v1': text}) == 0


def test_unsupported_diagnostics_remain_na():
    label = dict(positive_evidence_recall_applicable=False, required_answer_facts=[],
                 minimal_sufficient_evidence_sets=[])
    result = diagnose(label, {}, {}, {})
    assert result['diagnostic']['complete'] is None
    assert result['partial_spans'] == {}


def test_refined_parent_can_be_shared_by_multiple_sufficient_alternatives():
    text, spans, label, refinements = fixture_data()
    spans.update({s: dict(source_id=s, start=0, end=1) for s in ('q', 'r')})
    label['required_answer_facts'][0]['evidence_alternatives'] = [['p', 'q'], ['p', 'r']]
    label['minimal_sufficient_evidence_sets'] = [['p', 'q'], ['p', 'r']]
    result = diagnose(label, spans, {'manual-v1': text, 'q': 'x', 'r': 'x'},
                      {'manual-v1': [(0, 9)], 'q': [(0, 1)]}, refinements)
    assert result['diagnostic']['complete'] is True
    assert result['original']['complete'] is False


def test_refinements_do_not_mix_coherent_alternative_sets():
    spans = {s: dict(source_id=s, start=0, end=1) for s in 'abcd'}
    label = dict(positive_evidence_recall_applicable=True,
                 required_answer_facts=[dict(id='F1', evidence_alternatives=[['a'], ['c']]),
                                        dict(id='F2', evidence_alternatives=[['b'], ['d']])],
                 minimal_sufficient_evidence_sets=[['a', 'b'], ['c', 'd']])
    result = diagnose(label, spans, {s: 'x' for s in spans}, {'a': [(0, 1)], 'd': [(0, 1)]})
    assert result['diagnostic']['fact_recall'] == .5


def pilot_inputs():
    questions, traces = [], []
    for family in ('P01', 'P02', 'P03', 'P04'):
        for language in ('de', 'en', 'pl'):
            qid = family + '-' + language
            questions.append(dict(id=qid, family_id=family, language=language,
                                  text='Public question ' + qid, split='pilot'))
            traces.extend(dict(question_id=qid, family_id=family, language=language,
                               split='pilot', arm=arm, enclosing_context='Public source ' + arm)
                          for arm in 'ABC')
    return questions, traces


def test_36_requests_counterbalanced_and_exact_real_payloads():
    questions, traces = pilot_inputs()
    rows = prepare(questions, traces)
    assert len(rows) == 36
    assert len({(r['question_id'], r['arm']) for r in rows}) == 36
    for position in range(3):
        assert {a: sum(r['arm'] == a for r in rows[position::3]) for a in 'ABC'} == dict(A=4, B=4, C=4)
    assert rows == prepare(questions, traces)
    for row in rows:
        p = row['payload']
        assert p['model'] == 'gpt-5.6-luna' and p['tools'] == []
        assert p['store'] is False and p['stream'] is True
        assert p['input'] == [{'role': 'user', 'content': 'Public question ' + row['question_id']}]
        assert 'Project documentation language' not in p['instructions']


@pytest.mark.parametrize('failure', ['gold', 'missing', 'duplicate', 'wrong_language'])
def test_generator_rejects_label_leakage_and_context_identity_failures(failure):
    questions, traces = pilot_inputs()
    if failure == 'gold':
        questions[0]['required_answer_facts'] = ['must never reach the generator']
    elif failure == 'missing':
        traces.pop()
    elif failure == 'duplicate':
        traces.append(traces[0])
    else:
        traces[0]['language'] = 'pl'
    with pytest.raises(ValueError):
        prepare(questions, traces)


def test_serializer_preserves_context_verbatim_without_network():
    context = 'Relevant Global Knowledge:\n[manual.md > Warning]\nNever infer image content.'
    payload = serialize('Question?', context)
    assert payload['instructions'].endswith(context)
    assert 'temperature' not in payload and 'max_output_tokens' not in payload
