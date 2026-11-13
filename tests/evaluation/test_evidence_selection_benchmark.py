"""Evidence-loss accounting, frozen labels and real adapter serialization replay."""
import hashlib
import json
from pathlib import Path

import pytest

from laew.eval.evidence_selection_benchmark import analyze, pairs_for, verify
from laew.eval.reranker_benchmark import digest


def fixture_pool():
    chunks = [
        {"id": "a", "text": "First required prerequisite.", "source": "global", "path": "guide.md", "metadata": {}, "cosine": .9},
        {"id": "copy", "text": "First required prerequisite.", "source": "global", "path": "guide.md", "metadata": {}, "cosine": .89},
        {"id": "b", "text": "Second necessary acceptance condition.", "source": "global", "path": "guide.md", "metadata": {}, "cosine": .8},
        {"id": "x", "text": "Unavailable below threshold.", "source": "global", "path": "other.md", "metadata": {}, "cosine": .2},
    ]
    question = {"id": "test", "text": "What are the prerequisite and acceptance checks?", "language": "en",
                "allowed_scope": "global", "phenomenon": "procedure", "no_answer": None,
                "expected_document_ids": ["@knowledge/guide.md"], "relevance": {"@knowledge/guide.md": 2},
                "evidence": [{"document_id": "@knowledge/guide.md", "passage": "First required prerequisite."},
                             {"document_id": "@knowledge/guide.md", "passage": "Second necessary acceptance condition."},
                             {"document_id": "@knowledge/other.md", "passage": "Unavailable below threshold."}]}
    conditions = [{"dataset_directory": "test", "chunking": {"strategy": "legacy"}, "queries": [
        {"query": question, "index_evidence_available": [True, True, True], "scopes": [{"scope": "global", "chunks": chunks,
          "pools": {"10": [c["id"] for c in chunks], "20": [c["id"] for c in chunks]}, "retrieval_ms": {"10": 1, "20": 2}}]}]}]
    return {"conditions": conditions, "candidate_pool_hash": digest(conditions), "cosine_threshold": .3}


def test_metrics_distinguish_candidate_gate_selection_and_adapter_delivery():
    report = analyze([fixture_pool()])
    rows = [r for r in report["rows"] if r["k"] == 20 and r["budget"] == 1000]
    before = next(r for r in rows if r["policy"] == "top2")
    after = next(r for r in rows if r["policy"] == "novelty")
    assert before["candidate"]["evidence_coverage"] == 1
    assert before["eligible"]["evidence_coverage"] == pytest.approx(2 / 3)
    assert before["final"]["evidence_coverage"] == pytest.approx(1 / 3)
    assert after["final"]["evidence_coverage"] == pytest.approx(2 / 3)
    assert [s["stage"] for s in before["stages"]] == ["delivered_to_adapter", "selection_limit", "filtered_by_original_cosine_threshold"]
    assert all(r["adapter_received"] and r["allocation_compliant"] for r in report["rows"])
    assert before["retrieval_ms_historical_or_single"] == {"global": 2}
    assert not before["k5_is_captured_search"]


def test_pool_hash_prevents_accidental_relabeling_or_candidate_edits():
    pool = fixture_pool()
    pool["conditions"][0]["queries"][0]["scopes"][0]["chunks"][0]["cosine"] = .99
    with pytest.raises(ValueError, match="Frozen"):
        verify(pool)


def test_k5_prefix_is_explicit_and_does_not_invent_scores():
    scope = fixture_pool()["conditions"][0]["queries"][0]["scopes"][0]
    assert [c.chunk_id for c, _ in pairs_for(scope, 5)] == ["a", "copy", "b", "x"]
    with pytest.raises(ValueError, match="Missing"):
        pairs_for(scope, 7)


def test_supplement_freeze_and_source_labels_exist_before_retrieval():
    root = Path("tests/rag/evidence_supplement_v1")
    frozen = json.loads((root / "FREEZE.json").read_text(encoding="utf-8"))
    for name, expected in frozen["sha256"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
    dataset = json.loads((root / "dataset.json").read_text(encoding="utf-8"))
    assert len(dataset["queries"]) == 20
    assert {q["language"] for q in dataset["queries"]} == {"en", "pl", "de"}
    assert sum(bool(q["no_answer"]) for q in dataset["queries"]) == 4
    for q in dataset["queries"]:
        for atom in q["evidence"]:
            alias, relative = atom["document_id"].split("/", 1)
            file = root / ("global" if alias == "@knowledge" else "project") / relative
            assert atom["passage"] in file.read_text(encoding="utf-8")
