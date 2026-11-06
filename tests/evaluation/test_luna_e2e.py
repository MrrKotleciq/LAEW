"""Offline guard and evidence checks for the opt-in OAuth evaluator."""
import json
from types import SimpleNamespace

import pytest

from laew.cloud_chat import CloudError
from laew.eval.luna_e2e import MAX_MODEL_CALLS, MODEL, ObservedAdapter, load_cases
from laew.eval.routing_accuracy import RetrievalTrace
from laew.llm.base import LLMMessage, LLMResponse, MessageRole
from laew.tools.base import ToolResult


def test_fixture_is_small_and_references_are_fixed_before_dispatch():
    cases = load_cases()
    assert len(cases) == len({case["id"] for case in cases}) == 13
    assert {"v20", "v21", "h11", "h18"} <= {case["id"] for case in cases}
    assert all(case["reference"] for case in cases)
    assert {case["tool_probe"] for case in cases if case.get("tool_probe")} == {
        "MemoryTool.recall", "RagTool.query",
    }
    assert [case["id"] for case in cases if case.get("conversation") == "red-case"] == [
        "l06", "l07", "l08", "l09",
    ]


@pytest.mark.parametrize("server_model", [MODEL + "-2026-07-09", "unexpected-model"])
def test_observer_checks_server_model_without_recording_response_internals(server_model):
    transport = SimpleNamespace(_frames=lambda *_: iter([{
        "type": "response.completed", "response": {"model": server_model, "internal": "not reportable"},
    }]))

    def generate(*args, **kwargs):
        list(transport._frames(None, None))
        return LLMResponse("answer", MODEL, total_tokens=10)

    adapter = ObservedAdapter(SimpleNamespace(transport=transport, generate_tools=generate))
    if server_model.startswith(MODEL):
        adapter.generate_tools([LLMMessage(MessageRole.USER, "question")], MODEL, [])
        assert adapter.calls[0]["server_model"] == server_model
        assert adapter.calls[0]["usage"] == {"total_tokens": 10}
    else:
        with pytest.raises(CloudError, match="MODEL_MISMATCH"):
            adapter.generate_tools([], MODEL, [])
        assert adapter.calls[0]["server_model"] is None
    assert "not reportable" not in json.dumps(adapter.calls)


def test_model_call_cap_stops_before_provider_access():
    adapter = ObservedAdapter(None)
    adapter.calls = [{} for _ in range(MAX_MODEL_CALLS)]
    with pytest.raises(CloudError, match="EVAL_BUDGET"):
        adapter.generate_tools([], MODEL, [])


def test_model_initiated_memory_evidence_requires_the_matching_native_observation():
    trace = RetrievalTrace()
    entries = [{"id": "fixture", "scope": "user", "content": "The badge code is C-5819."}]
    trace.observe("tool", {
        "tool": "MemoryTool", "operation": "recall", "call_id": "recall-1",
        "result": ToolResult.ok({"memories": entries}),
    })
    system = LLMMessage(MessageRole.SYSTEM, "Fixture")
    response = json.dumps({"success": True, "data": {"memories": entries}})
    unrelated = LLMMessage(MessageRole.TOOL, response, tool_call_id="old-call")
    matching = LLMMessage(MessageRole.TOOL, response, tool_call_id="recall-1")
    assert trace.delivered([system, unrelated], "") == []
    excerpt, = trace.delivered([system, matching], "")
    assert excerpt.scope == "memory" and excerpt.text == entries[0]["content"]
