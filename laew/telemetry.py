"""Fixture-only, bounded local telemetry primitives.

This module does not establish an OS security boundary. Production wiring must
first verify a separately provisioned protected profile and disjoint roots.
"""
from __future__ import annotations

import json
import errno
import logging
import os
from pathlib import Path
import stat
import threading
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4
from laew.tools.base import _LOG_OPERATIONS

_LOG = logging.getLogger("laew.telemetry")
_SURFACES = frozenset("cli_chat cli_tool workflow multiagent console workbench cloud_chat memory_worker curation_worker".split())
_SCOPES = frozenset(("none", "global", "project"))
_EVENTS = frozenset("run.started routing.decided agent.started agent.finished tool.started tool.finished llm.started llm.finished runtime.sample run.finished".split())
_ERRORS = frozenset("validation permission_denied timeout dependency_unavailable io_error cancelled internal_error unknown".split())
_STATUSES = frozenset("started completed failed cancelled unknown".split())
_FIELDS = {
    "route": frozenset(("none", "global", "project", "both")),
    "role": frozenset(("primary", "reviewer", "worker", "coordinator", "unknown")),
    "tool": frozenset(_LOG_OPERATIONS) | {"unknown"},
    "operation": frozenset().union(*_LOG_OPERATIONS.values()) | {"unknown"},
    "decision": frozenset(("allowed", "denied", "unknown")),
    "provider": frozenset(("ollama", "llamacpp", "gemini", "openai-api", "chatgpt", "fake", "unknown")),
    **{f"{x}_source": frozenset(("reported", "estimated", "unavailable")) for x in ("input", "output", "total")},
}
_EVENT_FIELDS = {
    "routing.decided": {"route", "enabled"},
    "agent.started": {"role", "attempt"}, "agent.finished": {"role", "attempt"},
    "tool.started": {"tool", "operation", "decision", "executed", "reused"}, "tool.finished": {"tool", "operation", "decision", "executed", "reused"},
    "llm.started": {"provider", "attempt", "dispatched"},
    "llm.finished": {"provider", "attempt", "dispatched", "input_tokens", "output_tokens", "total_tokens", "input_source", "output_source", "total_source"},
    "runtime.sample": set(),
}
_TERMINAL_RESERVE = 2048
_QUOTA_METADATA_RESERVE = 1024
_LEASE_OFFSET = 262144  # Outside any byte that belongs to a trace.
_PROCESS_LOCK = threading.RLock()


def _regular(info):
    return (stat.S_ISREG(info.st_mode) and
            not getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _file_info(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not _regular(info):
        raise OSError("invalid")
    return info


def _reserve_slot(root, run_bytes, total_bytes):
    # DirEntry.stat reuses enumeration metadata on Windows. Reserve space for
    # leases left behind if a process dies before creating its trace as well.
    ids = set()
    with os.scandir(root) as entries:
        for entry in entries:
            if entry.name in {".quota.json", ".quota.lock"}:
                continue
            identifier, _, extension = entry.name.rpartition(".")
            if len(identifier) != 36 or extension not in ("jsonl", "lock"):
                raise OSError("invalid")
            info = entry.stat(follow_symlinks=False)
            limit = run_bytes if extension == "jsonl" else 0
            if not _regular(info) or info.st_size > limit:
                raise OSError("invalid")
            ids.add(identifier)
            if (len(ids) + 1) * run_bytes + _QUOTA_METADATA_RESERVE > total_bytes:
                raise OSError("quota")


def _uuid(value: object) -> str | None:
    if type(value) is not str:
        return None
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _try_lock(file, offset=0) -> bool:
    try:
        if os.name == "nt":
            import msvcrt
            file.seek(offset)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            return False
        raise


def _unlock(file, offset=0) -> None:
    if os.name == "nt":
        import msvcrt
        file.seek(offset)
        msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)


def _fault() -> None:
    # Never include exception text or paths in operational diagnostics.
    try:
        _LOG.warning("telemetry_degraded")
    except Exception:
        # A broken logging handler must not alter the user's work either.
        pass


class TelemetrySink:
    """Direct fixture backend; the caller must supply an existing private root."""

    def __init__(self, root: str | Path, *, max_run_bytes: int = 262144,
                 max_total_bytes: int = 268435456, announce: bool = False):
        self.root = Path(root)
        self.max_run_bytes = max_run_bytes
        self.max_total_bytes = max_total_bytes
        self.degraded = False
        self._announce = announce
        self._policy_stamp = None
        if (type(max_run_bytes) is not int or type(max_total_bytes) is not int or
                not 4096 <= max_run_bytes <= 262144 or
                not max_run_bytes + _QUOTA_METADATA_RESERVE <= max_total_bytes <= 268435456):
            raise ValueError("invalid telemetry quotas")

    def start_run(self, surface: str, scope_kind: str = "none") -> TelemetryRun:
        run = TelemetryRun(self, surface if type(surface) is str and surface in _SURFACES else "unknown",
                           scope_kind if type(scope_kind) is str and scope_kind in _SCOPES else "none")
        run._start()
        return run


class TelemetryRun:
    def __init__(self, sink: TelemetrySink, surface: str, scope_kind: str):
        self.sink = sink
        self.run_id = str(uuid4())
        self.span_id = str(uuid4())
        self.surface, self.scope_kind = surface, scope_kind
        self._file = None
        self._seq = 0
        self._bytes = 0
        self._dropped = 0
        self._finished = False
        self._start_time = time.monotonic()
        self._mutex = threading.RLock()

    def _degrade(self):
        self.sink.degraded = True
        _fault()

    def _start(self):
        # Conservative reservation: each retained trace consumes one whole
        # run quota. This bounds active and inactive files without a ledger.
        try:
            root = self.sink.root
            info = root.lstat() if root.is_absolute() else None
            if (info is None or not stat.S_ISDIR(info.st_mode) or
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise OSError("unavailable")
            with _PROCESS_LOCK:
                quota_path = root / ".quota.lock"
                _file_info(quota_path)
                with quota_path.open("a+b") as quota:
                    if not _try_lock(quota):
                        raise OSError("busy")
                    try:
                        policy = root / ".quota.json"
                        expected = {"version": 1, "run_bytes": self.sink.max_run_bytes,
                                    "total_bytes": self.sink.max_total_bytes}
                        info = _file_info(policy)
                        if info is not None:
                            stamp = (info.st_dev, info.st_ino, info.st_size, info.st_ctime_ns, info.st_mtime_ns,
                                     self.sink.max_run_bytes, self.sink.max_total_bytes)
                            if self.sink._policy_stamp != stamp:
                                with policy.open("rb") as f:
                                    data = f.read(_QUOTA_METADATA_RESERVE + 1)
                                if len(data) > _QUOTA_METADATA_RESERVE or json.loads(data) != expected:
                                    raise OSError("policy")
                                self.sink._policy_stamp = stamp
                        else:
                            if next(root.glob("*.jsonl"), None) is not None:
                                raise OSError("missing policy")
                            with policy.open("xb") as f:
                                f.write(json.dumps(expected, separators=(",", ":")).encode("ascii"))
                        _reserve_slot(root, self.sink.max_run_bytes, self.sink.max_total_bytes)
                        self._file = (root / (self.run_id + ".jsonl")).open("x+b")
                        if not _try_lock(self._file, _LEASE_OFFSET):
                            raise OSError("lease")
                        self._file.seek(0)
                    finally:
                        _unlock(quota)
            self._write("run.started", status="started", flush=True)
            if self._seq == 1 and self.sink._announce:
                try:
                    _LOG.info("telemetry_run %s", self.run_id)
                except Exception:
                    pass
        except (OSError, ValueError, TypeError):
            self._degrade()
            self._close()

    def _write(self, event: str, *, status=None, error_code=None, duration_ms=None,
               span_id=None, parent_span_id=None, flush=False, **fields):
        if self._file is None:
            return
        status = status if type(status) is str and status in _STATUSES else None
        error_code = error_code if type(error_code) is str and error_code in _ERRORS else ("unknown" if error_code is not None else None)
        if status in ("completed", "started"):
            error_code = None
        record = {"schema_version": 1, "ts": datetime.now(timezone.utc).isoformat(),
                  "event": event, "run_id": self.run_id, "seq": self._seq + 1,
                  "surface": self.surface, "scope_kind": self.scope_kind, "scope_ref": None,
                  "span_id": _uuid(span_id) or self.span_id, "parent_span_id": _uuid(parent_span_id),
                  "duration_ms": duration_ms if type(duration_ms) in (int, float) and 0 <= duration_ms <= 1e12 else None,
                  "status": status, "error_code": error_code}
        for key in _EVENT_FIELDS.get(event, set()):
            if key not in fields:
                continue
            value = fields[key]
            if key in _FIELDS:
                record[key] = value if isinstance(value, str) and value in _FIELDS[key] else ("unavailable" if key.endswith("_source") else "unknown")
            elif key in ("enabled", "dispatched", "executed", "reused"):
                record[key] = value if isinstance(value, bool) else False
            else:
                record[key] = value if type(value) is int and 0 <= value <= 2**53 else None
        if event.startswith("tool.") and "operation" in record:
            if record["operation"] not in _LOG_OPERATIONS.get(record.get("tool"), ()):
                record["operation"] = "unknown"
        if event == "llm.finished":
            for kind in ("input", "output", "total"):
                source, count = kind + "_source", kind + "_tokens"
                if record.get(source) not in ("reported", "estimated") or record.get(count) is None:
                    record[source], record[count] = "unavailable", None
        if event == "run.finished":
            record["dropped_events"] = self._dropped
        data = (json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        limit = self.sink.max_run_bytes if event == "run.finished" else self.sink.max_run_bytes - _TERMINAL_RESERVE
        if self._bytes + len(data) > limit:
            self._dropped += 1
            return
        try:
            self._file.write(data)
            self._bytes += len(data)
            self._seq += 1
            if flush:
                self._file.flush()
        except OSError:
            self._degrade()
            self._close()

    def emit(self, event: str, *, status=None, error_code=None, duration_ms=None,
             span_id=None, parent_span_id=None, **fields):
        with self._mutex:
            if not self._finished and type(event) is str and event in _EVENTS - {"run.started", "run.finished"}:
                self._write(event, status=status, error_code=error_code, duration_ms=duration_ms,
                            span_id=span_id, parent_span_id=parent_span_id, **fields)

    def finish(self, status: str, error_code=None):
        with self._mutex:
            if self._finished:
                return
            self._finished = True
            status = status if type(status) is str and status in ("completed", "failed", "cancelled") else "failed"
            self._write("run.finished", status=status, error_code=error_code,
                        duration_ms=(time.monotonic() - self._start_time) * 1000, flush=True)
            self._close()

    def _close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                self._degrade()
            self._file = None


_ENVELOPE = frozenset(("schema_version", "ts", "event", "run_id", "seq", "surface", "scope_kind", "scope_ref", "span_id", "parent_span_id", "duration_ms", "status", "error_code"))


def _valid_record(record: object, identifier: str, seq: int) -> bool:
    if type(record) is not dict:
        return False
    event = record.get("event")
    if type(event) is not str or event not in _EVENTS:
        return False
    extra = _EVENT_FIELDS.get(event, set()) | ({"dropped_events"} if event == "run.finished" else set())
    if not _ENVELOPE <= record.keys() or record.keys() - _ENVELOPE - extra:
        return False
    if type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["run_id"] != identifier or type(record["seq"]) is not int or record["seq"] != seq:
        return False
    if type(record["ts"]) is not str or len(record["ts"]) > 40:
        return False
    try:
        timestamp = datetime.fromisoformat(record["ts"])
        if timestamp.utcoffset() != timezone.utc.utcoffset(timestamp):
            return False
    except ValueError:
        return False
    if record["surface"] not in _SURFACES | {"unknown"} or record["scope_kind"] not in _SCOPES or record["scope_ref"] is not None:
        return False
    if _uuid(record["span_id"]) != record["span_id"] or (record["parent_span_id"] is not None and _uuid(record["parent_span_id"]) != record["parent_span_id"]):
        return False
    duration = record["duration_ms"]
    if duration is not None and (type(duration) not in (int, float) or not 0 <= duration <= 1e12):
        return False
    if record["status"] is not None and (type(record["status"]) is not str or record["status"] not in _STATUSES):
        return False
    if record["error_code"] is not None and (type(record["error_code"]) is not str or record["error_code"] not in _ERRORS):
        return False
    for key in extra & record.keys():
        value = record[key]
        if key in _FIELDS:
            if type(value) is not str or value not in _FIELDS[key]:
                return False
        elif key in ("enabled", "dispatched", "executed", "reused"):
            if type(value) is not bool:
                return False
        elif value is not None and (type(value) is not int or not 0 <= value <= 2**53):
            return False
    if event.startswith("tool.") and record.get("operation", "unknown") not in _LOG_OPERATIONS.get(record.get("tool"), ()) and record.get("operation", "unknown") != "unknown":
        return False
    return True


def read_run(root: str | Path, run_id: str) -> dict:
    """Read an existing trace without provisioning files or directories."""
    identifier = _uuid(run_id)
    if identifier is None or identifier != run_id:
        return {"state": "invalid", "events": []}
    root = Path(root)
    path, lease_path = root / (identifier + ".jsonl"), root / (identifier + ".lock")
    if not path.exists():
        return {"state": "not_found", "events": []}
    try:
        if root.is_symlink() or path.is_symlink() or lease_path.is_symlink() or path.stat().st_size > 262144:
            raise ValueError("invalid")
        with path.open("rb") as f:
            data = f.read(262145)
        if len(data) > 262144 or not data.endswith(b"\n"):
            raise ValueError("invalid")
        records = [json.loads(line) for line in data.splitlines()]
        if not records or any(not _valid_record(r, identifier, i + 1) for i, r in enumerate(records)):
            raise ValueError("invalid")
        if records[0]["event"] != "run.started" or any(r["event"] == "run.started" for r in records[1:]) or any(r["event"] == "run.finished" for r in records[:-1]):
            raise ValueError("invalid")
        if records[-1]["event"] == "run.finished":
            state = "finished"
        else:
            # Earlier fixture traces used a separate lease file.
            lease_path, offset = (lease_path, 0) if lease_path.exists() else (path, _LEASE_OFFSET)
            with lease_path.open("r+b") as lease:
                if _try_lock(lease, offset):
                    _unlock(lease, offset)
                    state = "interrupted"
                else:
                    state = "active"
        return {"state": state, "events": records}
    except OSError:
        return {"state": "unknown", "events": []}
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
        return {"state": "corrupt", "events": []}


def summarize_run(root: str | Path, run_id: str) -> dict:
    trace = read_run(root, run_id)
    return summarize_events(trace["events"], trace["state"])


def summarize_events(events, state):
    """Aggregate already validated records from the same trace read."""
    result = {"state": state, "event_count": len(events), "attempts": 0, "dispatched_attempts": 0,
              "dropped_events": 0, "usage": {}, "status": None, "duration_ms": None}
    for kind in ("input", "output", "total"):
        usage = {"reported": 0, "estimated": 0, "unavailable": 0}
        for event in events:
            if event.get("event") != "llm.finished":
                continue
            source, count = event.get(kind + "_source"), event.get(kind + "_tokens")
            if source in ("reported", "estimated") and type(count) is int and count >= 0:
                usage[source] += count
            else:
                usage["unavailable"] += 1
        result["usage"][kind] = usage
    result["attempts"] = sum(e.get("event") == "llm.finished" for e in events)
    result["dispatched_attempts"] = sum(e.get("event") == "llm.finished" and e.get("dispatched") is True
                                       for e in events)
    if events and events[-1].get("event") == "run.finished":
        result["dropped_events"] = events[-1].get("dropped_events", 0)
        result["status"] = events[-1].get("status")
        result["duration_ms"] = events[-1].get("duration_ms")
    return result
