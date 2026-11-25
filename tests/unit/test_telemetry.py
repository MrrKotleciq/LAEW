import json
import subprocess
import sys

from laew.telemetry import TelemetrySink, read_run, summarize_run


def test_safe_trace_and_usage(tmp_path):
    sink = TelemetrySink(tmp_path)
    run = sink.start_run("cli_chat", "project")
    run.emit("tool.finished", tool="RagTool", operation="query", secret="CANARY")
    run.emit("llm.finished", provider="openai-api", input_tokens=7, input_source="reported", output_tokens=99, output_source="unavailable", dispatched=True)
    run.finish("completed")
    trace = read_run(tmp_path, run.run_id)
    assert trace["state"] == "finished"
    assert "CANARY" not in str(trace)
    assert trace["events"][1]["operation"] == "query"
    assert trace["events"][2]["output_tokens"] is None
    usage = summarize_run(tmp_path, run.run_id)["usage"]
    assert usage["input"]["reported"] == 7
    assert usage["output"]["unavailable"] == 1


def test_invalid_values_and_terminal_reservation(tmp_path):
    run = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=8192).start_run([], {})
    for _ in range(100):
        run.emit("tool.finished", status=[], error_code={}, tool="RagTool", operation="CANARY")
    run.finish("completed")
    trace = read_run(tmp_path, run.run_id)
    assert trace["state"] == "finished"
    assert trace["events"][-1]["dropped_events"] > 0
    assert (tmp_path / (run.run_id + ".jsonl")).stat().st_size <= 4096
    assert "CANARY" not in str(trace)


def test_quota_and_missing_root_are_degraded_without_raising(tmp_path):
    sink = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=8192)
    first = sink.start_run("cli_tool")
    second = sink.start_run("cli_tool")
    second.finish("failed")
    assert sink.degraded
    assert not (tmp_path / (second.run_id + ".jsonl")).exists()
    first.finish("completed")
    missing = tmp_path / "missing"
    run = TelemetrySink(missing).start_run("cli_tool")
    run.finish("completed")
    assert not missing.exists()


def test_inconsistent_quota_policy_fails_closed(tmp_path):
    first = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=16384).start_run("cli_chat")
    first.finish("completed")
    sink = TelemetrySink(tmp_path, max_run_bytes=8192, max_total_bytes=16384)
    second = sink.start_run("cli_chat")
    assert sink.degraded
    assert not (tmp_path / (second.run_id + ".jsonl")).exists()


def test_quota_reserves_torn_run_without_trace(tmp_path):
    from uuid import uuid4
    sink = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=9216)
    sink.start_run("workbench").finish("completed")
    (tmp_path / (str(uuid4()) + ".lock")).touch()
    sink.start_run("workbench").finish("completed")
    assert sink.degraded
    assert len(list(tmp_path.glob("*.jsonl"))) == 1


def test_reader_rejects_injected_data_without_creating_files(tmp_path):
    missing = tmp_path / "missing"
    assert read_run(missing, "00000000-0000-4000-8000-000000000000")["state"] == "not_found"
    assert not missing.exists()
    run = TelemetrySink(tmp_path).start_run("cli_chat")
    run.finish("completed")
    path = tmp_path / (run.run_id + ".jsonl")
    records = [json.loads(x) for x in path.read_text().splitlines()]
    records[0]["secret"] = "CANARY"
    path.write_text("\n".join(json.dumps(x) for x in records) + "\n")
    trace = read_run(tmp_path, run.run_id)
    assert trace == {"state": "corrupt", "events": []}


def test_interrupted_trace_after_lease_release(tmp_path):
    run = TelemetrySink(tmp_path).start_run("workbench")
    run._close()  # Simulate OS releasing file handles after a producer crash.
    assert read_run(tmp_path, run.run_id)["state"] == "interrupted"


def test_active_trace_has_a_live_process_lease(tmp_path):
    script = """
import sys
from laew.telemetry import TelemetrySink
run = TelemetrySink(sys.argv[1]).start_run('workbench')
print(run.run_id, flush=True)
sys.stdin.readline()
"""
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        identifier = process.stdout.readline().strip()
        assert read_run(tmp_path, identifier)["state"] == "active"
    finally:
        process.stdin.write("stop\n")
        process.stdin.flush()
        process.wait(timeout=10)
    assert read_run(tmp_path, identifier)["state"] == "interrupted"


def test_manifest_telemetry_config_rejects_invalid_types():
    from laew.manifest import ManifestError, validate_manifest
    import pytest
    # Validation of this optional section runs before workspace internals.
    base = dict(version=1, system_name="x", stage="x", workspace={}, models={}, tools={}, memory={}, rag={})
    for telemetry in ({"enabled": "yes"}, {"enabled": True}, {"root": "relative"}, {"extra": True}):
        with pytest.raises(ManifestError, match="telemetry"):
            validate_manifest({**base, "telemetry": telemetry})
