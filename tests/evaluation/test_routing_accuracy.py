"""Hand-counted controls for routing, backend execution and adapter evidence."""
import json

import pytest

from laew.eval.knowledge_routing_eval import CONTROL_DATASET, evaluate_cases, summarize
from laew.eval.memory_sufficiency_eval import FixtureEmbedding
from laew.eval.routing_accuracy import Excerpt, RetrievalTrace, summarize_accuracy
from laew.llm.base import LLMMessage, MessageRole
from laew.memory.service import MemoryService


@pytest.fixture
def ephemeral_index(monkeypatch):
    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", lambda **kwargs: chromadb.EphemeralClient())


def test_control_dataset_measures_each_stage(tmp_path, ephemeral_index):
    cases = json.loads(CONTROL_DATASET.read_text(encoding="utf-8"))
    rows = evaluate_cases(cases, tmp_path)
    by_id = {row["id"]: row for row in rows}
    metrics = summarize_accuracy(rows)

    for stage in ("initial_routing", "final_source_selection", "executed_retrieval"):
        assert metrics[f"{stage}_recall"] == [7, 9]
        assert metrics[f"{stage}_precision"] == [7, 7]
    assert metrics["evidence_coverage"] == [4, 8]
    assert metrics["evidence_atom_coverage"] == [6, 10]
    assert metrics["backend_calls_attempted"] == metrics["backend_calls_completed"] == 8
    assert metrics["forbidden_evidence_cases"] == 0

    def accuracy(case_id):
        return by_id[case_id]["accuracy"]

    def outcomes(case_id):
        return {atom["marker"]: atom["outcome"] for atom in accuracy(case_id)["evidence_atoms"]}

    assert {tuple(atom["delivered_in"]) for atom in accuracy("c01")["evidence_atoms"]} == {
        ("global",), ("project",),
    }
    partial = accuracy("c02")["prefetch"][0]
    assert partial["status"] == "found" and partial["supplied"] == 1
    assert partial["fragments"][0]["truncated"]
    assert outcomes("c02") == {"ATOM-NEAR": "delivered", "ATOM-FAR": "found_not_prepared"}

    empty = summarize_accuracy([by_id["c03"]])
    assert empty["initial_routing_recall"] == empty["executed_retrieval_precision"] == [0, 0]
    assert empty["evidence_coverage"] == empty["evidence_atom_coverage"] == [0, 0]
    assert by_id["c04"]["evidence"] == {"Long-Term Memory": True}  # Legacy scaffold false positive.
    assert outcomes("c04") == {"Long-Term Memory": "source_not_selected"}
    assert outcomes("c05") == {"ATOM-RELAY": "selected_without_search"}
    assert accuracy("c05")["prefetch"][0]["status"] == "unavailable"
    assert outcomes("c06") == {"ATOM-UNRECORDED": "searched_without_evidence"}

    duplicate = accuracy("c07")
    cached, filtered = duplicate["follow_up"]
    assert cached["status"] == filtered["status"] == "already supplied"
    assert cached["reused"] and not cached["search_executed"]
    assert not filtered["reused"] and filtered["search_executed"] and filtered["duplicates_omitted"] == 1
    assert duplicate["executed_sources"] == ["global"] and len(duplicate["backend_calls"]) == 2
    assert outcomes("c07") == {"ATOM-GASKET": "delivered"}

    model_search = accuracy("c08")
    assert model_search["final_sources"] == [] and model_search["executed_sources"] == ["global"]
    atom, = model_search["evidence_atoms"]
    assert atom["first_dispatch_in"] == [] and atom["delivered_in"] == ["global"]
    assert model_search["provider_dispatches"] == 2
    assert accuracy("c09")["follow_up"][0]["status"] == "denied" and not accuracy("c09")["backend_calls"]
    assert accuracy("c10")["executed_sources"] == ["memory"] and not accuracy("c10")["prefetch"]
    assert summarize(rows)["evidence_coverage"] == [4, 8]  # Two opposite legacy attribution errors.


def test_pipeline_entry_without_backend_execution(tmp_path, ephemeral_index, monkeypatch):
    def fail_embedding(*args):
        raise RuntimeError("Fixture embedding unavailable")

    monkeypatch.setattr(FixtureEmbedding, "embed", fail_embedding)
    row, = evaluate_cases([{
        "id": "failed", "question": "Check Global Knowledge for the status.",
        "required": ["global"], "global": "The status is ATOM-STATUS.", "evidence": ["ATOM-STATUS"],
    }], tmp_path)
    assert row["searched"] == ["global"]  # Historical flag counts pipeline entry.
    accuracy = row["accuracy"]
    assert accuracy["prefetch"][0]["status"] == "error"
    assert accuracy["executed_sources"] == accuracy["backend_calls"] == []
    assert accuracy["selected_required_without_search"] == ["global"]


def memory_snapshot():
    return {"routing": {"memory_requested": True, "initial_scopes": [], "scopes": [],
                        "memory_recall": {}, "prefetch": [], "follow_up": []}}


def test_prepared_evidence_needs_an_actual_adapter_attachment():
    trace = RetrievalTrace()
    trace.memory_context = MemoryService.context([{"id": "id", "scope": "user", "content": "ATOM-A"}])
    trace.appendices.append(trace.memory_context)
    trace.observe("provider_dispatch", {})
    result = trace.assess(
        {"id": "one", "required": ["memory"], "evidence": ["ATOM-A"]},
        [[LLMMessage(MessageRole.SYSTEM, "Scaffold mentions ATOM-A."), LLMMessage(MessageRole.USER, "ATOM-A")]],
        memory_snapshot(),
    )
    assert result["evidence_atoms"][0]["outcome"] == "prepared_not_delivered"


def test_eligible_reused_evidence_covers_a_source_without_a_new_search():
    trace = RetrievalTrace()
    trace.memory_context = MemoryService.context([{"id": "METADATA", "scope": "user", "content": "ATOM-A"}])
    trace.appendices.append(trace.memory_context)
    trace.observe("provider_dispatch", {})
    result = trace.assess(
        {"id": "one", "required": ["memory"], "evidence": ["ATOM-A"], "forbidden": ["METADATA"]},
        [[LLMMessage(MessageRole.SYSTEM, "Scaffold\n\n" + trace.memory_context)]],
        memory_snapshot(),
    )
    assert result["executed_sources"] == []
    assert result["required_covered_without_search"] == ["memory"]
    assert result["required_without_search_or_evidence"] == result["forbidden_delivered"] == []


def test_a_backend_failure_is_an_attempt_and_not_a_completed_search():
    trace = RetrievalTrace()
    trace.found = [Excerpt("memory", "ATOM-A")]

    def fail():
        raise OSError("Fixture backend unavailable")

    with pytest.raises(OSError):
        trace.search("memory", fail)
    trace.observe("provider_dispatch", {})
    result = trace.assess(
        {"id": "one", "required": ["memory"], "evidence": ["ATOM-B"]},
        [[LLMMessage(MessageRole.SYSTEM, "Scaffold")]],
        memory_snapshot(),
    )
    assert result["backend_calls"] == [
        {"scope": "memory", "call_id": None, "completed": False, "error": "OSError"},
    ]
    assert result["executed_sources"] == []
    assert result["evidence_atoms"][0]["outcome"] == "backend_failed"
