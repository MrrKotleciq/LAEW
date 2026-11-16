"""Synthetic runtime-input contracts; no benchmark labels or answer fixtures."""
import copy
import inspect
import math

import pytest

from laew.eval import evidence_aware_selection as selector
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.vector_store import DocumentChunk


def candidate(cid,text,score=.8,path='device-v2.md',section='Procedure',scope='global'):
    return Candidate(DocumentChunk(chunk_id=cid,text=text,source=scope,file_path=path,
        metadata={'section_path':['Manual',section],'tags':['navigation'],
                  'backlinks':['index.md'],'frontmatter':{'type':'manual','status':'frozen'}}),score)


def run(pool,query='device version 2 backup procedure and prerequisites',budget=1000,**kwargs):
    selected,enclosing=selector.select_evidence_scopes({'global':pool},
        SelectionConfig(policy='ranked_fill',budget=budget),query,**kwargs)
    return selected['global'],enclosing


def ids(result):
    return [c.chunk_id for c,_ in result.chunks]


def test_query_complement_replaces_duplicate_without_dropping_prerequisite():
    body='Before the backup, start the initiating session and keep it connected. '*4
    pool=[candidate('start',body,.9),candidate('duplicate',body,.89),
          candidate('files','The backup procedure must save returned metadata before ending the session. '*3,.82)]
    result,_=run(pool,query='device version 2 backup session procedure and returned metadata',budget=240)
    assert 'files' in ids(result)
    assert any(cid in ids(result) for cid in ('start','duplicate'))
    assert len(ids(result))==2


def test_unrelated_warning_bait_does_not_acquire_a_query_role():
    pool=[candidate('relevant','Begin the backup session before starting the backup.',.8),
          candidate('bait','WARNING: Do not remove the aquarium cover. Keep the fish cool.',.85,path='aquarium-v2.md')]
    profile=selector.profile_candidates('backup session procedure',pool)
    assert profile['candidates'][0]['roles']
    assert not profile['candidates'][1]['roles']


def test_wrong_explicit_source_version_is_a_weak_penalty_not_source_relabelling():
    pool=[candidate('old','The server backup procedure starts with the old session command. '*3,.92,path='server-v3.md'),
          candidate('target','The server version 2 backup procedure starts the requested session. '*3,.85,path='server-v2.md')]
    profile=selector.profile_candidates('server version 2 backup procedure',pool)
    assert profile['candidates'][0]['identity_conflict']
    result,context=run(pool,'server version 2 backup procedure',budget=130)
    assert ids(result)==['target']
    assert 'server-v2.md' in context and pool[0].chunk.file_path=='server-v3.md'


def test_requested_two_versions_remain_separately_attributed():
    pool=[candidate('two','The server version 2 default recovery setting selects current.',.9,path='server-v2.md'),
          candidate('duplicate','The server version 2 default recovery setting selects current.',.89,path='server-v2.md'),
          candidate('three','The server version 3 default recovery setting selects latest.',.8,path='server-v3.md')]
    result,context=run(pool,'Compare server version 2 and 3 recovery defaults.',budget=180)
    assert 'two' in ids(result) and 'three' in ids(result)
    assert 'server-v2.md' in context and 'server-v3.md' in context


def test_warning_and_negation_body_and_attribution_are_verbatim():
    pool=[candidate('procedure','For firmware installation, connect the matching device.',.9),
          candidate('condition','Before firmware installation, do not disconnect power; keep the controller connected.',.8)]
    before=copy.deepcopy(pool)
    result,context=run(pool,'device version 2 firmware installation requirements')
    assert pool==before
    assert all(c==next(x.chunk for x in pool if x.chunk.chunk_id==c.chunk_id) for c,_ in result.chunks)
    assert 'do not disconnect power' in context
    assert 'navigation' in context and 'backlinks: index.md' in context and 'status: frozen' in context


def test_distinct_warnings_with_the_same_weak_role_are_not_substitutes():
    warning='Before backup, do not disconnect the initiating session.'
    pool=[candidate('original',warning,.9),
          candidate('different','Before backup, do not remove the unrelated adapter.',.89),
          candidate('extra','Backup procedure metadata and session reference.',.8)]
    baseline,_=select_scopes({'global':pool},SelectionConfig(policy='ranked_fill',budget=120))
    result,context=run(pool,'device version 2 backup session procedure metadata',budget=120)
    if 'original' in ids(baseline['global']):
        assert warning in context


def test_quantitative_limit_is_protected_without_claiming_its_semantics():
    limit='The device power requirement is 24 V and 2 A.'
    assert limit in selector.risk_clauses(limit)
    pool=[candidate('limit',limit,.9),candidate('other','Device configuration and power procedure documentation.',.85)]
    result,context=run(pool,'device version 2 power configuration procedure',budget=105)
    assert limit in context


@pytest.mark.parametrize('budget',[0,1,10,40,100,500,1000])
def test_clipped_baseline_falls_back_verbatim_without_new_excerpt(budget):
    pool=[candidate('long','A complete device procedure. '*250+'Do not remove the guard.')]
    cfg=SelectionConfig(policy='ranked_fill',budget=budget)
    baseline,_=select_scopes({'global':pool},cfg)
    result,enclosing=run(pool,budget=budget)
    assert result.context==baseline['global'].context
    assert result.estimated_tokens<=budget and math.ceil(len(enclosing)/4)<=8000


def test_anchor_only_html_is_diagnostic_and_has_no_evidence_role():
    pool=[candidate('anchor',' <a id="_backup"></a>\n',.99),
          candidate('body','The backup procedure retains the required metadata.',.8)]
    assert selector.anchor_only(pool[0].chunk.text)
    assert not selector.anchor_only('<a id="x"></a>\nKeep the backup metadata.')
    profile=selector.profile_candidates('backup procedure metadata',pool)
    assert profile['candidates'][0]['anchor_only'] and not profile['candidates'][0]['roles']
    assert not profile['candidates'][0]['query_features']


def test_unknown_query_alignment_falls_back_without_inventing_roles():
    pool=[candidate('a','Opaque technical material.',.9),candidate('b','Other material.',.8)]
    baseline,_=select_scopes({'global':pool},SelectionConfig(policy='ranked_fill',budget=1000))
    result,_=run(pool,'Uninterpretable zyxwvu qrstuv')
    assert result.context==baseline['global'].context
    assert result.decisions[0]['fallback']=='insufficient_query_alignment'


def test_determinism_and_native_order_with_tied_scores():
    pool=[candidate(str(i),f'Backup procedure metadata item {i}.',.8) for i in range(8)]
    first,context=run(pool,'device version 2 backup metadata procedure',budget=300)
    second,context2=run(pool,'device version 2 backup metadata procedure',budget=300)
    assert first==second and context==context2
    assert ids(first)==sorted(ids(first),key=int)


@pytest.mark.parametrize('kind',['scope','duplicate','nan','k11','relevance','version'])
def test_invalid_runtime_inputs_fail_closed(kind):
    pool=[candidate('one','Backup technical procedure.')]
    kwargs={}
    if kind=='scope':pool=[candidate('one','Body',scope='project')]
    elif kind=='duplicate':pool*=2
    elif kind=='nan':pool=[candidate('one','Body',float('nan'))]
    elif kind=='k11':pool=[candidate(str(i),'Body') for i in range(11)]
    elif kind=='relevance':pool=[Candidate(pool[0].chunk,.8,.9)]
    else:kwargs['version']='unknown'
    with pytest.raises(ValueError):run(pool,**kwargs)


def test_exact_scope_allocator_and_source_separation():
    pools={scope:[candidate(scope+str(i),'Backup session procedure requires metadata. '*3,.9-i*.02,scope=scope) for i in range(5)] for scope in ('global','project')}
    selected,context=selector.select_evidence_scopes(pools,SelectionConfig(policy='ranked_fill',budget=1000),
        'backup session procedure metadata',overall_budget=500)
    assert math.ceil(len(context)/4)<=500
    assert all(c.source==scope for scope,result in selected.items() for c,_ in result.chunks)


def test_threshold_empty_and_original_cosine_are_preserved():
    pool=[candidate('eligible','Backup metadata procedure.',.8),candidate('low','Backup warning.',.299),candidate('empty','',.99)]
    result,_=run(pool,'backup metadata procedure')
    assert ids(result)==['eligible'] and result.chunks[0][1]==.8


def test_selector_cannot_open_data_or_import_evaluation_scoring():
    source=inspect.getsource(selector)
    for forbidden in ('score_evidence','proof_present','read_text','open(', 'Path(',
                      'oracle','P02','S12','S13','draft-labels','source-atoms'):
        assert forbidden not in source
