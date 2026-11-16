"""Frozen study acceptance: input isolation, exact replay and guarded text."""
import copy
import importlib.util
import os
from pathlib import Path

import pytest

from laew.eval import evidence_aware_selection as final_selector
from laew.eval.complementary_context_study import load_inputs,offline,read,sha,verify_manifest
from laew.rag.evidence_selection import SelectionConfig


@pytest.fixture(scope='module')
def frozen():
    root=os.environ.get('LAEW_EVIDENCE_AWARE_STUDY_ROOT')
    if not root:
        pytest.skip('Set LAEW_EVIDENCE_AWARE_STUDY_ROOT for immutable acceptance')
    root=Path(root)
    config=copy.deepcopy(read(root/'study-config.json'))
    config['rubric']=str(root/'missing-rubric-intentionally')
    config['datasets']=[]
    with offline():
        data=load_inputs(config,scoring=False)
    return root,data


def test_collection_inputs_replay_without_any_reference_files(frozen):
    root,data=frozen
    assert len(data['traces'])==180 and len(data['questions'])==60
    assert not {'rubric','atoms','families','historical'} & set(data)
    for name in ('initial','r1'):
        for split in ('pilot','all'):
            delivery=root/f'{name}-{split}-delivery'
            verify_manifest(delivery,'integrity.json',sha(delivery/'integrity.json'))
            provenance=read(delivery/'provenance.json')
            assert not provenance['labels_read'] and not provenance['rubric_read'] and not provenance['answers_read']
            assert provenance['network_calls']==provenance['embedding_calls']==provenance['generation_calls']==0


def test_initial_and_final_all_question_selections_replay_exactly(frozen):
    root,data=frozen
    spec=importlib.util.spec_from_file_location('initial_query_role_selector',root/'versions/initial/evidence_aware_selection.py')
    initial=importlib.util.module_from_spec(spec);spec.loader.exec_module(initial)
    for name,selector in [('initial',initial),('r1',final_selector)]:
        rows=read(root/f'{name}-all-delivery/selection-traces.json')
        assert len(rows)==240
        for trace in rows:
            if not trace['arm'].endswith(selector.VERSION):continue
            pool=data['pools'][trace['question_id'],trace['baseline_arm']]
            query=data['questions'][trace['question_id']]['text']
            with offline():
                results,context=selector.select_evidence_scopes({'global':pool},SelectionConfig(policy='ranked_fill',budget=1000),query)
            result=results['global']
            assert result.context==trace['context'] and context==trace['enclosing_context']
            assert [(c.chunk_id,c.text) for c,_ in result.chunks]==[(c['id'],c['text']) for c in trace['selected']]
        all_by={(r['question_id'],r['arm']):r for r in rows}
        for trace in read(root/f'{name}-pilot-delivery/selection-traces.json'):
            assert trace['context']==all_by[trace['question_id'],trace['arm']]['context']


def test_whole_bodies_attribution_native_scores_and_budgets_are_immutable(frozen):
    root,data=frozen
    originals={(t['question_id'],t['arm']):t for t in data['traces']}
    for name in ('initial','r1'):
        for trace in read(root/f'{name}-all-delivery/selection-traces.json'):
            native={c['id']:c for c in originals[trace['question_id'],trace['baseline_arm']]['raw']}
            assert all(c==native[c['id']] for c in trace['selected'])
            assert (len(trace['context'])+3)//4<=1000
            assert (len(trace['enclosing_context'])+3)//4<=8000


def test_refined_guard_preserves_exact_protected_surface_clauses(frozen):
    root,data=frozen
    originals={(t['question_id'],t['arm']):t for t in data['traces']}
    count=0
    for trace in read(root/'r1-all-delivery/selection-traces.json'):
        if not trace['arm'].endswith(final_selector.VERSION):continue
        baseline=originals[trace['question_id'],trace['baseline_arm']]
        pool=data['pools'][trace['question_id'],trace['baseline_arm']]
        profile=final_selector.profile_candidates(data['questions'][trace['question_id']]['text'],pool)
        by={p['id']:p for p in profile['candidates']}
        raw={c.chunk.chunk_id:c.chunk for c in pool}
        selected=[raw[c['id']] for c in trace['selected']]
        for c in baseline['selected']:
            p=by[c['id']]
            associated=p['roles'] or len(p['query_features'])>=2 or p['identities']
            if associated and not p['identity_conflict']:
                chunk=raw[c['id']]
                for clause in final_selector.risk_clauses(chunk.text):
                    assert any(s.file_path==chunk.file_path and clause in s.text for s in selected)
                    count+=1
    assert count>0


def test_positive_denominators_and_all_paired_losses_are_retained(frozen):
    root,_=frozen
    for name in ('initial','r1'):
        scores=root/f'{name}-all-score'
        verify_manifest(scores,'integrity.json',sha(scores/'integrity.json'))
        rows=read(scores/'per-question.json')
        pairs=read(scores/'paired.json')
        assert len(rows)==420 and len(pairs)==240
        by={(r['question_id'],r['arm']):r for r in rows}
        for pair in pairs:
            before=by[pair['question_id'],pair['baseline']]['support']['selected']
            after=by[pair['question_id'],pair['experimental']]['support']['selected']
            assert set(pair['requirement_losses'])=={rid for rid in before if before[rid] and not after[rid]}
        for arm in ('B','C'):
            assert sum(r['stages']['selected']['positive_recall'] is not None for r in rows if r['arm']==arm)==48
