"""Exact diagnostic optimization, provenance gates and frozen-run acceptance."""
import hashlib
from itertools import combinations
import json
import os
from pathlib import Path
import random
import sqlite3

import numpy as np
import pytest

from laew.eval import retrieval_budget_diagnostics as study


def fixture():
    text = 'Parameter identity. Enable it. Retain ancestors. Warning applies.'
    atoms = {
        'identity': dict(id='identity', source_id='s', start=0, end=19),
        'enable': dict(id='enable', source_id='s', start=20, end=30),
        'chain': dict(id='chain', source_id='s', start=31, end=48),
        'warning': dict(id='warning', source_id='s', start=49, end=len(text)),
    }
    def req(rid, proofs, category='essential', when=None):
        return dict(id=rid, category=category, when=when or {}, safety_critical=False,
                    contextual=False, proofs=proofs, rationale=rid)
    family = dict(conditions={'advice': None}, positive_recall_applicable=True,
        requirements=[req('config', [['identity','enable']]), req('ancestry', [['chain']]),
                      req('safety', [['warning']], 'conditional', {'advice':True})],
        methods=[dict(id='minimum', required=['config','ancestry'], conditions={'advice':False})])
    def chunk(cid, start, end):
        return dict(id=cid, source_id='s', source_ranges=[(start,end)], text=text[start:end])
    candidates = [chunk('first',0,12),chunk('second',12,30),chunk('chain',31,48),chunk('all',0,len(text))]
    return family, atoms, candidates, {'s':text}


def test_exact_dp_matches_exhaustive_for_random_joint_proof_cells():
    rng=random.Random(72139)
    for _ in range(30):
        masks=[rng.randrange(1<<10) for _ in range(9)]
        costs=[rng.randrange(1,400) for _ in masks]
        exhaustive={}
        for subset in range(1<<len(masks)):
            mask=study.sum_masks(masks[i] for i in range(len(masks)) if subset & (1<<i))
            cost=sum(costs[i] for i in range(len(masks)) if subset & (1<<i))
            exhaustive[mask]=min(exhaustive.get(mask,(10**9,0)),(cost,subset))
        assert study.exact_states(masks,costs)==exhaustive


def test_oracle_combines_partial_atom_carriers_and_proves_minimum_cost():
    family,atoms,candidates,texts=fixture()
    result=study.oracle_diagnostic(family,atoms,candidates,texts,[100,100,100,5000],budget=100)
    assert result['complete'] and result['coverage']==1
    assert result['witness_indices']==[0,1,2]
    assert result['min_complete_chars']==314  # Bodies/attribution costs + two separators.
    assert result['min_complete_tokens']==79
    assert result['complete_registered_proof_bundles']==1
    assert 'warning' not in result['unavailable_atom_ids']


def test_available_complete_evidence_can_be_mathematically_over_budget():
    family,atoms,candidates,texts=fixture()
    result=study.oracle_diagnostic(family,atoms,candidates,texts,[1500,1500,1500,5000])
    assert not result['complete'] and result['coverage']==.5
    assert result['min_complete_chars']==4514
    assert result['min_complete_tokens']==1129
    assert result['complete_methods_available']==['minimum']


def test_conditional_warning_is_required_for_its_method():
    family,atoms,candidates,texts=fixture()
    family['methods'][0]['conditions']['advice']=True
    result=study.oracle_diagnostic(family,atoms,candidates[:3],texts,[100,100,100])
    assert not result['complete'] and result['coverage']==pytest.approx(2/3)
    assert result['min_complete_tokens'] is None
    family['methods'][0]['conditions']['advice']=None
    unresolved=study.oracle_diagnostic(family,atoms,candidates,texts,[100]*4)
    assert not unresolved['complete']


def test_coherent_alternative_methods_cannot_mix_partial_solutions():
    family,atoms,candidates,texts=fixture()
    family['requirements'][1]['category']='alternative'
    family['requirements'].append(dict(id='alternate',category='alternative',safety_critical=False,
        contextual=False,when={},proofs=[['warning']],rationale='Separate valid method'))
    family['methods'].append(dict(id='alternate',required=['config','alternate'],conditions={'advice':False}))
    result=study.oracle_diagnostic(family,atoms,[candidates[0],candidates[2]],texts,[100,100])
    assert result['coverage']==.5 and not result['complete']


def test_missing_proof_is_not_fabricated_or_reconstructed():
    family,atoms,candidates,texts=fixture()
    result=study.oracle_diagnostic(family,atoms,[candidates[2]],texts,[100])
    assert result['coverage']==.5 and result['min_complete_tokens'] is None
    assert result['complete_registered_proof_bundles']==0


def test_restricted_component_cannot_earn_positive_credit():
    family,atoms,candidates,texts=fixture()
    regions=[dict(source_id='s',component_ranges=[dict(start=20,end=30)],related_context_ranges=[])]
    result=study.oracle_diagnostic(family,atoms,candidates,texts,[100]*4,regions=regions)
    assert not result['complete'] and 'enable' in result['unavailable_atom_ids']


@pytest.mark.parametrize('args,expected',[
    ((True,True,True,1,1),'complete'),
    ((True,False,True,1,1),'selection_lost'),
    ((True,False,False,1,.5),'budget_infeasible'),
    ((False,False,False,.5,.5),'retrieval_missing'),
    ((False,False,False,.75,.5),'mixed'),
    ((False,False,False,.5,.5,True),'unresolved'),
])
def test_classification_requires_candidate_and_budget_evidence(args,expected):
    assert study.classify(*args)==expected


def test_mixed_classification_includes_retrieval_plus_recoverable_selection_loss():
    assert study.classify(False,False,False,.5,.5,actual_recall=0)=='mixed'


def test_readonly_cache_never_embeds_on_missing_key(tmp_path):
    path=tmp_path/'cache.sqlite3'
    model={'id':'saved','meta':{'n_embd':1024}}
    identity=hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()
    key=hashlib.sha256((identity+'\0known').encode()).hexdigest()
    with sqlite3.connect(path) as conn:
        conn.execute('create table vectors (key text primary key, vector blob)')
        conn.execute('insert into vectors values (?,?)',(key,np.ones(1024,dtype=np.float32).tobytes()))
    before=study.sha(path)
    cache=study.FrozenVectors(path,dict(model_catalog=model,model_identity_sha256=identity,dimensions=1024))
    assert cache.get('known').shape==(1024,)
    with pytest.raises(RuntimeError,match='EMBEDDING STOP GATE'):
        cache.get('missing')
    cache.close()
    assert before==study.sha(path)


def test_exact_budget_boundary_counts_separators_before_rounding():
    family,atoms,candidates,texts=fixture()
    result=study.oracle_diagnostic(family,atoms,candidates[:3],texts,[1300,1300,1386])
    assert result['complete'] and result['witness_tokens']==1000
    too_large=study.oracle_diagnostic(family,atoms,candidates[:3],texts,[1300,1300,1387])
    assert not too_large['complete'] and too_large['min_complete_tokens']==1001


@pytest.fixture(scope='module')
def frozen():
    root=os.environ.get('LAEW_RETRIEVAL_BUDGET_ROOT')
    if not root:
        pytest.skip('Set LAEW_RETRIEVAL_BUDGET_ROOT for full frozen artifact acceptance')
    root=Path(root)
    for name in ('retrieval','analysis-v3'):
        study.verify_manifest(root/name,'integrity.json',study.sha(root/name/'integrity.json'))
    return root,study.read(root/'analysis-v3/per-question.json')


def test_frozen_all_60_questions_and_all_four_configurations_are_reported(frozen):
    root,rows=frozen
    assert len(rows)==240 and len({r['question_id'] for r in rows})==60
    for cfg in ('B/K10','B/K20','C/K10','C/K20'):
        rr=[r for r in rows if r['configuration']==cfg]
        assert len(rr)==60 and sum(r['answerable'] for r in rr)==48
        assert all(r['classification']=='unresolved' for r in rr if not r['answerable'])
        assert all(r['scores']['selected']['positive_recall'] is None for r in rr if not r['answerable'])


def test_frozen_rankings_scores_and_vector_identity_are_verified(frozen):
    root,_=frozen
    verification=study.read(root/'retrieval/retrieval-verification.json')
    reviewed=study.read(root/'analysis-v3/ranking-tie-review.json')
    assert verification['discrepancies']==1
    assert {r['question_id'] for r in reviewed}=={'P01-de','S15-de'}
    checks=study.read(root/'retrieval/ranking-checks.json')
    assert len(checks)==120
    assert all(c['historical_k10_order_equal'] and c['ranking_repeat_equal'] for c in checks)
    assert all(c['historical_k20_prefix_equal'] for c in checks if c['question_id']!='S15-de' or c['arm']!='C')
    assert max(c['max_historical_score_delta'] for c in checks)<=2e-6


def test_frozen_exact_oracle_is_between_actual_and_candidate_and_k_is_monotonic(frozen):
    _,rows=frozen
    by={(r['question_id'],r['arm'],r['k']):r for r in rows}
    for r in rows:
        assert r['oracle']['optimality']=='exact'
        assert r['oracle']['witness_tokens']<=1000
        if not r['answerable']:
            continue
        assert r['scores']['selected']['positive_recall']<=r['oracle']['coverage']+1e-12
        assert r['oracle']['coverage']<=r['scores']['eligible']['positive_recall']+1e-12
        if r['k']==10:
            assert r['oracle']['coverage']<=by[r['question_id'],r['arm'],20]['oracle']['coverage']+1e-12
