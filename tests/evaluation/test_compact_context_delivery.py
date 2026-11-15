"""Synthetic coverage, safety, budgets and unchanged attribution controls."""
import copy

import pytest

from laew.eval.compact_context_delivery import select_compact_scopes
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.vector_store import DocumentChunk


def candidate(cid, text, *, score=.9, path='manual.md', tags=None, source='global'):
    return Candidate(DocumentChunk(chunk_id=cid, text=text, source=source, file_path=path,
        metadata={'section_path':['Version 2','Procedure'], 'tags':tags or [],
                  'backlinks':['other.md'], 'frontmatter':{'type':'public-technical-source',
                                                        'status':'verified-with-limitations'}}),score)


def test_compact_attribution_delivers_complementary_warning_without_body_edits():
    pool=[candidate('procedure','Use the documented procedure.',tags=['navigation-anchor-'*25]),
          candidate('warning','WARNING: disconnect power before opening.',score=.8,tags=['navigation-anchor-'*25])]
    config=SelectionConfig(policy='ranked_fill',budget=160)
    baseline,_=select_scopes({'global':pool},config)
    compact,context=select_compact_scopes({'global':pool},config)
    assert 'WARNING: disconnect power before opening.' in context
    assert len(compact['global'].chunks)>len(baseline['global'].chunks)
    assert [c.text for c,_ in compact['global'].chunks]==[c.chunk.text for c in pool]
    assert 'Version 2 > Procedure' in context and 'verified-with-limitations' in context
    assert 'manual.md' in context and 'GLOBAL KNOWLEDGE @knowledge' in context
    assert 'navigation-anchor' not in context and 'backlinks:' not in context


def test_missing_discovery_metadata_is_byte_identical_to_baseline():
    pool=[candidate('one','A complete technical statement.')]
    pool[0].chunk.metadata.pop('backlinks')
    config=SelectionConfig(policy='ranked_fill',budget=300)
    baseline,original=select_scopes({'global':pool},config)
    compact,context=select_compact_scopes({'global':pool},config)
    assert context==original and compact['global'].estimated_tokens==baseline['global'].estimated_tokens


def test_inputs_rank_scores_and_token_budgets_are_preserved():
    pool=[candidate(str(i),'Body '+str(i)+' '+('content '*50),score=.9-i*.01,tags=['index '*100]) for i in range(10)]
    before=copy.deepcopy(pool)
    config=SelectionConfig(policy='ranked_fill',budget=500)
    compact,context=select_compact_scopes({'global':pool},config,overall_budget=600)
    assert pool==before
    assert compact['global'].estimated_tokens<=500 and (len(context)+3)//4<=600
    ids=[c.chunk_id for c,_ in compact['global'].chunks]
    assert ids==sorted(ids,key=int)
    assert all(score==pool[int(c.chunk_id)].cosine for c,score in compact['global'].chunks)


def test_native_top2_does_not_expand_to_deeper_candidates():
    pool=[candidate(str(i),'body '+str(i),score=.9-i*.1) for i in range(3)]
    compact,_=select_compact_scopes({'global':pool},SelectionConfig(policy='top2',budget=500))
    assert [c.chunk_id for c,_ in compact['global'].chunks]==['0','1']


def test_wrong_scope_and_duplicate_candidates_still_fail():
    config=SelectionConfig(policy='ranked_fill',budget=1000)
    with pytest.raises(ValueError,match='scope'):
        select_compact_scopes({'global':[candidate('one','body',source='project')]},config)
    with pytest.raises(ValueError,match='unique'):
        select_compact_scopes({'global':[candidate('one','body'),candidate('one','other')]},config)


def test_eligibility_gate_unchanged_and_no_novelty_policy():
    compact,_=select_compact_scopes({'global':[candidate('low','body',score=.29)]},
                                   SelectionConfig(policy='ranked_fill',budget=500))
    assert compact['global'].chunks==[]
    with pytest.raises(ValueError):
        select_compact_scopes({},SelectionConfig(policy='novelty'))


def test_first_fragment_clipping_cannot_invent_an_unseen_warning():
    text='Ordinary prose. '*100+'WARNING: never remove protective earth.'
    compact,context=select_compact_scopes({'global':[candidate('long',text,tags=['tag '*100])]},
                                        SelectionConfig(policy='ranked_fill',budget=100))
    chunk=compact['global'].chunks[0][0]
    assert text.startswith(chunk.text) and len(chunk.text)<len(text)
    assert 'protective earth' not in context


def test_compact_context_survives_real_first_dispatch_without_network():
    from laew.eval.real_world_answer_plan import serialize
    _,context=select_compact_scopes({'global':[candidate('one','WARNING: keep the supply disconnected.',
                                                           tags=['navigation-only'])]},
                                   SelectionConfig(policy='ranked_fill',budget=500))
    payload=serialize('A manually authored synthetic question.',context)
    assert payload['instructions'].endswith(context)
    assert 'WARNING: keep the supply disconnected.' in payload['instructions']
    assert 'navigation-only' not in payload['instructions']
    assert payload['tools']==[] and payload['store'] is False and payload['stream'] is True


def test_freed_budget_can_displace_a_later_short_fragment_so_regressions_are_measured():
    # The mechanism does not claim evidence-monotonicity: ranked-fill is greedy.
    pool=[candidate('first','a'*80),candidate('second','b'*850,tags=['tag '*150],score=.8),
          candidate('late-warning','WARNING: retain backups.',score=.7)]
    config=SelectionConfig(policy='ranked_fill',budget=310)
    baseline,_=select_scopes({'global':pool},config)
    compact,_=select_compact_scopes({'global':pool},config)
    assert 'late-warning' in [c.chunk_id for c,_ in baseline['global'].chunks]
    assert 'second' in [c.chunk_id for c,_ in compact['global'].chunks]
    assert 'late-warning' not in [c.chunk_id for c,_ in compact['global'].chunks]
