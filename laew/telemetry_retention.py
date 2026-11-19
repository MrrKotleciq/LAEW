"""Reviewed, age-based cleanup for an operator-owned trace directory."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from laew.telemetry import (
    _LEASE_OFFSET,
    _QUOTA_METADATA_RESERVE,
    _file_info,
    _regular,
    _read_storage_policy,
    _try_lock,
    _unlock,
    _uuid,
    read_run,
)


_AGE = timedelta(days=30)
_MAX_FILES = 2048


class TelemetryRetentionError(ValueError):
    """A trace retention plan or boundary could not be verified."""


class TelemetryPlanChanged(TelemetryRetentionError):
    """The reviewed trace plan no longer matches the verified state."""


def _root(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.drive.startswith("\\\\"):
        raise TelemetryRetentionError("Invalid telemetry root.")
    for entry in (*reversed(path.parents), path):
        info = entry.lstat()
        if (not stat.S_ISDIR(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise TelemetryRetentionError("Invalid telemetry root.")
    return path


def _inventory(root, policy):
    entries = {}
    with os.scandir(root) as directory:
        for index, entry in enumerate(directory):
            if index >= _MAX_FILES:
                raise TelemetryRetentionError("Telemetry inventory exceeds its bound.")
            if entry.name in {".quota.json", ".quota.lock"}:
                continue
            identifier, _, suffix = entry.name.rpartition(".")
            if policy is None or suffix not in {"jsonl", "lock"} or _uuid(identifier) != identifier:
                raise TelemetryRetentionError("Unverified telemetry inventory.")
            info = Path(entry.path).lstat()
            if not _regular(info) or info.st_nlink != 1 or info.st_size > (policy["run_bytes"] if suffix == "jsonl" else 0):
                raise TelemetryRetentionError("Unverified telemetry member.")
            entries.setdefault(identifier, {})[suffix] = info
    return entries


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _item_fingerprint(path, info, lease_info):
    with path.open("rb") as stream:
        if _stamp(os.fstat(stream.fileno()))[:4] != _stamp(info)[:4]:
            raise TelemetryRetentionError("Telemetry member changed.")
        content = stream.read(262145)
        if (len(content) != info.st_size or _stamp(os.fstat(stream.fileno()))[:4] != _stamp(info)[:4] or
                _stamp(path.lstat()) != _stamp(info)):
            raise TelemetryRetentionError("Telemetry member changed.")
    return _digest(json.dumps((_stamp(info), _stamp(lease_info) if lease_info else None,
                               _digest(content)), separators=(",", ":")).encode("ascii"))


def _plan(root, now, emergency_free_slots):
    policy = _read_storage_policy(root)
    inventory = _inventory(root, policy)
    capacity = ((policy["total_bytes"] - _QUOTA_METADATA_RESERVE) // policy["run_bytes"]) if policy is not None else 0
    if emergency_free_slots is not None and (
        type(emergency_free_slots) is not int or not 1 <= emergency_free_slots <= capacity
    ):
        raise TelemetryRetentionError("Invalid emergency headroom.")
    items = []
    recent_finished = []
    for identifier, files in sorted(inventory.items()):
        info = files.get("jsonl")
        if info is None:
            items.append({"run_id": identifier, "eligible": False, "reason": "orphan_lease",
                          "bytes": 0, "last_modified": None, "fingerprint": None})
            continue
        stamp = datetime.fromtimestamp(info.st_mtime, timezone.utc)
        path = root / (identifier + ".jsonl")
        fingerprint = _item_fingerprint(path, info, files.get("lock"))
        recent = stamp > now - _AGE
        if recent and emergency_free_slots is None:
            reason = "within_retention"
        else:
            state = read_run(root, identifier)["state"]
            if state == "active":
                reason = "active"
            elif state == "finished" or (state == "interrupted" and not recent):
                reason = "within_retention" if recent else "age_limit"
            elif state == "interrupted":
                reason = "interrupted_protected"
            else:
                reason = "unverified"
        item = {"run_id": identifier, "eligible": reason == "age_limit", "reason": reason,
                "bytes": info.st_size, "last_modified": stamp.isoformat(), "fingerprint": fingerprint}
        items.append(item)
        if recent and emergency_free_slots is not None and reason == "within_retention" and stamp <= now:
            recent_finished.append(item)
    projected = capacity - len(inventory) + sum(item["eligible"] for item in items)
    state = "ready" if policy is not None else "uninitialized"
    if emergency_free_slots is not None:
        needed = max(0, emergency_free_slots - projected)
        if needed > len(recent_finished):
            state = "insufficient_inactive_traces"
        else:
            recent_finished.sort(key=lambda item: (item["last_modified"], item["run_id"]))
            for item in recent_finished[:needed]:
                item.update(eligible=True, reason="emergency_quota")
            projected += needed
    return {"schema_version": 1, "kind": "telemetry_retention", "max_age_days": _AGE.days,
            "state": state, "emergency_free_slots": emergency_free_slots, "projected_free_slots": max(0, projected),
            "items": items, "eligible_bytes": sum(item["bytes"] for item in items if item["eligible"])}


def _clock(now):
    now = datetime.now(timezone.utc) if now is None else now
    if not isinstance(now, datetime) or now.utcoffset() != timedelta(0):
        raise TelemetryRetentionError("Retention time must be UTC.")
    return now


def plan_telemetry_retention(path, *, now=None, emergency_free_slots=None):
    """Return a reviewable ledger without writing files or taking quota locks."""
    try:
        return _plan(_root(path), _clock(now), emergency_free_slots)
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise TelemetryRetentionError("Telemetry retention plan unavailable.") from exc


def _remove(root, item):
    identifier = item["run_id"]
    trace = root / (identifier + ".jsonl")
    old_lease = root / (identifier + ".lock")
    info, old_info = _file_info(trace), _file_info(old_lease)
    if info is None or _item_fingerprint(trace, info, old_info) != item["fingerprint"]:
        raise TelemetryRetentionError("Reviewed telemetry member changed.")
    path, offset = (old_lease, 0) if old_info is not None else (trace, _LEASE_OFFSET)
    with path.open("r+b") as lease:
        if not _try_lock(lease, offset):
            raise TelemetryRetentionError("Telemetry run is active.")
        try:
            if _item_fingerprint(trace, info, old_info) != item["fingerprint"]:
                raise TelemetryRetentionError("Reviewed telemetry member changed.")
        finally:
            _unlock(lease, offset)
    # Admission remains blocked under the same quota lock. A trace UUID is
    # uniquely created and an inactive writer never reacquires its lease.
    trace.unlink()
    if old_info is not None:
        old_lease.unlink()


def apply_telemetry_retention(path, reviewed_plan, *, now=None, emergency_free_slots=None):
    """Remove only exact approved candidates after revalidation under the quota lock."""
    try:
        root, now = _root(path), _clock(now)
        quota_path = root / ".quota.lock"
        info = _file_info(quota_path)
        if info is None or info.st_nlink != 1 or info.st_size != 0:
            raise TelemetryRetentionError("Telemetry quota lock is unavailable.")
        with quota_path.open("r+b") as quota:
            if not os.path.samestat(info, os.fstat(quota.fileno())) or not _try_lock(quota):
                raise TelemetryRetentionError("Telemetry quota lock is busy.")
            try:
                current = _plan(root, now, emergency_free_slots)
                if (json.dumps(current, sort_keys=True) != json.dumps(reviewed_plan, sort_keys=True) or
                        current["state"] != "ready"):
                    raise TelemetryPlanChanged("Reviewed telemetry plan changed.")
                selected = [item for item in current["items"] if item["eligible"]]
                for item in selected:
                    _remove(root, item)
                return {"schema_version": 1, "kind": "telemetry_retention", "removed": len(selected),
                        "removed_bytes": current["eligible_bytes"]}
            finally:
                _unlock(quota)
    except TelemetryRetentionError:
        raise
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        raise TelemetryRetentionError("Telemetry retention was refused or interrupted.") from exc
