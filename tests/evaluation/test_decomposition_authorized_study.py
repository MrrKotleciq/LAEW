"""Authorized embedding compatibility and immutable retrieval acceptance."""
import os
from pathlib import Path

import pytest

from laew.eval.complementary_context_study import read, sha, verify_manifest
from laew.eval.decomposition_embedding_job import catalog_compatible


def test_catalog_timestamp_drift_does_not_rekey_the_historical_cache():
    old=dict(id='laew-qwen3-embedding',created=1,meta=dict(n_embd=1024,ftype='Q8_0'))
    new=dict(old,created=2)
    result=catalog_compatible(old,new)
    assert result['changed_fields']==['created']
    assert not result['original_cache_rekeyed']
    assert result['original_catalog_identity']!=result['current_catalog_identity']


@pytest.mark.parametrize('change',[
    dict(id='another-model'),dict(meta=dict(n_embd=512,ftype='Q8_0')),
    dict(meta=dict(n_embd=1024,ftype='Q4_0')),
])
def test_model_or_dimension_drift_fails_closed(change):
    old=dict(id='laew-qwen3-embedding',created=1,meta=dict(n_embd=1024,ftype='Q8_0'))
    with pytest.raises(ValueError):
        catalog_compatible(old,dict(old,**change))


@pytest.fixture(scope='module')
def study():
    root=os.environ.get('LAEW_FINE_EVIDENCE_ROOT')
    if not root:
        pytest.skip('Set LAEW_FINE_EVIDENCE_ROOT for authorized study acceptance')
    root=Path(root)
    for name in ('embeddings-authorized','decomposition-retrieval','decomposition-scores'):
        verify_manifest(root/name,'integrity.json',sha(root/name/'integrity.json'))
    return root


def test_exact_approved_embedding_job_and_all_original_controls(study):
    receipt=read(study/'embeddings-authorized/metadata.json')
    assert receipt['inputs']==41 and receipt['requests']==6
    assert not receipt['original_cache_modified'] and not receipt['corpus_reembedded']
    dispatches=read(study/'embeddings-authorized/dispatch-ledger.json')
    assert all(r['status']=='completed' for r in dispatches)
    inputs=[s for r in dispatches for s in r['input_sha256s']]
    assert len(inputs)==len(set(inputs))==41
    controls=read(study/'decomposition-retrieval/controls.json')
    assert len(controls)==240 and all(c['native_equal'] for c in controls)


def test_equal_raw_budgets_dedup_and_complete_all_question_ledgers(study):
    traces=read(study/'decomposition-retrieval/retrieval-traces.json')
    scores=read(study/'decomposition-scores/per-question.json')
    assert len(traces)==len(scores)==360
    for row in traces:
        assert sum(row['allocations'])==row['total_raw_budget']
        assert len({c['id'] for c in row['eligible']})==len(row['eligible'])
        assert all(c['cosine']>=.3 for c in row['eligible'])
        if row['condition'].startswith('equal'):
            assert row['total_raw_budget']==int(row['condition'][5:])


def test_original_only_rows_are_exactly_unchanged_and_reference_labels_cannot_gain(study):
    plans={p['question_id']:p for p in read(study/'decomposition/question-only-plans.json')}
    scores=read(study/'decomposition-scores/per-question.json')
    for row in scores:
        if plans[row['question_id']]['status']=='unsplit':
            assert row['candidate_score']==row['baseline_candidate_score']
            assert not row['gained_requirements'] and not row['lost_requirements']
        if row['answerable']:
            for result in row['extractions'].values():
                if result['complete']:
                    assert row['candidate_score']['complete']


def test_all_new_extraction_witnesses_are_exact_unrestricted_candidate_text(study):
    from laew.eval import source_evidence_oracle as oracle
    config=read(study/'study-config.json')
    units={u['id']:u for u in read(Path(config['corpus'])/'corpus/source-manifest.json')['source_units']}
    texts={sid:(Path(config['corpus'])/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    regions=read(Path(config['corpus'])/'review/r3d/restricted-regions.json')['regions']
    rules=read(study/'scopes-v3/scope-rules.json')
    rubric=read(Path(config['rubric'])/'rubric-v2.1.json')['families']
    traces={(r['question_id'],r['arm'],r['condition']):r for r in read(study/'decomposition-retrieval/retrieval-traces.json')}
    for row in read(study/'decomposition-scores/per-question.json'):
        available=oracle.subtract_regions(oracle.coverage_of(traces[row['question_id'],row['arm'],row['condition']]['eligible']),regions)
        family=rubric[row['family_id']]
        for granularity,result in row['extractions'].items():
            for witness in [result['witness']]+([result['minimum_complete']] if result['minimum_complete'] else []):
                cov=witness['coverage']
                assert oracle.render(cov,texts,units)==witness['rendering']
                assert oracle.ranges_key(cov)==oracle.ranges_key(oracle.subtract_regions(cov,regions))
                assert all(oracle.span_present(dict(source_id=sid,start=a,end=z),available,texts)
                           for sid,ranges in cov.items() for a,z in ranges)
                for req in family['requirements']:
                    if not witness['support'][req['id']] or req.get('contextual'):
                        continue
                    assert any(all(oracle.span_present(dict(source_id=sid,start=a,end=z),cov,texts)
                        for aid in proof for sid,ranges in rules[aid]['ranges'].items()
                        for x,y in ranges for a,z in oracle.expand(texts[sid],x,y,granularity)) for proof in req['proofs'])
