"""End-to-end evaluator contracts, independent of semantic model behavior."""
from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from laew.eval.hierarchical_benchmark import benchmark
from laew.eval.lexical_benchmark import digest, read


def corpus():
    records=[]
    for i in range(18):
        x=1. if i==0 else (.7 if i==17 else .9-i*.001)
        records.append({'id':f'id{i:02}','source':'global','path':'manual.md' if i in (0,17) else f'{i}.md',
                        'text':f'original passage {i}','metadata':{},'embedding':[x,(1-x*x)**.5]})
    q={'id':'test','text':'original fixed question','language':'pl','allowed_scope':'global',
       'no_answer':None,'expected_document_ids':['@knowledge/manual.md'],'relevance':{'@knowledge/manual.md':2},
       'evidence':[{'document_id':'@knowledge/manual.md','passage':'original passage 17'}]}
    original={'dataset_directory':'stress_1036','chunking':{'strategy':'legacy'},'chunks':records,
              'queries':[{'query':q,'embedding':[1.,0.],'index_atom_available':[True]}]}
    grouped=deepcopy(original)
    grouped['dataset_directory']='stress_grouped'
    for r in grouped['chunks']:
        if r['path']!='manual.md':
            r['metadata']['control_original_path']=r['path'];r['path']='all-distractors.md'
    conditions=[original,grouped]
    return {'conditions':conditions,'content_hash':digest(conditions)}


def test_real_chroma_routing_quality_is_separate_from_renderer_and_grouped_layout():
    result=benchmark(corpus(),repeats=1,overall_budget=200)
    assert result['controls']=={'same_seeds_both_methods':True,'grouped_control_same_native_seed_ids':True}
    rows={(r['dataset'],r['method']):r for r in result['rows']}
    assert not rows['stress_1036','dense']['candidate']['complete_evidence']
    assert rows['stress_1036','hierarchical']['candidate']['complete_evidence']
    assert not rows['stress_grouped','hierarchical']['candidate']['complete_evidence']
    assert all(r['tokens']<=200 and r['allocation_compliant'] and r['adapter_received'] for r in result['rows'])
    assert all(len(ids)<=10 for r in result['rows'] for ids in r['candidate_ids'].values())
    assert all(d['chroma_calls']<=2 for r in result['rows'] for d in r['diagnostics'].values())


def test_modified_cache_fails_before_any_backend_access():
    data=corpus();data['conditions'][0]['chunks'][0]['text']='changed'
    with pytest.raises(ValueError,match='cache changed'):
        benchmark(data,repeats=1)


def test_authored_fixture_freeze_remains_valid():
    root=Path('tests/rag/hierarchical_long_v1')
    freeze=read(root/'FREEZE.json')
    assert 'not independently human judged' in freeze['authorship']
    for relative,sha in freeze['sha256'].items():
        assert hashlib.sha256((root/relative).read_bytes()).hexdigest()==sha
