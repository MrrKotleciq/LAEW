"""Optional immutable-artifact replay; every operation is offline and read-only."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket

import pytest

from laew.eval.scoring_calibration import score_answer, score_evidence
from laew.eval.real_world_retrieval import coverage_of


@pytest.fixture(scope='module')
def saved():
    variables=['LAEW_ANSWER_PILOT_ROOT','LAEW_SCORING_CALIBRATION_ROOT','LAEW_FROZEN_CORPUS_ROOT',
               'LAEW_REAL_WORLD_RETRIEVAL','LAEW_ANSWER_ADJUDICATION_ROOT']
    if not all(os.environ.get(k) for k in variables):
        pytest.skip('Set frozen pilot, rubric, corpus, retrieval and adjudication artifact roots')
    live,calibration,corpus,retrieval,adjudication=[Path(os.environ[k]) for k in variables]
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    old_path=adjudication/'historical/scoring_calibration_v2_1.py'
    assert hashlib.sha256(old_path.read_bytes()).hexdigest()=='b0f7a8bc72645957f084398b8002fc8937c15b5d29014212954cbdf582ac3330'
    module=importlib.util.spec_from_file_location('historical_scorer_for_test',old_path)
    old=importlib.util.module_from_spec(module);module.loader.exec_module(old)
    units=read(corpus/'corpus/source-manifest.json')['source_units']
    texts={u['id']:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for u in units}
    traces={(t['question_id'],t['arm']):t for t in read(retrieval/'run-v2/retrieval-traces.json') if t['split']=='pilot'}
    return dict(old=old,live=live,adjudication=adjudication,read=read,texts=texts,traces=traces,
        rubric=read(calibration/'rubric-v2.1.json'),atoms=read(calibration/'source-atoms-v2.1.json'),
        rows=read(live/'evaluation-v3/agent-review.json')['rows'])


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('Adjudication tests cannot contact a service')
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr('requests.Session.request',forbidden)


def test_same_36_annotations_eliminate_11_conflicts_and_preserve_other_25(saved):
    s=saved;rejected=[]
    for r in s['rows']:
        family=s['rubric']['families'][r['family_id']]
        answer=r['claim_annotations'][0]['quote'];review=copy.deepcopy(r['deterministic_answer_review'])
        coverage=coverage_of(s['traces'][r['question_id'],r['arm']]['selected'])
        args=(family,s['atoms'],s['texts'],coverage,answer,review)
        new=score_answer(*args)
        try:old=s['old'].score_answer(*args)
        except ValueError as exc:
            assert str(exc)=='Chosen method contradicts reviewed applicability'
            rejected.append(r['sequence'])
        else:
            assert old=={k:v for k,v in new.items() if k not in {'condition_trace','condition_review_gaps'}}
        assert new['correctness']=='unresolved'  # Do not invent missing atomic semantic labels.
        assert score_evidence(family,s['atoms'],coverage,s['texts'])==s['old'].score_evidence(family,s['atoms'],coverage,s['texts'])
    assert rejected==[13,22,24,28,29,30,31,32,33,34,36]


def test_scoped_adjudication_preserves_warnings_and_grounding_separation(saved):
    overlay=saved['read'](saved['adjudication']/'results-v3/adjudication-overlay.json')['rows']
    assert len(overlay)==36
    for r in overlay:
        assert r['origin']=='post_result_agent_adjudication' and not r['independent_human_validation']
        result=r['corrected_deterministic_score']['result']
        assert not result['condition_review_gaps']
        if r['sequence'] in {28,32,33}:
            assert 'P04.new_config' in result['critical_missing']
        if r['sequence'] in {22,24}:
            assert 'P03.checksum' not in result['critical_missing']
            assert r['grounding_status']=='unresolved'
        if r['sequence']==18:
            req=next(q for q in r['requirement_reviews'] if q['requirement_id']=='P02.first_layer')
            assert req['status']=='correct' and not req['delivered_proof_present']
            assert 'P02.first_layer' not in result['grounded_required']


def test_comparison_retains_uncertainty_and_unfavorable_b_change(saved):
    summary=saved['read'](saved['adjudication']/'results-v3/summary.json')
    assert summary['applicability_errors_before']==11 and summary['applicability_errors_after']==0
    assert [summary['corrected'][a]['correct_complete'] for a in 'ABC']==[4,5,6]
    assert [summary['corrected'][a]['correct_complete_grounded'] for a in 'ABC']==[3,5,4]
    assert summary['corrected']['B']['fully_grounded_lower']==8
    assert summary['corrected']['B']['fully_grounded_upper']==9
    assert summary['corrected']['A']['support_unresolved']==1
    assert summary['strict_deterministic']['correctness_unresolved']==36
