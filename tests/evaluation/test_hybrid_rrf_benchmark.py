"""Equal candidate caps, union accounting and final-selection delivery controls."""
from copy import deepcopy

import pytest

from laew.eval.hybrid_rrf_benchmark import analyze, verify
from laew.eval.lexical_benchmark import digest


def inputs():
    records = [{"id": i, "text": text, "source": "global", "path": i + ".md", "metadata": {}}
               for i, text in (("a", "required alpha"), ("b", "required beta"), ("c", "other context"))]
    q = {"id": "test", "text": "How do alpha and beta work?", "language": "en", "allowed_scope": "global",
         "no_answer": None, "expected_document_ids": ["@knowledge/a.md", "@knowledge/b.md"],
         "relevance": {"@knowledge/a.md": 2, "@knowledge/b.md": 2},
         "evidence": [{"document_id": "@knowledge/a.md", "passage": "required alpha"},
                      {"document_id": "@knowledge/b.md", "passage": "required beta"}]}
    conditions = [{"dataset_directory": "test", "chunking": {"strategy": "legacy"}, "chunks": records,
                   "queries": [{"query": q, "index_atom_available": [True, True]}], "document_languages": {}}]
    corpus = {"conditions": conditions, "content_hash": digest(conditions)}
    rows = []
    for depth in (5, 10, 20, 50):
        for backend, hits in (("dense_raw", [("a", .8), ("c", .7)]), ("fts5", [("b", -3.), ("c", -2.)])):
            rows.append({"dataset": "test", "chunker": "legacy", "query_id": "test", "k": depth, "backend": backend,
                         "hits": [{"id": i, "source": "global", "path": i + ".md", "score": score} for i, score in hits],
                         "timing_per_scope_ms": {"global": {"median": 1., "p95": 2.}}})
    return corpus, {"corpus_hash": corpus["content_hash"], "rows": rows}


def test_union_can_recover_lexical_only_evidence_and_ranked_fill_delivers_it():
    corpus, retrieval = inputs()
    report = analyze(corpus, retrieval)
    assert len(report["rows"]) == 18
    assert report["primary_dense_selector_controls_matched"] == 1
    rrf = next(r for r in report["rows"] if r["method"] == "rrf" and r["backend_depth"] == r["final_limit"] == 10)
    dense = next(r for r in report["rows"] if r["method"] == "dense" and r["backend_depth"] == r["final_limit"] == 10)
    assert dense["candidate"]["evidence_coverage"] == .5
    assert rrf["union"]["evidence_coverage"] == 1
    assert rrf["candidate"]["complete_evidence"] and rrf["selection"]["metrics"]["complete_evidence"]
    assert rrf["union_count_by_scope"] == {"global": 3}
    assert rrf["selection"]["adapter_received"] and rrf["selection"]["allocation_compliant"]
    assert next(h for h in rrf["candidates_by_scope"]["global"] if h["id"] == "b")["dense_score"] is None
    assert all(n <= r["final_limit"] for r in report["rows"] for n in r["candidate_count_by_scope"].values())
    gain = next(c for c in report["comparisons"] if c["method"] == "rrf" and c["stage"] == "selection")
    assert gain["recovered_atoms"] == [1] and not gain["lost_atoms"]


def test_mismatched_capture_and_modified_corpus_fail_before_analysis():
    corpus, retrieval = inputs()
    retrieval["corpus_hash"] = "wrong"
    with pytest.raises(ValueError, match="different captures"):
        verify(corpus, retrieval)
    corpus["conditions"][0]["chunks"][0]["text"] = "modified"
    with pytest.raises(ValueError, match="cache changed"):
        verify(corpus, retrieval)


def test_overall_budget_and_loss_stage_are_checked_after_candidate_coverage():
    corpus, retrieval = inputs()
    report = analyze(corpus, retrieval, overall_budget=1)
    row = next(r for r in report["rows"] if r["method"] == "rrf" and r["backend_depth"] == r["final_limit"] == 10)
    assert row["candidate"]["complete_evidence"]
    assert row["selection"]["metrics"]["evidence_coverage"] == 0
    assert row["selection"]["context_tokens"] <= 1
    assert {s["stage"] for s in row["atom_stages"]} == {"lost_at_context_budget"}
