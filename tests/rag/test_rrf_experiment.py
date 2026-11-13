"""RRF math, source boundaries, fallback and pre-vetted ranked_fill contracts."""
from copy import deepcopy
from dataclasses import replace
import math
import sqlite3

import pytest

from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes, select_ranked_scopes
from laew.rag.lexical_experiment import Binding, Hit
from laew.rag.rrf_experiment import Ranking, fuse, retrieve
from laew.rag.vector_store import DocumentChunk

BINDING = Binding("fixture", "global")


def record(identifier, text=None, scope="global"):
    return {"id": identifier, "text": text or identifier + " evidence", "source": scope,
            "path": identifier + ".md", "metadata": {"section_path": ["Root", "Evidence"]}}


def ranking(ids_scores, records, binding=BINDING):
    return Ranking(binding, [Hit(records[i], score) for i, score in ids_scores])


def test_rrf_math_uses_rank_not_incompatible_score_magnitudes():
    records = {i: record(i) for i in "abc"}
    dense = ranking([("a", .99), ("b", .31)], records)
    lexical = ranking([("b", -1000.), ("c", -.00001)], records)
    result = fuse(dense, lexical, authorized=records, final_limit=3)
    assert [h.record["id"] for h in result.hits] == ["b", "a", "c"]
    assert result.hits[0].score == pytest.approx(1 / 62 + 1 / 61)
    assert result.hits[0].dense_score == .31 and result.hits[0].lexical_score == -1000
    assert result.hits[2].dense_score is None
    changed = ranking([("b", -.0000001), ("c", -100000)], records)
    assert [h.score for h in fuse(dense, changed, authorized=records).hits] == [h.score for h in result.hits]


def test_filters_before_compact_ranks_and_deduplicates_once():
    records = {i: record(i) for i in "abcd"}
    dense = ranking([("a", .2), ("b", .9), ("b", .8), ("c", .7)], records)
    lexical = ranking([("d", -4), ("b", -3), ("b", -2)], records)
    authorized = {i: records[i] for i in "abc"}
    result = fuse(dense, lexical, authorized=authorized)
    b = next(h for h in result.hits if h.record["id"] == "b")
    assert b.dense_rank == b.lexical_rank == 1
    assert b.score == pytest.approx(2 / 61)
    assert result.diagnostics["dense_rejected"] == {"native_score_gate": 1, "unauthorized": 0, "duplicate": 1}
    assert result.diagnostics["lexical_rejected"]["unauthorized"] == 1
    assert not any(h.record["id"] == "d" for h in result.hits)


def test_equal_rrf_scores_use_id_and_union_precedes_fair_limit():
    records = {i: record(i) for i in "abc"}
    dense = ranking([("c", .8), ("b", .7)], records)
    lexical = ranking([("a", -2), ("b", -1)], records)
    result = fuse(dense, lexical, authorized=records, final_limit=2)
    assert [h.record["id"] for h in result.union] == ["b", "a", "c"]
    assert [h.record["id"] for h in result.hits] == ["b", "a"]
    assert result.diagnostics["union_before_truncation"] == 3
    assert fuse(dense, lexical, authorized=records, final_limit=0).hits == []


def test_absent_lexical_is_exact_dense_fallback_not_an_empty_ranking_error():
    records = {i: record(i) for i in "za"}
    dense = ranking([("z", .8), ("a", .8)], records)
    fallback = fuse(dense, None, authorized=records)
    assert [(h.record["id"], h.score) for h in fallback.hits] == [("z", .8), ("a", .8)]
    assert fallback.diagnostics["dense_fallback"]
    empty = fuse(dense, Ranking(BINDING, []), authorized=records)
    assert not empty.diagnostics["dense_fallback"]
    assert empty.diagnostics["lexical_status"] == "empty"
    assert [h.record["id"] for h in empty.hits] == ["z", "a"]


def test_availability_failure_degrades_but_security_failure_surfaces():
    records = {"a": record("a")}
    dense = ranking([("a", .8)], records)
    def unavailable():
        raise sqlite3.OperationalError("fixture unavailable")
    result = retrieve(lambda: dense, unavailable, authorized=records)
    assert result.diagnostics["dense_fallback"]
    assert "OperationalError" in result.diagnostics["lexical_error"]
    with pytest.raises(ValueError, match="binding"):
        retrieve(lambda: dense, lambda: Ranking(Binding("other-project", "global"), []), authorized=records)
    def missing():
        raise FileNotFoundError("missing lexical snapshot")
    assert retrieve(lambda: dense, missing, authorized=records).diagnostics["dense_fallback"]
    with pytest.raises(FileNotFoundError):
        retrieve(missing, lambda: Ranking(BINDING, []), authorized=records)


def test_empty_or_ineligible_rankings_return_no_evidence():
    records = {"a": record("a")}
    result = fuse(ranking([("a", .2)], records), Ranking(BINDING, []), authorized=records)
    assert not result.hits and not result.union
    assert result.diagnostics["union_before_truncation"] == 0


@pytest.mark.parametrize("change", ["scope", "path", "text", "metadata"])
def test_scope_and_stale_slot_payload_fail_closed(change):
    records = {"a": record("a")}
    corrupted = deepcopy(records["a"])
    corrupted["source" if change == "scope" else change] = "project" if change == "scope" else {} if change == "metadata" else "changed"
    with pytest.raises(ValueError, match="scope|payload"):
        fuse(ranking([("a", .8)], records), Ranking(BINDING, [Hit(corrupted, -1.)]), authorized=records)


def test_project_bindings_do_not_merge_even_with_same_chunk_id():
    records = {"a": record("a", scope="project")}
    first = Ranking(Binding("fixture", "project", "one"), [Hit(records["a"], .8)])
    second = Ranking(Binding("fixture", "project", "two"), [Hit(records["a"], -1)])
    with pytest.raises(ValueError, match="binding"):
        fuse(first, second, authorized=records)


def test_input_bounds_invalid_scores_and_output_independence():
    records = {"a": record("a") | {"embedding": [1., 0.]}}
    before = deepcopy(records)
    dense = ranking([("a", .8)], records)
    result = fuse(dense, Ranking(BINDING, []), authorized=records)
    assert "embedding" not in result.hits[0].record
    result.hits[0].record["metadata"]["section_path"].append("changed")
    assert records == before
    with pytest.raises(ValueError, match="512"):
        fuse(Ranking(BINDING, [dense.hits[0]] * 513), None, authorized=records)
    for bad in (float("nan"), float("inf"), 4.):
        with pytest.raises(ValueError):
            fuse(Ranking(BINDING, [Hit(records["a"], bad)]), None, authorized=records)


@pytest.mark.parametrize("budget", [0, 50, 500, 1000])
def test_pre_vetted_dense_ranked_fill_matches_original_selector(budget):
    chunks = [DocumentChunk("a", "long prerequisite " * 100, source="global", file_path="guide.md"),
              DocumentChunk("b", "short acceptance", source="global", file_path="guide.md")]
    pairs = [(chunks[0], .8), (chunks[1], .7)]
    config = SelectionConfig(policy="ranked_fill", budget=budget)
    old, old_context = select_scopes({"global": [Candidate(c, score) for c, score in pairs]}, config)
    new, new_context = select_ranked_scopes({"global": pairs}, config)
    assert new_context == old_context
    assert new["global"].chunks == old["global"].chunks


def test_pre_vetted_ranked_fill_keeps_order_and_native_scores_without_cosine_faking():
    a = DocumentChunk("a", "lexical-only evidence", source="global")
    b = DocumentChunk("b", "dense-only evidence", source="global")
    pools = {"global": [(a, -.000001), (b, .01)]}
    result, context = select_ranked_scopes(pools, SelectionConfig(policy="ranked_fill", budget=1000))
    assert [c.chunk_id for c, _ in result["global"].chunks] == ["a", "b"]
    assert "lexical-only evidence" in context
    with pytest.raises(ValueError):
        select_ranked_scopes(pools, SelectionConfig(policy="novelty"))
    with pytest.raises(ValueError, match="scope"):
        select_ranked_scopes({"project": pools["global"]}, SelectionConfig(policy="ranked_fill"))
