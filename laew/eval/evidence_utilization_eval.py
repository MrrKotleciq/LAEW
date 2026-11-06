"""Opt-in, bounded evidence-use diagnosis through LAEW's existing OAuth adapter."""
import argparse
import hashlib
import json
import tempfile
from dataclasses import replace
from pathlib import Path

from laew.cloud_chat import CloudChatService, CloudError
from laew.eval.knowledge_routing_eval import FIXTURES, isolated_routing_fixture
from laew.eval.luna_e2e import MAX_MODEL_CALLS, MODEL, ObservedAdapter, build_conversation, load_cases, run_case
from laew.llm.base import LLMError, MessageRole


DATASET = FIXTURES / "evidence_utilization.json"
NAMED_REGRESSIONS = ("v21", "v20", "h11", "h18", "l03", "l04", "l05")
REPLAY_VARIANTS = {
    "memory_only": ("memory",),
    "global_only": ("global",),
    "global_then_memory": ("global", "memory"),
}


class CaptureAdapter(ObservedAdapter):
    def generate_tools(self, messages, model, tools, **kwargs):
        if not self.messages:
            self.first_tools = tools
        return super().generate_tools(messages, model, tools, **kwargs)


def replay_input(messages, memory, knowledge, variant):
    """Change only the evidence appendix on the already captured first input."""
    system, *history = messages
    suffix = "\n\n" + memory + "\n\n" + knowledge
    if (system.role != MessageRole.SYSTEM or not memory or not knowledge
            or not system.content.endswith(suffix) or not knowledge.startswith("Relevant Global Knowledge")
            or "\n\n" in knowledge):
        raise ValueError("The v21 input does not have the expected two evidence blocks.")
    sections = {"memory": memory, "global": knowledge}
    appendix = "\n\n".join(sections[source] for source in REPLAY_VARIANTS[variant])
    return [replace(system, content=system.content.removesuffix(suffix) + "\n\n" + appendix), *history]


def replay(adapter, messages, tools, variant, attempt):
    first_call = len(adapter.calls)
    adapter.messages = []
    row = {
        "id": "v21", "variant": variant, "attempt": attempt,
        "reference": ("State that the borrower is unknown or request more evidence."
                      if variant == "memory_only" else "Identify Lena as the camera borrower."),
        "evidence_blocks": list(REPLAY_VARIANTS[variant]),
        "system_sha256": hashlib.sha256(messages[0].content.encode()).hexdigest(),
    }
    try:
        reply = adapter.generate_tools(messages, MODEL, tools)
        row.update(answer=reply.content, requested_tools=[call.name for call in reply.tool_calls])
    except LLMError as exc:
        row["error_code"] = exc.code
    row["model_calls"] = adapter.calls[first_call:]
    return row


def run_baseline(cases, root, adapter, report):
    with isolated_routing_fixture(cases, root) as (general, project, embedding):
        v21 = cases[0]
        conversation = build_conversation(v21, root, general, adapter)
        executor = conversation[0]
        for attempt in range(1, 4):
            executor.agent.reset_history()
            row = run_case(v21, general, adapter, conversation)
            first_input = adapter.messages[0]
            row.update(attempt=attempt, variant="unchanged",
                       system_sha256=hashlib.sha256(first_input[0].content.encode()).hexdigest())
            report["turns"].append(row)
            print(f"v21 unchanged {attempt}: {'completed' if row['success'] else 'failed'}", flush=True)
            if not row["success"]:
                return
            if attempt == 1:
                original = list(first_input)
                tools = adapter.first_tools
                memory, knowledge = executor.memory_context, executor.knowledge_context
                report["captured_v21"] = {
                    "messages": [{"role": message.role.value, "content": message.content} for message in original],
                    "memory_block": memory, "global_block": knowledge,
                }
            else:
                row["matches_first_input"] = first_input == original and adapter.first_tools == tools
        for variant in REPLAY_VARIANTS:
            messages = replay_input(original, memory, knowledge, variant)
            for attempt in range(1, 3):
                row = replay(adapter, messages, tools, variant, attempt)
                report["first_response_probes"].append(row)
                print(f"v21 {variant} {attempt}: {'failed' if 'error_code' in row else 'completed'}", flush=True)
                if "error_code" in row:
                    return
        for index, case in enumerate(cases[1:], start=1):
            embedding.current = index
            rag = project if case.get("in_project") else general
            row = run_case(case, rag, adapter, build_conversation(case, root, rag, adapter))
            report["turns"].append(row)
            print(f"{row['id']}: {'completed' if row['success'] else 'failed'}", flush=True)
            if not row["success"]:
                return


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error("--output must be a new file in an existing directory")
    known = {case["id"]: case for case in load_cases()}
    independent = json.loads(DATASET.read_text(encoding="utf-8"))
    cases = [known["v21"], *independent, *(known[key] for key in NAMED_REGRESSIONS[1:])]
    report = {
        "provider": "chatgpt", "authorization": "existing ChatGPT OAuth registration",
        "model_requested": MODEL, "call_cap": MAX_MODEL_CALLS,
        "turns": [], "first_response_probes": [],
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
        adapter = CaptureAdapter(provider)
        with tempfile.TemporaryDirectory(prefix=".evidence-eval-", dir=".") as scratch:
            run_baseline(cases, Path(scratch).resolve(), adapter, report)
    except LLMError as exc:
        report["error_code"] = exc.code
    finally:
        cloud.close()
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
            output.write("\n")
    complete = (len(report["turns"]) == len(cases) + 2
                and all(row["success"] for row in report["turns"])
                and len(report["first_response_probes"]) == 6
                and not any("error_code" in row for row in report["first_response_probes"]))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
