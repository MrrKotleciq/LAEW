"""Behavioral boundaries for the isolated selector; no model/service calls."""
from dataclasses import replace
import math

import pytest

from laew.rag.evidence_selection import Candidate, SelectionConfig, select, select_scopes
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import DocumentChunk


def candidate(identifier, text, score=.8, path="guide.md", source="global", **metadata):
    return Candidate(DocumentChunk(identifier, text, source=source, file_path=path, metadata=metadata), score)


@pytest.mark.parametrize("policy", ["top2", "ranked_fill", "novelty"])
def test_empty_ineligible_and_zero_budget(policy):
    config = SelectionConfig(policy=policy)
    assert not select([], "global", config).chunks
    assert not select([candidate("a", "unsupported", .299)], "global", config).chunks
    assert not select([candidate("a", "supported")], "global", replace(config, budget=0)).chunks


@pytest.mark.parametrize("policy", ["top2", "ranked_fill"])
def test_controls_match_renderer_including_attribution_skip_and_clipping(policy):
    pool = [candidate("a", "long " * 300, .9, section_path=["Root", "Prerequisite"],
                      tags=["engineering"], frontmatter={"status": "approved"}),
            candidate("b", "more " * 300, .8), candidate("c", "short", .7)]
    for budget in (10, 80, 400, 1000):
        result = select(pool, "global", SelectionConfig(policy=policy, budget=budget))
        pairs = [(c.chunk, c.cosine) for c in (pool[:2] if policy == "top2" else pool)]
        expected = RAGPipeline(None, None, max_context_tokens=budget)._build_context(pairs)
        assert (result.context, result.chunks, result.estimated_tokens) == expected


def test_novelty_suppresses_copies_but_keeps_same_document_complements():
    pool = [candidate("a", "Disconnect excitation before the firmware update.", .9),
            candidate("copy", "Disconnect excitation before the firmware update.", .89, "copy.md"),
            candidate("b", "Acceptance requires forty seconds without dropped samples.", .8),
            candidate("c", "Record the approved checksum in the external audit.", .7, "audit.md")]
    result = select(pool, "global", SelectionConfig())
    assert [c.chunk_id for c, _ in result.chunks] == ["a", "b", "c"]
    assert {c.file_path for c, _ in result.chunks} == {"guide.md", "audit.md"}
    assert next(d for d in result.decisions if d["id"] == "copy")["reason"] == "low_marginal_utility"


def test_one_fragment_for_repeated_information_and_stable_ties():
    pool = [candidate("z", "One exact sentence."), candidate("a", "One exact sentence.")]
    first = select(pool, "global", SelectionConfig())
    assert [c.chunk_id for c, _ in first.chunks] == ["z"]
    assert first == select(pool, "global", SelectionConfig())
    assert pool[0].chunk.text == "One exact sentence."


def test_whole_fragments_include_metadata_cost_and_no_partial_prerequisites():
    pool = [candidate("a", "prerequisite " * 200, .9),
            candidate("b", "short instruction", .8, section_header="long header " * 100),
            candidate("c", "small independent fact", .7)]
    result = select(pool, "global", SelectionConfig(budget=50))
    assert [c.chunk_id for c, _ in result.chunks] == ["c"]
    assert result.estimated_tokens == math.ceil(len(result.context) / 4) <= 50
    assert result.chunks[0][0] is pool[2].chunk


@pytest.mark.parametrize("policy", ["top2", "ranked_fill", "novelty"])
def test_scope_security_and_bounds_fail_closed(policy):
    config = SelectionConfig(policy=policy)
    with pytest.raises(ValueError, match="scope"):
        select([candidate("p", "secret", source="project")], "global", config)
    with pytest.raises(ValueError, match="single"):
        select([], "hybrid", config)
    with pytest.raises(ValueError, match="bound"):
        select([candidate(str(i), "text") for i in range(129)], "global", config)
    with pytest.raises(ValueError, match="character"):
        select([candidate("a", "x" * 50)], "global", replace(config, max_total_chars=20))
    with pytest.raises(ValueError, match="unique"):
        select([candidate("a", "first"), candidate("a", "changed")], "global", config)
    for bad in (float("nan"), float("inf"), 4.):
        with pytest.raises(ValueError, match="cosine"):
            select([candidate("a", "text", bad)], "global", config)


def test_configuration_does_not_lower_existing_eligibility_gate():
    for threshold in (.299, float("nan")):
        with pytest.raises(ValueError, match="threshold"):
            SelectionConfig(threshold=threshold)
    with pytest.raises(ValueError):
        SelectionConfig(max_candidates=129)


def test_future_normalized_relevance_preserves_original_cosine_gate_and_scores():
    pool = [replace(candidate("a", "alpha", .8), relevance=.2),
            replace(candidate("b", "beta", .7), relevance=.9),
            replace(candidate("c", "filtered", .2), relevance=1.)]
    result = select(pool, "global", SelectionConfig(policy="ranked_fill"))
    assert [(c.chunk_id, score) for c, score in result.chunks] == [("b", .7), ("a", .8)]
    with pytest.raises(ValueError, match="normalized"):
        select([replace(pool[0], relevance=3.)], "global", SelectionConfig())
    with pytest.raises(ValueError, match="mix"):
        select([pool[0], candidate("d", "delta")], "global", SelectionConfig())


@pytest.mark.parametrize("budget", [0, 1, 100, 8000])
def test_overall_allocation_includes_scope_wrappers_without_score_merging(budget):
    pools = {"global": [candidate("g", "global evidence " * 2000, .5)],
             "project": [candidate("p", "project evidence " * 2000, .99, source="project")]}
    results, context = select_scopes(pools, SelectionConfig(policy="ranked_fill", budget=5000), budget)
    assert math.ceil(len(context) / 4) <= budget
    assert set(results) == {"global", "project"}
    if budget == 8000:
        assert "@knowledge" in context and "@project" in context
        assert math.ceil(len(context) / 4) > 7990


def test_no_accidental_runtime_import():
    from pathlib import Path
    for name in ("laew/runtime.py", "laew/knowledge/routing.py", "laew/agent/executor.py", "laew/rag/pipeline.py"):
        assert "evidence_selection" not in Path(name).read_text(encoding="utf-8")
