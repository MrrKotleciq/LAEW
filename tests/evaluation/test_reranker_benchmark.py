"""Offline mathematical and boundary regressions for the isolated reranker experiment."""
import hashlib
import json
import math
from pathlib import Path

import pytest

from laew.eval.reranker_benchmark import (
    BUDGETS, RerankError, RerankerClient, TimedClient, atom_present, client_module, digest,
    paired_comparisons, rank_metrics, replay, restore, scoped_ranking_metrics, split_rerank,
)
from laew.rag.pipeline import RAGPipeline


def item(identifier, text, path=None):
    return {"id": identifier, "text": text, "path": path or identifier + ".md",
            "source": "global", "metadata": {"section_header": "Evidence"}, "cosine": .8}


def query():
    return {"text": "How do both checks work?", "allowed_scope": "global", "no_answer": None,
            "expected_document_ids": ["@knowledge/a.md", "@knowledge/b.md"],
            "relevance": {"@knowledge/a.md": 2, "@knowledge/b.md": 2},
            "evidence": [{"document_id": "@knowledge/a.md", "passage": "required alpha"},
                         {"document_id": "@knowledge/b.md", "passage": "required beta"}]}


def test_twenty_document_mapping_and_native_limit():
    class Client:
        timeout = 45
        calls = []
        def rerank(self, value):
            self.calls.append(value)
            n = len(value["documents"])
            return {"results": [{"index": i, "score": float(int(value['documents'][i]['id']))} for i in reversed(range(n))],
                    "candidate_count": n, "request_ms": 2, "inference_ms": 1,
                    "truncation": {"status": "none"}}
    client = Client()
    chunks = [item(str(i), f"text {i}") for i in range(20)]
    response = split_rerank(client, "query", chunks)
    assert [len(call["documents"]) for call in client.calls] == [16, 4]
    assert response["scores"] == {str(i): i for i in range(20)}
    assert all(call["truncate"] is False for call in client.calls)
    assert client.timeout == 45


def test_timing_wrapper_preserves_shared_client_and_distinguishes_native_header(monkeypatch):
    def transport(self, path, body=None):
        if path == "/info":
            return {"model_id": client_module.MODELS["gte"]["model_id"],
                    "model_sha": client_module.MODELS["gte"]["revision"]}, {}
        return [{"index": i, "score": 1.} for i in range(len(body["texts"]))], {
            "x-inference-time": "2", "x-total-time": "4"}
    monkeypatch.setattr(RerankerClient, "_request", transport)
    result = split_rerank(TimedClient("gte"), "private-query", [item("a", "private-document")])
    assert result["native_inference_ms"] == 2
    assert result["server_total_ms"] == 4
    assert result["rerank_post_ms"] >= 0
    assert "private" not in json.dumps(result["calls"])


def test_incomplete_mapping_is_not_silently_cosine_fallback():
    class Client:
        timeout = 45
        def rerank(self, value):
            return {"results": [], "candidate_count": len(value["documents"]),
                    "request_ms": 1, "inference_ms": 1, "truncation": {}}
    with pytest.raises(RerankError, match="mapping"):
        split_rerank(Client(), "query", [item("a", "text")])


def test_metrics_separate_missing_document_and_duplicate_document_rank():
    pairs = [(restore(item("a1", "required alpha", "a.md")), 3),
             (restore(item("a2", "required alpha", "a.md")), 2),
             (restore(item("irrelevant", "unrelated")), 1)]
    metrics = rank_metrics(query(), pairs, cutoff=20)
    assert metrics["document_recall"] == .5
    assert metrics["evidence_coverage"] == .5
    assert metrics["complete_evidence"] is False
    assert metrics["evidence_positions"] == [1, None]
    assert metrics["ndcg"] == pytest.approx(3 / (3 + 3 / math.log2(3)))
    assert metrics["mrr"] == 1


def test_budget_removal_and_adapter_delivery_are_different_stages():
    pipeline = RAGPipeline(None, None, max_context_tokens=10000)
    pairs = [(restore(item("a", "required alpha " + "filler " * 190)), 2),
             (restore(item("b", "required beta " + "filler " * 140)), 1)]
    assert rank_metrics(query(), pairs)["complete_evidence"]
    small, used, tokens = pipeline._build_context(pairs, 500)
    assert tokens <= 500
    assert rank_metrics(query(), used)["evidence_coverage"] == .5
    large, all_used, tokens = pipeline._build_context(pairs, 5000)
    assert rank_metrics(query(), all_used)["complete_evidence"]
    received, _ = replay(query(), [("global", large)])
    assert received
    assert BUDGETS == (500, 1000, 5000)


def test_evidence_cannot_match_another_source_or_section():
    atom = {"document_id": "@knowledge/a.md", "section": "Evidence", "passage": "required alpha"}
    assert atom_present(atom, restore(item("a", "required alpha")))
    assert not atom_present(atom, restore(item("b", "required alpha")))
    changed = item("a", "required alpha")
    changed["metadata"]["section_header"] = "Other"
    assert not atom_present(atom, restore(changed))


def test_hybrid_ranks_are_computed_per_scope():
    question = query()
    question["allowed_scope"] = "hybrid"
    question["expected_document_ids"][0] = "@project/a.md"
    question["relevance"] = {"@project/a.md": 2, "@knowledge/b.md": 2}
    question["evidence"][0]["document_id"] = "@project/a.md"
    project = item("a", "required alpha")
    project["source"] = "project"
    metrics = scoped_ranking_metrics(question, [("project", [(restore(project), 1)]),
        ("global", [(restore(item("noise", "unrelated")), 4), (restore(item("b", "required beta")), 3)])], 20)
    assert metrics["mrr"] == .75
    assert metrics["evidence_positions"] == [1, 2]


def test_holdout_freeze_and_labels_without_models():
    root = Path("tests/rag/reranker_holdout_v1")
    frozen = json.loads((root / "FREEZE.json").read_text(encoding="utf-8"))
    for relative, expected in frozen["sha256"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected
    dataset = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
    assert len(dataset["queries"]) == 32
    assert {q["language"] for q in dataset["queries"]} == {"en", "pl", "de"}
    for question in dataset["queries"]:
        for evidence in question["evidence"]:
            alias, name = evidence["document_id"].split("/", 1)
            path = root / ("global" if alias == "@knowledge" else "project") / name
            assert evidence["passage"] in path.read_text(encoding="utf-8")
    assert digest(dataset) == digest(json.loads(json.dumps(dataset)))


def test_paired_uncertainty_clusters_shared_sources_and_tracks_regressions():
    rows = []
    for qid, topic, document, before, after in (("x1", "t1", "a", 0, 1),
        ("x2", "t2", "a", .5, 1), ("x3", "t3", "b", 1, .5)):
        for method, value in (("cosine", before), ("gte", after)):
            rows.append({"dataset": "holdout", "strategy": "legacy", "k": 20,
                         "policy": "top2", "budget_per_scope": 1000,
                         "query_id": qid, "topic_id": topic, "method": method,
                         "no_answer": False, "multi_document": False,
                         "stages": [{"document": document}],
                         "ranking": {"ndcg": value},
                         "final": {"evidence_coverage": value, "complete_evidence": value == 1}})
    result = paired_comparisons(rows, resamples=100)[0]
    assert result["independent_topic_components"] == 2
    assert result["mean_delta"] == pytest.approx(1 / 3)
    assert result["regressed_queries"] == ["x3"]
    assert result["one_document_regressions"] == ["x3"]
    assert result["cluster_bootstrap_95ci"][0] < 0
