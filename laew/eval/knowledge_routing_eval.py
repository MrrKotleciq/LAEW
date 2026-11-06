"""Offline Knowledge Routing evaluation with isolated SQLite and Chroma fixtures."""
import argparse
import hashlib
import json
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.eval.memory_sufficiency_eval import FixedAdapter, FixtureEmbedding
from laew.eval.routing_accuracy import RetrievalTrace, summarize_accuracy
from laew.knowledge.routing import KnowledgeTurn
from laew.llm.base import LLMResponse, MessageRole, ToolCall
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.security.permissions import PermissionBroker

FIXTURES = Path("tests/evaluation")
DATASETS = [
    FIXTURES / "memory_sufficiency" / (name + ".json")
    for name in ("validation", "horizon_holdout", "horizon_strategy_holdout")
] + [FIXTURES / "knowledge_routing.json", FIXTURES / "routing_intent.json"]
CONTROL_DATASET = FIXTURES / "routing_accuracy_controls.json"


class ScriptedRagAdapter(FixedAdapter):
    """Issue fixture queries once, then let the fixed response end the turn."""

    native_tools = True

    def __init__(self, queries):
        super().__init__()
        self.queries = queries

    def generate_tools(self, messages, model, tools, **kwargs):
        if self.messages:
            return self.generate(messages, model=model)
        self.messages.append(list(messages))
        return LLMResponse("", model, tool_calls=[
            ToolCall(f"fixture-{index}", "RagTool__query", json.dumps(args))
            for index, args in enumerate(self.queries)
        ])


@contextmanager
def isolated_routing_fixture(cases, root):
    import chromadb

    vault, projects = root / "knowledge", root / "projects"
    active = projects / "active"
    vault.mkdir()
    active.mkdir(parents=True)
    for case in cases:
        for scope, folder in (("global", vault), ("project", active)):
            if case.get(scope):
                (folder / (case["id"] + ".md")).write_text(
                    f"EVIDENCE-{case['id']} {case[scope]}", encoding="utf-8",
                )

    embedding = FixtureEmbedding(cases)
    manifest = {"rag": {"vector_store": {"enabled": True, "global_collection": "routing_eval"}}}
    client = chromadb.PersistentClient(path=str(root / "index"))
    try:
        with patch("laew.rag.vector_store._build_chroma_client", return_value=client):
            general, project = [
                build_rag_tool(manifest, project_root=folder, projects_root=projects,
                               knowledge_root=vault, embedding_service=embedding, general=folder is None)
                for folder in (None, active)
            ]
            synchronize_scope(general._pipeline.knowledge_base, "global")
            synchronize_scope(project._pipeline.knowledge_base, "project")
            yield general, project, embedding
    finally:
        client.close()


def evaluate_cases(cases, root):
    with isolated_routing_fixture(cases, root) as (general, project, embedding):
        return [
            run_case(case, root, project if case.get("in_project") else general, embedding, index)
            for index, case in enumerate(cases)
        ]


def run_case(case, root, tool, embedding, index):
    embedding.current = index
    project_id = "active" if case.get("in_project") else None
    store = MemoryStore(root / (case["id"] + ".db"))
    store.save_settings({"semantic_enabled": False})
    for content in case.get("memory", []):
        store.remember(content)
    memory = MemoryService(store)
    adapter = ScriptedRagAdapter(case["tool_queries"]) if case.get("tool_queries") else FixedAdapter()
    rag = None if case.get("rag_unavailable") else tool
    agent = Agent(AgentConfig(), provider=adapter, tools=[rag] if rag else [])
    for message in case.get("history", []):
        agent.add_message(MessageRole.USER, message)
        agent.add_message(MessageRole.ASSISTANT, "Earlier reply.")
    executor = AgentExecutor(agent)
    broker = PermissionBroker(root / "projects" / "active" if project_id else None)
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    trace = RetrievalTrace()

    def observe(phase, details):
        trace.observe(phase, details)
        turn.observe(phase, details)

    def after_tools(steps, after_order):
        context = turn.after_tools(steps, after_order)
        if context:
            trace.appendices.append(context)
        return context

    started = time.perf_counter()
    pipeline = tool._pipeline
    with (trace.capture(store, pipeline),
          patch.object(pipeline, "max_context_tokens", case.get("rag_context_tokens", pipeline.max_context_tokens))):
        turn.prepare(executor, case["question"], project_id, lambda: memory, rag)
        trace.memory_context = executor.memory_context
        trace.appendices = list(filter(None, (executor.memory_context, executor.knowledge_context)))
        context_size = len(executor.memory_context) + len(executor.knowledge_context)
        result = executor.run(case["question"], on_tool_call=turn.call, on_diagnostic=observe,
                              on_tool_batch=after_tools)
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not result.success or not adapter.messages:
        raise RuntimeError(f"Fixture dispatch failed for {case['id']}")
    system = adapter.messages[0][0].content
    diag = turn.diagnostics
    recall = diag["memory_recall"]
    searches = diag["prefetch"]
    selected = (["memory"] if diag["memory_requested"] else []) + diag["scopes"]
    return {
        "id": case["id"], "required": case["required"], "selected": selected,
        "initial": (["memory"] if diag["memory_requested"] else []) + diag["initial_scopes"],
        "searched": (["memory"] if recall.get("search_executed") else []) +
                    [search["scope"] for search in searches if search.get("search_executed")],
        "memory_status": recall["status"], "memory_invoked": bool(recall.get("invoked")),
        "memory_supplied": recall.get("supplied", 0), "assessment": diag.get("assessment", {}).get("status"),
        "assessment_calls": diag.get("assessment", {}).get("model_assessment", {}).get("calls", 0),
        "reason": diag["reason"], "bound_topic": diag["topic_from_history"],
        "rag_supplied": {search["scope"]: search.get("supplied", 0) for search in searches},
        "rag_status": {search["scope"]: search["status"] for search in searches},
        "evidence": {marker: marker in system for marker in case.get("evidence", [])},
        "unexpected_evidence": [marker for marker in case.get("forbidden", []) if marker in system],
        "routing_ms": diag["routing_ms"], "elapsed_ms": round(elapsed_ms, 2),
        "retrieval_ms": round(recall.get("elapsed_ms", 0) + sum(s.get("elapsed_ms", 0) for s in searches), 2),
        "context_chars": context_size, "adapter_calls": len(adapter.messages),
        "accuracy": trace.assess(case, adapter.messages, turn.snapshot()),
    }


def summarize(rows):
    required = [set(row["required"]) for row in rows]
    selected = [set(row["selected"]) for row in rows]
    scored = [row for row in rows if row["evidence"]]
    required_total = sum(map(len, required))
    selected_total = sum(map(len, selected))
    missed = sum(len(want - got) for want, got in zip(required, selected))
    unnecessary = sum(len(got - want) for want, got in zip(required, selected))
    searched = [set(row["searched"]) for row in rows]
    memory_required = sum("memory" in want for want in required)
    memory_hits = sum("memory" in want and "memory" in got for want, got in zip(required, selected))
    false_memory = sum("memory" not in want and "memory" in got for want, got in zip(required, selected))
    return {
        "cases": len(rows),
        "false_memory_routing_rate": [false_memory, len(rows) - memory_required],
        "memory_routing_recall": [memory_hits, memory_required],
        "routing_recall": [sum(want <= got for want, got in zip(required, selected)), len(rows)],
        "routing_precision": [selected_total - unnecessary, selected_total],
        "missed_retrieval_rate": [missed, required_total],
        "unnecessary_retrieval_rate": [unnecessary, selected_total],
        "required_scopes_without_backend_search": [
            sum(len(want - ran) for want, ran in zip(required, searched)), required_total,
        ],
        "unnecessary_backend_searches": [
            sum(len(ran - want) for want, ran in zip(required, searched)), sum(map(len, searched)),
        ],
        "evidence_coverage": [sum(all(row["evidence"].values()) for row in scored), len(scored)],
        "unexpected_evidence_cases": sum(bool(row["unexpected_evidence"]) for row in rows),
        "memory_invocations": sum(row["memory_invoked"] for row in rows),
        "backend_searches": sum(len(row["searched"]) for row in rows),
        **{key: round(sum(row[key] for row in rows), 2) for key in (
            "routing_ms", "elapsed_ms", "retrieval_ms", "context_chars", "adapter_calls", "assessment_calls",
        )},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    datasets = {}
    with tempfile.TemporaryDirectory(prefix=".routing-eval-", dir=".") as scratch:
        for dataset in [*DATASETS, CONTROL_DATASET]:
            data = dataset.read_bytes()
            cases = json.loads(data.decode("utf-8-sig"))
            if dataset.parent.name == "memory_sufficiency":
                cases = [{
                    **case, "global": case["rag"], "evidence": [case["evidence"]] if case["evidence"] else [],
                    "required": ["memory", "global"] if case["needs_rag"] else ["memory"],
                } for case in cases]
            root = Path(scratch).resolve() / dataset.stem
            root.mkdir()
            rows = evaluate_cases(cases, root)
            datasets[dataset.stem] = {
                "schema_version": 2, "sha256": hashlib.sha256(data).hexdigest(),
                "metrics": summarize(rows), "accuracy": summarize_accuracy(rows), "cases": rows,
            }
    args.output.write_text(json.dumps(datasets, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: {**data["metrics"], "accuracy": data["accuracy"]}
                      for name, data in datasets.items()}, indent=2))


if __name__ == "__main__":
    main()
