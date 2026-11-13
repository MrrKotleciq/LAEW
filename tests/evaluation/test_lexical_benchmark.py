"""Candidate-only metrics and real isolated backend evaluation boundaries."""
import importlib.util

import pytest

from laew.eval.lexical_benchmark import benchmark, digest, measure_resource


def pool():
    chunks = [{"id": "a", "text": "alpha prerequisite", "source": "global", "path": "a.md", "metadata": {}, "embedding": [1., 0.]},
              {"id": "b", "text": "beta acceptance", "source": "global", "path": "b.md", "metadata": {}, "embedding": [.8, .2]}]
    question = {"id": "quality", "text": "alpha beta", "allowed_scope": "global", "language": "en", "no_answer": None,
                "expected_document_ids": ["@knowledge/a.md", "@knowledge/b.md"],
                "relevance": {"@knowledge/a.md": 2, "@knowledge/b.md": 2},
                "evidence": [{"document_id": "@knowledge/a.md", "passage": "alpha prerequisite"},
                             {"document_id": "@knowledge/b.md", "passage": "beta acceptance"}]}
    unsupported = dict(question, id="unsupported", text="zzunknownlexicaltoken", no_answer="unsupported", expected_document_ids=[], relevance={}, evidence=[])
    conditions = [{"dataset_directory": "test", "chunking": {"strategy": "legacy"}, "chunks": chunks,
                   "document_languages": {"@knowledge/a.md": "de", "@knowledge/b.md": "en"},
                   "queries": [{"query": question, "embedding": [1., 0.], "index_atom_available": [True, True]},
                               {"query": unsupported, "embedding": [1., 0.], "index_atom_available": []}]}]
    return {"conditions": conditions, "content_hash": digest(conditions)}


@pytest.mark.skipif(importlib.util.find_spec("bm25s") is None, reason="Optional pinned BM25S dependency")
def test_candidate_metrics_are_separate_from_selection_and_no_answer_behavior():
    data = pool()
    data["conditions"][0]["dataset_directory"] = "stress_1036"
    data["content_hash"] = digest(data["conditions"])
    result = benchmark(data, repeats=1)
    assert len(result["rows"]) == 2 * 4 * 4
    for row in result["rows"]:
        if not row["no_answer"]:
            assert row["metrics"]["complete_evidence"]
            assert row["multi_document"] and row["cross_language"]
            assert len(row["hits"]) == 2  # no fixed-K zero-score padding
    summaries = [s for s in result["summary"] if s["k"] == 20]
    assert next(s for s in summaries if s["backend"] == "fts5")["unsupported_empty_rate"] == 1
    assert next(s for s in summaries if s["backend"] == "bm25s")["unsupported_empty_rate"] == 1
    assert next(s for s in summaries if s["backend"] == "dense_raw")["unsupported_empty_rate"] == 0
    fts = next(r for r in result["rows"] if r["backend"] == "fts5" and not r["no_answer"])
    assert all(hit["score"] < 0 for hit in fts["hits"])  # never filtered by cosine >= .3
    exact = next(r for r in result["stress_exact_cosine_diagnostic"] if r["query_id"] == "quality")
    assert exact["atom_ranks"] == [1, 2]
    assert exact["metrics_at_k"]["5"]["complete_evidence"]


def test_cache_hash_detects_modified_text_before_opening_indexes():
    data = pool()
    data["conditions"][0]["chunks"][0]["text"] = "modified"
    with pytest.raises(ValueError, match="Cached corpus"):
        benchmark(data, repeats=1)


def test_resource_probe_verifies_native_mutation_and_reload(tmp_path):
    data = pool()["conditions"][0]
    result = measure_resource(data, "fts5", tmp_path / "resource.db")
    assert all(m["verified"] for m in result["mutations"])
    assert result["post_mutation_equals_clean"] and result["reload_verified"]
    assert result["active_index_bytes_after_mutations"] > 0
    assert result["python_traced_build_peak_bytes"] > 0
