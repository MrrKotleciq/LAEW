"""Synthetic contracts for whole-fragment complementary context packing."""
import copy
import inspect
import math

import pytest

from laew.eval import complementary_context_selection as selector
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.vector_store import DocumentChunk


def candidate(cid, text, score=.8, path='manual-v2.md', section='Procedure', scope='global', tags=None):
    return Candidate(DocumentChunk(chunk_id=cid, text=text, source=scope, file_path=path,
        metadata={'section_path': ['Version 2', section], 'tags': tags or [], 'backlinks': ['index.md'],
                  'frontmatter': {'type': 'technical-source', 'status': 'restricted-text-only'}}), score)


def run(pool, budget=1000, **kwargs):
    results, enclosing = selector.select_complementary_scopes({'global': pool},
        SelectionConfig(policy='ranked_fill', budget=budget), query='installation precautions', **kwargs)
    return results['global'], enclosing


def ids(result):
    return [c.chunk_id for c, _ in result.chunks]


def test_joint_packing_prefers_complement_over_exact_duplicate():
    text = 'Check the installed version before continuing with the procedure. ' * 5
    pool = [candidate('anchor', text, .9), candidate('duplicate', text, .89),
            candidate('warning', 'Disconnect power. Wait for the surface to cool. Keep the shield installed. ' * 5,
                      .8, section='Precautions')]
    result, context = run(pool, budget=270, version='complementary-pack-v1')
    assert ids(result) == ['anchor', 'warning']
    assert 'Wait for the surface to cool.' in context
    assert result.estimated_tokens <= 270


def test_new_section_in_same_document_is_allowed_and_body_is_never_rewritten():
    pool = [candidate('start', 'Start in maintenance mode after checking the version.', .9),
            candidate('limits', 'Only use the matching device revision. Never interrupt power.', .8, section='Limits')]
    result, context = run(pool)
    assert ids(result) == ['start', 'limits']
    assert [c.text for c, _ in result.chunks] == [c.chunk.text for c in pool]
    assert 'Version 2 > Limits' in context and 'restricted-text-only' in context
    assert 'manual-v2.md' in context and 'GLOBAL KNOWLEDGE @knowledge' in context


def test_different_versions_remain_separately_attributed():
    pool = [candidate('v2', 'The default is current.', .9, path='server-v2.md'),
            candidate('v3', 'The default is latest.', .8, path='server-v3.md')]
    result, context = run(pool)
    assert ids(result) == ['v2', 'v3']
    assert 'server-v2.md' in context and 'server-v3.md' in context


def test_warning_keyword_is_not_an_applicability_detector():
    # This selector does not establish relevance or an actual warning obligation.
    # Complete local prose remains the unit even without a WARNING label.
    pool = [candidate('procedure', 'Use the maintenance branch only after the pump has stopped. ' * 4, .9),
            candidate('conditional', 'If cleaning is required, allow the plate to cool before touching it.', .8)]
    result, _ = run(pool)
    assert ids(result) == ['procedure', 'conditional']
    assert result.chunks[1][0].text == pool[1].chunk.text


@pytest.mark.parametrize('budget', [0, 1, 10, 40, 100, 500, 1000])
def test_budget_and_clipping_follow_baseline_without_invented_suffix(budget):
    pool = [candidate('long', 'A complete sentence. ' * 150 + 'Only after cooling: remove the part.', .9)]
    baseline, _ = select_scopes({'global': pool}, SelectionConfig(policy='ranked_fill', budget=budget))
    result, enclosing = run(pool, budget)
    assert result.estimated_tokens <= budget
    assert math.ceil(len(enclosing) / 4) <= 8000
    if baseline['global'].chunks and len(baseline['global'].chunks[0][0].text) < len(pool[0].chunk.text):
        assert result.context == baseline['global'].context
        assert 'remove the part' not in result.context


def test_exact_cost_with_all_scope_wrappers_and_separators():
    pools = {scope: [candidate(scope + str(i), 'Unique content ' + str(i) + ' safe. ' * 20,
                               .9 - i * .01, scope=scope) for i in range(5)] for scope in ('global', 'project')}
    results, context = selector.select_complementary_scopes(pools,
        SelectionConfig(policy='ranked_fill', budget=1000), overall_budget=340)
    assert math.ceil(len(context) / 4) <= 340
    assert all(r.estimated_tokens < 170 for r in results.values())
    assert all(c.source == scope for scope, result in results.items() for c, _ in result.chunks)


def test_purity_determinism_score_and_metadata_preservation():
    pool = [candidate(str(i), f'Procedure {i} for the selected revision and its limits.', .9 - i * .01,
                      section=str(i), tags=['navigation-' * 100]) for i in range(10)]
    before = copy.deepcopy(pool)
    first, context = run(pool)
    second, context2 = run(pool)
    assert first == second and context == context2 and pool == before
    assert all(score == pool[int(c.chunk_id)].cosine for c, score in first.chunks)
    assert 'navigation-' not in context and 'backlinks:' not in context
    assert all(c.metadata['frontmatter'] == before[int(c.chunk_id)].chunk.metadata['frontmatter']
               for c, _ in first.chunks)


@pytest.mark.parametrize('kind', ['scope', 'duplicate', 'nan', 'k11', 'relevance'])
def test_invalid_inputs_fail_closed(kind):
    pool = [candidate('one', 'Complete technical content.')]
    if kind == 'scope':
        pool = [candidate('one', 'Body', scope='project')]
    elif kind == 'duplicate':
        pool *= 2
    elif kind == 'nan':
        pool = [candidate('one', 'Body', float('nan'))]
    elif kind == 'k11':
        pool = [candidate(str(i), 'Body') for i in range(11)]
    else:
        pool = [Candidate(pool[0].chunk, .9, .8)]
    with pytest.raises(ValueError):
        run(pool)


def test_ineligible_and_empty_candidates_cannot_contribute():
    result, _ = run([candidate('low', 'Useful looking warning', .29), candidate('empty', '', .9)])
    assert result.chunks == []


def test_selector_has_no_evaluation_or_filesystem_access():
    source = inspect.getsource(selector)
    for forbidden in ('score_evidence', 'source-atoms', 'draft-labels', 'read_text', 'open(',
                      'P02', 'P03', 'rubric', 'reference_answer'):
        assert forbidden not in source


def test_exact_unicode_shingles_and_empty_sets():
    assert selector.shingles('') == set()
    assert selector.shingles('NIE usuń WAL') == {('nie', 'usuń', 'wal')}
    assert selector.bitsets([set(), {'a'}, {'a', 'b'}]) == [0, 1, 3]


@pytest.mark.parametrize('budget', [180, 270, 500, 1000])
def test_v2_retains_every_baseline_body_even_when_novel_text_scores_higher(budget):
    pool = [candidate('first', 'Preparation requires the original backup manifest. ' * 5, .9),
            candidate('duplicate', 'Preparation requires the original backup manifest. ' * 5, .89),
            candidate('late', 'If changing configuration, keep normal settings and do not start the service.', .8),
            candidate('novel', 'Many different unrelated words describe installation features and documentation. ' * 8, .7)]
    cfg = SelectionConfig(policy='ranked_fill', budget=budget)
    baseline, _ = select_scopes({'global': pool}, cfg)
    result, _ = run(pool, budget, version='complementary-pack-v2')
    delivered = {c.chunk_id: c.text for c, _ in result.chunks}
    assert all(delivered[c.chunk_id] == c.text for c, _ in baseline['global'].chunks)


def test_v2_can_add_complement_without_displacing_original_warning():
    pool = [candidate('first', 'Prepare the device with the matching firmware. ' * 4, .9,
                      tags=['navigation-' * 45]),
            candidate('second', 'Additional installation procedure. ' * 12, .85, tags=['navigation-' * 45]),
            candidate('warning', 'Keep the device disconnected until the inspection is complete.', .8),
            candidate('complement', 'The media must use the documented filesystem.', .7, section='Media')]
    baseline, _ = select_scopes({'global': pool}, SelectionConfig(policy='ranked_fill', budget=310))
    result, _ = run(pool, 310, version='complementary-pack-v2')
    assert 'warning' in ids(baseline['global'])
    assert set(ids(baseline['global'])) <= set(ids(result))
    assert 'complement' in ids(result)
