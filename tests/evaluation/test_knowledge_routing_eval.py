"""Verify routing and evidence at the first Chief adapter dispatch."""
import json

import pytest

from laew.eval.knowledge_routing_eval import DATASETS, evaluate_cases, summarize
from laew.eval.routing_accuracy import summarize_accuracy


@pytest.mark.parametrize("dataset", (*DATASETS[:2], *DATASETS[3:]), ids=lambda path: path.stem)
def test_routing_delivers_required_sources(dataset, tmp_path, monkeypatch):
    cases = json.loads(dataset.read_text(encoding="utf-8-sig"))
    historical = dataset.parent.name == "memory_sufficiency"
    if historical:
        cases = [{
            **case, "global": case["rag"], "evidence": [case["evidence"]],
            "required": ["memory", "global"] if case["needs_rag"] else ["memory"],
        } for case in cases if case["id"] in {"v20", "v21", "h11", "h18"}]

    import chromadb

    # Keep metric regressions independent of on-disk HNSW startup. The
    # standalone report and runtime integration tests use persistent indexes.
    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: chromadb.EphemeralClient())
    rows = evaluate_cases(cases, tmp_path)
    metrics = summarize(rows)
    accuracy = summarize_accuracy(rows)
    assert metrics["missed_retrieval_rate"][0] == 0
    assert metrics["evidence_coverage"][0] == metrics["evidence_coverage"][1]
    assert metrics["unexpected_evidence_cases"] == 0
    assert metrics["assessment_calls"] == 0
    assert metrics["false_memory_routing_rate"][0] == 0
    assert metrics["memory_routing_recall"][0] == metrics["memory_routing_recall"][1]
    assert accuracy["final_source_selection_recall"][0] == accuracy["final_source_selection_recall"][1]
    assert accuracy["evidence_coverage"] == metrics["evidence_coverage"]
    assert accuracy["evidence_atom_coverage"][0] == accuracy["evidence_atom_coverage"][1]
    assert accuracy["forbidden_evidence_cases"] == 0
    for row in rows:
        if not row["required"]:
            assert not row["selected"] and not row["searched"], row["id"]
        elif not row["evidence"]:
            assert row["memory_status"] == "no_results" and row["memory_supplied"] == 0, row["id"]
            assert row["rag_status"] == {"global": "empty"} and row["rag_supplied"] == {"global": 0}, row["id"]
            assert row["accuracy"]["executed_sources"] == ["global"], row["id"]
        if historical:
            assert row["initial"] == ["memory"] and row["memory_supplied"] == 1, row["id"]
            if "global" in row["required"]:
                assert row["rag_supplied"]["global"] > 0, row["id"]
