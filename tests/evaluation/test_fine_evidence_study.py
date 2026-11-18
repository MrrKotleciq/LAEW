"""Offline feasibility contracts: isolation, provenance and fail-closed scope."""
import ast
import hashlib
import itertools
import json
import os
from pathlib import Path

import pytest

from laew.eval import question_decomposition as decomposition
from laew.eval import source_evidence_oracle as oracle
from laew.eval.complementary_context_study import read, sha, verify_manifest
from laew.eval.fine_evidence_study import PARENT


def example():
    text='Enable X.\n\nKeep 10 days, unless disabled.\n\nNever remove ancestors.'
    ranges=[(0,9),(11,39),(41,len(text))]
    atoms={str(i):dict(id=str(i),source_id='s',start=a,end=z) for i,(a,z) in enumerate(ranges)}
    family=dict(conditions={},positive_recall_applicable=True,
        requirements=[dict(id=str(i),category='essential',when={},safety_critical=True,
                           contextual=False,proofs=[[str(i)]],rationale='test') for i in range(3)],
        methods=[dict(id='all',required=list(atoms),conditions={})])
    candidates=[dict(id='c',source_id='s',source_ranges=[(0,len(text))])]
    units={'s':dict(revision='17',normalized_sha256=hashlib.sha256(text.encode()).hexdigest())}
    rules={aid:dict(ranges={'s':[(a['start'],a['end'])]}) for aid,a in atoms.items()}
    return family,atoms,{'s':text},units,candidates,rules


def test_question_mechanism_has_no_imported_label_or_io_surface():
    tree=ast.parse(Path(decomposition.__file__).read_text(encoding='utf-8'))
    imports=[n.module if isinstance(n,ast.ImportFrom) else n.names[0].name
             for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    assert set(imports)=={'__future__','re'}
    assert not any(isinstance(n,ast.Name) and n.id in {'open','eval','exec','__import__'} for n in ast.walk(tree))


@pytest.mark.parametrize('question',[
    'On version 17, what files must I keep, and how should I restore?',
    'Dla wersji 17: jakie pliki zachować, i jak je odtworzyć?',
    'Für Version 17: welche Dateien behalten, und wie wiederherstellen?',
])
def test_scope_versions_conditions_and_negation_stay_verbatim(question):
    result=decomposition.decompose(question)
    assert result['status']=='split'
    assert result['queries'][0]==question
    assert all(q.startswith(question+'\nRequested part: ') for q in result['queries'][1:])


def test_unsplittable_question_uses_only_the_original_query():
    assert decomposition.decompose('How do I repair it?')['queries']==['How do I repair it?']


def test_focus_cap_groups_contiguous_requests_without_dropping_them():
    q='What first; how second; which third; when fourth; why fifth; where sixth?'
    result=decomposition.decompose(q)
    assert len(result['foci'])==4
    for word in ('first','second','third','fourth','fifth','sixth'):
        assert word in '; '.join(result['foci'])


@pytest.mark.parametrize('queries,total',list(itertools.product(range(1,6),(10,20))))
def test_equal_raw_budget_is_exact_and_does_not_backfill(queries,total):
    counts=decomposition.search_allocations(queries,total)
    assert sum(counts)==total and min(counts)>0 and max(counts)-min(counts)<=1


def test_round_robin_dedup_keeps_distinct_chunk_sources_and_threshold():
    result=decomposition.merge_ranked([
        [dict(id='same',cosine=.7),dict(id='other-language-copy',cosine=.6)],
        [dict(id='same',cosine=.8),dict(id='low',cosine=.29)],
    ],4)
    assert [c['id'] for c in result['candidates']]==['same','other-language-copy']
    assert len(result['duplicates'])==len(result['filtered'])==1


def test_source_gap_is_visible_and_revision_hash_are_fully_costed():
    family,atoms,texts,units,candidates,rules=example()
    rendering=oracle.render({'s':[(0,9),(41,len(texts['s']))]},texts,units)
    assert '[separate source passage]' in rendering['context']
    assert units['s']['normalized_sha256'] in rendering['context']
    assert '[chars 0:9]' in rendering['context']
    assert rendering['tokens']==(len(rendering['context'])+3)//4
    assert rendering['body_chars']+rendering['attribution_and_separator_chars']==rendering['chars']


def test_required_neighbor_cannot_be_read_from_outside_the_candidate_pool():
    family,atoms,texts,units,candidates,rules=example()
    candidates[0]['source_ranges']=[(0,9),(11,39)]
    rules['0']['ranges']['s'].append((41,len(texts['s'])))
    result=oracle.solve(family,atoms,texts,units,candidates,[],rules,'minimal-span')
    assert not result['complete'] and result['min_complete_tokens'] is None
    assert result['rejected']


def test_restricted_prerequisite_never_earns_evidence_credit():
    family,atoms,texts,units,candidates,rules=example()
    regions=[dict(source_id='s',component_ranges=[dict(start=41,end=len(texts['s']))],related_context_ranges=[])]
    result=oracle.solve(family,atoms,texts,units,candidates,regions,rules,'minimal-span')
    assert not result['complete'] and not result['witness']['support']['2']


def test_proof_only_floor_is_separate_from_coherent_attributed_witness():
    family,atoms,texts,units,candidates,rules=example()
    floor=oracle.solve(family,atoms,texts,units,candidates,[],rules,'minimal-span',floor=True)
    coherent=oracle.solve(family,atoms,texts,units,candidates,[],rules,'minimal-span')
    assert floor['min_complete_tokens']<coherent['min_complete_tokens']
    assert 'NOT coherent' in floor['status']


def test_incidental_atom_presence_cannot_bypass_its_mandatory_scope():
    family,atoms,texts,units,candidates,rules=example()
    # A packet for 1 incidentally includes proof 0; proof 0 requires warning 2.
    rules['0']['ranges']['s'].append((41,len(texts['s'])))
    rules['1']['ranges']['s'].append((0,9))
    result=oracle.solve(family,atoms,texts,units,candidates,[],rules,'minimal-span')
    assert result['incoherent_unions_rejected']>0
    assert result['complete'] and result['witness']['support']['2']


def test_source_version_identity_prevents_wrong_version_proof_credit():
    family,atoms,texts,units,candidates,rules=example()
    candidates[0]['source_id']='other-version'
    result=oracle.solve(family,atoms,texts,units,candidates,[],rules,'minimal-span')
    assert not result['complete'] and result['coverage']==0


def test_paragraph_and_sentence_rules_are_distinct_and_fences_stay_whole():
    text='First fact. Second condition.\n\n```console\ncommand\n\noutput\n```\n'
    assert oracle.expand(text,0,5,'sentence')==[(0,12)]
    assert oracle.expand(text,0,5,'paragraph')==[(0,30)]
    a=text.index('command')
    result=oracle.expand(text,a,a+7,'sentence')
    assert len(result)==1 and text[result[0][0]:result[0][1]].startswith('```console')
    assert text[result[0][0]:result[0][1]].rstrip().endswith('```')


@pytest.fixture(scope='module')
def frozen():
    root=os.environ.get('LAEW_FINE_EVIDENCE_ROOT')
    if not root:
        pytest.skip('Set LAEW_FINE_EVIDENCE_ROOT for sealed-study acceptance')
    root=Path(root)
    for name in ('decomposition','inspection','scopes-v3','analysis-v3'):
        verify_manifest(root/name,'integrity.json',sha(root/name/'integrity.json'))
    return root,read(root/'analysis-v3/per-question.json')


def test_frozen_has_all_60_questions_and_four_configurations(frozen):
    root,rows=frozen
    assert len(rows)==240 and len({r['question_id'] for r in rows})==60
    assert sum(r['answerable'] for r in rows)==192
    for cfg in ('B/K10','B/K20','C/K10','C/K20'):
        assert sum(r['configuration']==cfg for r in rows)==60


def test_every_extraction_witness_is_source_exact_in_pool_and_unrestricted(frozen):
    root,rows=frozen
    config=read(root/'study-config.json')
    corpus=Path(config['corpus'])
    units={u['id']:u for u in read(corpus/'corpus/source-manifest.json')['source_units']}
    texts={sid:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    regions=read(corpus/'review/r3d/restricted-regions.json')['regions']
    traces={(r['question_id'],r['configuration']):r for r in read(PARENT/'retrieval/retrieval-traces.json')}
    for row in rows:
        available=oracle.subtract_regions(oracle.coverage_of(traces[row['question_id'],row['configuration']]['eligible']),regions)
        for e in row['extractions'].values():
            for witness in [e['witness']]+([e['minimum_complete']] if e['minimum_complete'] else []):
                cov=witness['coverage']
                assert all(oracle.span_present(dict(source_id=sid,start=a,end=z),available,texts)
                           for sid,ranges in cov.items() for a,z in ranges)
                assert oracle.ranges_key(cov)==oracle.ranges_key(oracle.subtract_regions(cov,regions))
                assert oracle.render(cov,texts,units)==witness['rendering']
            assert e['witness']['rendering']['tokens']<=1000


def test_query_freeze_and_embedding_gate_are_unchanged(frozen):
    root,_=frozen
    freeze=read(root/'decomposition/freeze.json')
    assert freeze['mechanism_sha256']==sha(decomposition.__file__)
    assert freeze['new_unique_inputs']==41 and freeze['verified_unique_cache_hits']==60
    assert freeze['embedding_calls']==freeze['network_calls']==0
    plans=read(root/'decomposition/question-only-plans.json')
    for p in plans:
        assert decomposition.decompose(p['question'])['queries']==p['queries']


def test_body_floor_never_exceeds_an_admitted_complete_witness(frozen):
    root,rows=frozen
    for row in rows:
        if not row['answerable']:
            continue
        floor=row['proof_body_cost_floor']['min_complete_tokens']
        for result in row['extractions'].values():
            if result['min_complete_tokens'] is not None:
                assert floor is not None and floor<=result['min_complete_tokens']
            if result['complete']:
                assert row['candidate_score']['complete']


def test_credited_source_packets_retain_their_declared_local_scope(frozen):
    root,rows=frozen
    config=read(root/'study-config.json')
    rules=read(root/'scopes-v3/scope-rules.json')
    rubric=read(Path(config['rubric'])/'rubric-v2.1.json')['families']
    units=read(Path(config['corpus'])/'corpus/source-manifest.json')['source_units']
    texts={u['id']:(Path(config['corpus'])/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for u in units}
    for row in rows:
        family=rubric[row['family_id']]
        for granularity,result in row['extractions'].items():
            for witness in [result['witness']]+([result['minimum_complete']] if result['minimum_complete'] else []):
                for requirement in family['requirements']:
                    if not witness['support'][requirement['id']] or requirement.get('contextual'):
                        continue
                    def closed(proof):
                        return all(oracle.span_present(dict(source_id=sid,start=a,end=z),witness['coverage'],texts)
                            for aid in proof for sid,ranges in rules[aid]['ranges'].items()
                            for x,y in ranges for a,z in oracle.expand(texts[sid],x,y,granularity))
                    assert any(closed(proof) for proof in requirement['proofs']), (row['question_id'],granularity,requirement['id'])
