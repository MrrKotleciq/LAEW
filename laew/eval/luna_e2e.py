"""Opt-in, bounded GPT-5.6 Luna evaluation through the existing ChatGPT OAuth provider."""
import argparse
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.cloud_chat import CloudChatService, CloudError
from laew.eval.knowledge_routing_eval import FIXTURES, isolated_routing_fixture
from laew.eval.routing_accuracy import RetrievalTrace, summarize_accuracy
from laew.knowledge.routing import KnowledgeTurn
from laew.llm.base import LLMError
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore
from laew.memory.tool import MemoryTool
from laew.security.permissions import PermissionBroker
from laew.tools.base import ErrorCode, ToolResult

MODEL = "gpt-5.6-luna"
DATASET = FIXTURES / "luna_e2e.json"
MAX_MODEL_CALLS = 22


def load_cases():
    spec = json.loads(DATASET.read_text(encoding="utf-8"))
    historical = {}
    for entry in spec["historical"]:
        dataset = FIXTURES / "memory_sufficiency" / (entry["dataset"] + ".json")
        original = next(case for case in json.loads(dataset.read_text(encoding="utf-8-sig"))
                        if case["id"] == entry["id"])
        historical[entry["id"]] = {
            "id": entry["id"], "dataset": entry["dataset"], "reference": entry["reference"],
            "question": original["question"], "memory": original["memory"], "global": original["rag"],
            "evidence": [original["evidence"]],
            "required": ["memory", "global"] if original["needs_rag"] else ["memory"],
        }
    independent = spec["independent"]
    return independent[:2] + list(historical.values()) + independent[2:]


class ObservedAdapter:
    """Record adapter input and safe response metadata while using the real provider."""

    native_tools = True
    manages_retries = True

    def __init__(self, provider):
        self.provider = provider
        self.messages = []
        self.calls = []

    def is_available(self):
        return self.provider.is_available()

    def generate_tools(self, messages, model, tools, **kwargs):
        self.messages.append(list(messages))
        if len(self.calls) >= MAX_MODEL_CALLS:
            raise CloudError("EVAL_BUDGET", "The evaluation model call cap was reached.")
        record = {
            "message_chars": sum(len(message.content) for message in messages),
            "tool_schema_chars": len(json.dumps(tools, ensure_ascii=False)),
            "server_model": None,
        }
        self.calls.append(record)
        frames = self.provider.transport._frames

        def inspect_frames(response, cancellation):
            for frame in frames(response, cancellation):
                if frame.get("type") == "response.completed":
                    identity = frame.get("response", {}).get("model")
                    if identity:
                        if not re.fullmatch(r"gpt-5\.6-luna(?:-\d{4}-\d{2}-\d{2})?", identity):
                            record["server_model_mismatch"] = True
                            raise CloudError("MODEL_MISMATCH", "The response used a different model.")
                        record["server_model"] = identity
                yield frame

        started = time.perf_counter()
        try:
            with patch.object(self.provider.transport, "_frames", inspect_frames):
                reply = self.provider.generate_tools(messages, model, tools, **kwargs)
            record["usage"] = {key: value for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                               if (value := getattr(reply, key)) is not None}
            return reply
        except LLMError as exc:
            record["error_code"] = exc.code
            raise
        finally:
            record["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)


def build_conversation(case, root, rag, adapter):
    project_id = "active" if case.get("in_project") else None
    store = MemoryStore(root / (case.get("conversation", case["id"]) + ".db"))
    store.save_settings({"semantic_enabled": False})
    for content in case.get("memory", []):
        store.remember(content)
    service = MemoryService(store)
    memory = MemoryTool(service, project_id)
    memory.operations = {"recall": memory.operations["recall"]}
    agent = Agent(
        AgentConfig(model=MODEL, name="laew-web-chief", project_scope=bool(project_id), max_iterations=3),
        provider=adapter, tools=[rag, memory],
    )
    broker = PermissionBroker(root / "projects" / "active" if project_id else None, "restricted")
    return AgentExecutor(agent), broker, service, project_id


def run_case(case, rag, adapter, conversation):
    executor, broker, memory, project_id = conversation
    trace = RetrievalTrace()
    adapter.messages = []
    first_call = len(adapter.calls)

    def call(tool, operation, args):
        if (tool.name, operation) not in {("MemoryTool", "recall"), ("RagTool", "query")}:
            return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Only fixture retrieval is available.")
        return broker.call(tool, operation, args, None)

    turn = KnowledgeTurn(call)

    def observe(phase, details):
        trace.observe(phase, details)
        turn.observe(phase, details)

    def after_tools(steps, after_order):
        context = turn.after_tools(steps, after_order)
        if context:
            trace.appendices.append(context)
        return context

    started = time.perf_counter()
    with trace.capture(memory.store, rag._pipeline):
        turn.prepare(executor, case["question"], project_id, lambda: memory, rag)
        trace.memory_context = executor.memory_context
        trace.appendices = list(filter(None, (executor.memory_context, executor.knowledge_context)))
        result = executor.run(case["question"], on_tool_call=turn.call, on_diagnostic=observe,
                              on_tool_batch=after_tools)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    snapshot = turn.snapshot()
    accuracy = trace.assess(case, adapter.messages, snapshot)
    searched, required = set(accuracy["executed_sources"]), set(case["required"])
    calls = adapter.calls[first_call:]
    row = {
        "id": case["id"], "dataset": case.get("dataset", "independent"),
        "conversation": case.get("conversation"), "question": case["question"],
        "reference": case["reference"], "abstention_expected": case.get("abstention", False),
        "tool_probe": case.get("tool_probe"), "required": case["required"],
        "forbidden": case.get("forbidden", []), "success": result.success,
        "answer": result.final_response if result.success else None,
        "bound_topic": snapshot["routing"]["topic_from_history"],
        "source_policy": {key: snapshot["routing"][key] for key in (
            "memory_only", "memory_excluded", "only_scope", "excluded_scopes", "rag_disabled",
        )},
        "missing_searches": sorted(required - searched), "extra_searches": sorted(searched - required),
        "accuracy": accuracy, "diagnostic_tools": snapshot["tools"],
        "elapsed_ms": elapsed, "model_calls": calls,
        "retrieved_context_chars": len(executor.memory_context) + len(executor.knowledge_context),
    }
    row["retrieval_quality"] = {key: value for key, value in summarize_accuracy([row]).items()
                                if key.endswith("_recall") or key == "evidence_atom_coverage"}
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--live", action="store_true", required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("--output must be a new file in an existing directory")
    cases = load_cases()
    rows = []
    report = {
        "model_requested": MODEL, "provider": "chatgpt", "authorization": "existing ChatGPT OAuth registration",
        "mode": "native read-only Chief Agent",
        "model_call_limit": MAX_MODEL_CALLS, "planned_cases": [case["id"] for case in cases],
        "fixture_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(), "cases": rows,
    }
    cloud = CloudChatService()
    try:
        accounts = [account for account in cloud.auth.status()["accounts"] if account["authenticated"]]
        if len(accounts) != 1:
            raise CloudError("EVAL_ACCOUNT", "Exactly one authenticated LAEW ChatGPT registration is required.")
        provider = cloud.provider("chatgpt", accounts[0]["id"], timeout=45)
        report["catalog_verified"] = MODEL in provider.list_models()
        if not report["catalog_verified"]:
            raise CloudError("MODEL_UNAVAILABLE", "The exact requested model is absent from the account catalog.")
        adapter = ObservedAdapter(provider)
        with tempfile.TemporaryDirectory(prefix=".luna-eval-", dir=".") as scratch:
            root = Path(scratch).resolve()
            with isolated_routing_fixture(cases, root) as (general, project, embedding):
                conversations = {}
                for index, case in enumerate(cases):
                    embedding.current = index
                    rag = project if case.get("in_project") else general
                    group = case.get("conversation", case["id"])
                    if group not in conversations:
                        conversations[group] = build_conversation(case, root, rag, adapter)
                    row = run_case(case, rag, adapter, conversations[group])
                    rows.append(row)
                    print(f"{row['id']}: {'completed' if row['success'] else 'failed'}, "
                          f"{len(row['model_calls'])} model calls", flush=True)
                    if not row["success"]:
                        break
        completed = [row for row in rows if row["success"]]
        report["retrieval"] = summarize_accuracy(completed)
        report["retrieval_excluding_tool_probes"] = summarize_accuracy(
            [row for row in completed if not row["tool_probe"]],
        )
    except LLMError as exc:
        report["error_code"] = exc.code
    finally:
        cloud.close()
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    return 0 if len(rows) == len(cases) and all(row["success"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
