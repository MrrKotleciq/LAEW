"""Retention of reviewed traces in a disposable, bounded directory."""

from datetime import datetime, timedelta, timezone
import json
import os

import pytest

from laew.operator_cli import dispatch
from laew.telemetry import TelemetrySink, inspect_telemetry_storage
from laew.telemetry_retention import (
    TelemetryRetentionError,
    apply_telemetry_retention,
    plan_telemetry_retention,
)


_NOW = datetime(2026, 11, 19, tzinfo=timezone.utc)


def _mtime(path, age):
    seconds = (_NOW - age).timestamp()
    os.utime(path, (seconds, seconds))


def test_reviewed_age_boundary_frees_quota_and_preserves_recent_trace(tmp_path):
    sink = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=9216)
    old = sink.start_run("workbench")
    old.finish("completed")
    fresh = sink.start_run("workbench")
    fresh.finish("completed")
    old_file = tmp_path / (old.run_id + ".jsonl")
    fresh_file = tmp_path / (fresh.run_id + ".jsonl")
    _mtime(old_file, timedelta(days=30))
    _mtime(fresh_file, timedelta(days=30, seconds=-1))

    assert inspect_telemetry_storage(tmp_path) == ("degraded", "quota_full")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    plan = plan_telemetry_retention(tmp_path, now=_NOW)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert [item["run_id"] for item in plan["items"] if item["eligible"]] == [old.run_id]
    assert apply_telemetry_retention(tmp_path, plan, now=_NOW)["removed"] == 1
    assert not old_file.exists() and fresh_file.exists()
    assert inspect_telemetry_storage(tmp_path) == ("ok", "cached_storage_available")
    with pytest.raises(TelemetryRetentionError):
        apply_telemetry_retention(tmp_path, plan, now=_NOW)


def test_active_old_trace_is_never_eligible(tmp_path):
    sink = TelemetrySink(tmp_path)
    run = sink.start_run("cli_chat")
    path = tmp_path / (run.run_id + ".jsonl")
    try:
        _mtime(path, timedelta(days=90))
        plan = plan_telemetry_retention(tmp_path, now=_NOW)
        assert [entry["reason"] for entry in plan["items"]] == ["active"]
        assert apply_telemetry_retention(tmp_path, plan, now=_NOW)["removed"] == 0
        assert path.is_file()
    finally:
        run.finish("cancelled", "cancelled")


def test_new_trace_invalidates_review_before_any_delete(tmp_path):
    sink = TelemetrySink(tmp_path)
    run = sink.start_run("cli_tool")
    run.finish("completed")
    old = tmp_path / (run.run_id + ".jsonl")
    _mtime(old, timedelta(days=31))
    reviewed = plan_telemetry_retention(tmp_path, now=_NOW)
    sink.start_run("workflow").finish("completed")
    with pytest.raises(TelemetryRetentionError):
        apply_telemetry_retention(tmp_path, reviewed, now=_NOW)
    assert old.exists()


def test_invalid_trace_and_nonexistent_root_are_protected(tmp_path):
    sink = TelemetrySink(tmp_path)
    run = sink.start_run("console")
    run.finish("failed", "internal_error")
    trace = tmp_path / (run.run_id + ".jsonl")
    trace.write_bytes(b"invalid\n")
    _mtime(trace, timedelta(days=60))
    plan = plan_telemetry_retention(tmp_path, now=_NOW)
    assert plan["items"][0]["reason"] == "unverified"
    assert apply_telemetry_retention(tmp_path, plan, now=_NOW)["removed"] == 0
    missing = tmp_path / "absent"
    with pytest.raises(TelemetryRetentionError):
        plan_telemetry_retention(missing, now=_NOW)
    assert not missing.exists()


def test_emergency_headroom_is_explicit_and_only_selects_oldest_finished(tmp_path):
    sink = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=13312)
    first = sink.start_run("console")
    first.finish("failed", "internal_error")
    second = sink.start_run("console")
    second.finish("completed")
    running = sink.start_run("console")
    paths = [tmp_path / (run.run_id + ".jsonl") for run in (first, second, running)]
    try:
        for path, days in zip(paths, (10, 5, 15)):
            _mtime(path, timedelta(days=days))
        normal = plan_telemetry_retention(tmp_path, now=_NOW)
        assert not any(item["eligible"] for item in normal["items"])
        emergency = plan_telemetry_retention(tmp_path, now=_NOW, emergency_free_slots=1)
        assert emergency["projected_free_slots"] == 1
        assert [(item["run_id"], item["reason"]) for item in emergency["items"] if item["eligible"]] == [
            (first.run_id, "emergency_quota"),
        ]
        with pytest.raises(TelemetryRetentionError):
            apply_telemetry_retention(tmp_path, emergency, now=_NOW)
        assert all(path.exists() for path in paths)
        assert apply_telemetry_retention(tmp_path, emergency, now=_NOW, emergency_free_slots=1)["removed"] == 1
        assert not paths[0].exists() and paths[1].exists() and paths[2].exists()
    finally:
        running.finish("cancelled", "cancelled")


def test_emergency_refuses_incomplete_plan_without_deleting(tmp_path):
    sink = TelemetrySink(tmp_path, max_run_bytes=4096, max_total_bytes=9216)
    run = sink.start_run("workflow")
    path = tmp_path / (run.run_id + ".jsonl")
    try:
        _mtime(path, timedelta(days=5))
        plan = plan_telemetry_retention(tmp_path, now=_NOW, emergency_free_slots=2)
        assert plan["state"] == "insufficient_inactive_traces"
        with pytest.raises(TelemetryRetentionError):
            apply_telemetry_retention(tmp_path, plan, now=_NOW, emergency_free_slots=2)
        assert path.is_file()
    finally:
        run.finish("cancelled", "cancelled")


def test_cli_requires_explicit_review_and_repeated_emergency_scope(tmp_path, capsys):
    root = tmp_path / "traces"
    root.mkdir()
    sink = TelemetrySink(root, max_run_bytes=4096, max_total_bytes=5120)
    run = sink.start_run("console")
    run.finish("completed")
    trace = root / (run.run_id + ".jsonl")
    review = tmp_path / "review.json"

    def call(*args):
        code = dispatch(["retention", *args, "--json"], telemetry_root_resolver=lambda _: root)
        return code, json.loads(capsys.readouterr().out)

    code, normal = call("plan")
    assert code == 0 and not any(item["eligible"] for item in normal["data"]["items"])
    code, emergency = call("plan", "--emergency-free-slots", "1")
    assert code == 0 and emergency["data"]["items"][0]["reason"] == "emergency_quota"
    review.write_text(json.dumps(emergency), encoding="utf-8")
    assert call("apply", "--plan", str(review))[0] == 2
    assert call("apply", "--plan", str(review), "--apply")[0] == 1
    assert trace.is_file()
    args = ("apply", "--plan", str(review), "--apply", "--emergency-free-slots", "1")
    code, result = call(*args)
    assert code == 0 and result["data"]["removed"] == 1
    assert not trace.exists()
    code, result = call(*args)
    assert code == 1 and result["error_code"] == "reviewed_plan_changed"
