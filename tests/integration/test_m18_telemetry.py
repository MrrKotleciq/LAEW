"""Exercise correlated telemetry through a synthetic Workbench execution."""

from http import HTTPStatus
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

import pytest

from laew.agent.executor import StreamCancelled
from laew.operator_cli import dispatch
from laew.telemetry import TelemetrySink, read_run, summarize_run
from laew.web import WorkspaceService


@pytest.fixture
def service_with_trace(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    projects = workspace / "Projects"
    project = projects / "synthetic-project"
    (project / ".git").mkdir(parents=True)
    root = tmp_path / "operator-telemetry"
    root.mkdir(mode=0o700)
    service = WorkspaceService(tmp_path / "manifest.yaml", project, projects,
                               telemetry=TelemetrySink(root))
    monkeypatch.setattr(service, "_ensure_runtime", lambda *_: None)
    monkeypatch.setattr(service, "_register_memory_tool", lambda *_: None)
    monkeypatch.setattr(service, "memory", lambda: None)
    monkeypatch.setattr(service, "knowledge", lambda: None)
    monkeypatch.setattr(service, "_activate_session", lambda *_: None)
    service._model = "synthetic-private-model"
    service._provider_name = "ollama"
    return service, root


def test_workbench_lookup_correlates_attempts_without_persisting_callback_contents(service_with_trace):
    service, root = service_with_trace

    class Executor:
        def run(self, message, *, on_diagnostic, **_options):
            assert message == "synthetic-private-prompt"
            on_diagnostic("provider_request", {"attempt": 1, "tool_results": 0})
            on_diagnostic("provider_outcome", {"status": "failed", "elapsed_ms": 1,
                                                "error_category": "synthetic-private-error"})
            on_diagnostic("provider_request", {"attempt": 2, "tool_results": 0})
            on_diagnostic("provider_dispatch", {})
            on_diagnostic("provider_outcome", {"status": "completed", "elapsed_ms": 3,
                                                "usage": {"input": 9, "output": 0}})
            return SimpleNamespace(success=True, final_response="synthetic-private-response", steps=[],
                                   prompt_tokens=9, completion_tokens=0, total_tokens=9)

    service._executor = Executor()
    status, response = service.chat("synthetic-private-prompt")
    assert status == HTTPStatus.OK
    assert response["response"] == "synthetic-private-response"
    trace, = root.glob("*.jsonl")
    assert "synthetic-private" not in trace.read_text(encoding="utf-8")
    records = read_run(root, trace.stem)["events"]
    assert records[0]["surface"] == "workbench"
    assert records[0]["scope_kind"] == "project"
    assert [record["seq"] for record in records] == list(range(1, len(records) + 1))
    starts = [record for record in records if record["event"] == "llm.started"]
    attempts = [record for record in records if record["event"] == "llm.finished"]
    assert [(a["span_id"], a["attempt"]) for a in starts] == [(a["span_id"], a["attempt"]) for a in attempts]
    assert [a["dispatched"] for a in attempts] == [False, True]
    assert [a["error_code"] for a in attempts] == ["unknown", None]
    summary = summarize_run(root, trace.stem)
    assert summary["attempts"] == 2
    assert summary["usage"]["input"] == {"reported": 9, "estimated": 0, "unavailable": 1}
    assert summary["usage"]["total"]["unavailable"] == 2
    assert [r["status"] for r in records if r["event"] == "run.finished"] == ["completed"]


def test_stream_cancelled_after_dispatch_keeps_one_terminal_record(service_with_trace):
    service, root = service_with_trace
    cancellation = Event()

    class Executor:
        def run(self, message, *, on_diagnostic, **_options):
            on_diagnostic("provider_request", {"attempt": 1, "tool_results": 0})
            on_diagnostic("provider_dispatch", {})
            cancellation.set()
            on_diagnostic("provider_outcome", {"status": "cancelled", "elapsed_ms": 1,
                                                "error_category": "StreamCancelled"})
            raise StreamCancelled()

    service._executor = Executor()
    service.stream_chat("cancel this synthetic turn", "manifest", service._active_project_id,
                        lambda _event: None, cancellation=cancellation)
    trace, = root.glob("*.jsonl")
    records = read_run(root, trace.stem)["events"]
    assert [(r["status"], r["dispatched"]) for r in records if r["event"] == "llm.finished"] == [("cancelled", True)]
    assert [r["status"] for r in records if r["event"] == "run.finished"] == ["cancelled"]


def test_rejected_workbench_message_creates_no_trace(service_with_trace):
    service, root = service_with_trace
    assert service.chat("")[0] == HTTPStatus.UNPROCESSABLE_ENTITY
    assert service.chat("accept me", expected_project_id="wrong-scope")[0] == HTTPStatus.CONFLICT
    assert list(root.iterdir()) == []


def test_operator_diagnoses_failed_run_by_id_and_status(service_with_trace, capsys):
    service, root = service_with_trace
    source = Path(__file__).resolve().parents[2] / "manifests" / "SYSTEM_MANIFEST.yaml"
    service.manifest_path.write_bytes(source.read_bytes())

    class Executor:
        def run(self, message, *, on_diagnostic, **_options):
            on_diagnostic("provider_request", {"attempt": 1, "tool_results": 0})
            on_diagnostic("provider_dispatch", {})
            on_diagnostic("provider_outcome", {"status": "failed", "elapsed_ms": 1,
                                               "error_category": "private-canary"})
            return SimpleNamespace(success=False, steps=[], error="private-canary")

    service._executor = Executor()
    assert service.chat("private-canary")[0] == HTTPStatus.BAD_GATEWAY
    trace, = root.glob("*.jsonl")

    def inspect(args):
        code = dispatch([*args, "--manifest", str(service.manifest_path), "--json"],
                        telemetry_root_resolver=lambda _: root)
        output = capsys.readouterr()
        assert not output.err and "private-canary" not in output.out
        return code, json.loads(output.out)

    code, trace_result = inspect(["telemetry", "show", trace.stem])
    assert code == 0 and trace_result["run_id"] == trace.stem
    assert trace_result["summary"]["status"] == "failed"
    assert trace_result["summary"]["dispatched_attempts"] == 1
    assert trace_result["summary"]["usage"]["input"]["unavailable"] == 1
    code, readiness = inspect(["status"])
    assert code == 1 and readiness["overall"] == "degraded"
    assert any(check["component"] == "provider" and check["reason"] == "not_probed"
               for check in readiness["checks"])
