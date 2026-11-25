"""Bounded advisory backup status, separate from private archive and cut evidence."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import stat
import sys
import tempfile

from .archive import _identifier, _json, _parse, _sync_dir, verify_archive
from .fence import FENCE_FILENAME, host_fence
from .inventory import _declared_path, _inspect, _overlap, backup_target_from_profile


STATUS_FILENAME = "status.json"
STATUS_LIMIT = 4096
STATUS_MAX_AGE = timedelta(hours=26)
VERIFIED_MAX_AGE = timedelta(hours=24)
_OUTCOMES = {
    "verified": {"archive_verified"},
    "skipped": {"writer_busy"},
    "failed": {"capture_failed", "archive_verification_failed", "invalid_arguments"},
}


def _require(condition):
    if not condition:
        raise ValueError("Invalid backup worker status.")


def _check_owner(path, owner):
    info = path.lstat()
    if os.name == "nt":
        from laew.security.windows_security import assert_trusted_owned_path
        assert_trusted_owned_path(path, owner)
    else:
        _require(owner == str(info.st_uid) and not info.st_mode & 0o022)
    return info


def _check_ancestry(path, owner):
    """Reject directories whose entries can be replaced by untrusted users."""
    for directory in reversed((path, *path.parents)):
        if os.name == "nt":
            from laew.security.windows_security import get_path_owner_sid, assert_trusted_owned_path
            actual = get_path_owner_sid(directory)
            _require(actual in (owner, "S-1-5-18", "S-1-5-32-544"))
            assert_trusted_owned_path(directory, actual)
        else:
            info = directory.lstat()
            _require(stat.S_ISDIR(info.st_mode) and str(info.st_uid) in (owner, "0"))
            # A root-owned sticky directory protects its trusted-owned children
            # against renames by other users, even if it is world writable.
            _require(not info.st_mode & 0o022 or
                     (info.st_uid == 0 and bool(info.st_mode & stat.S_ISVTX)))


def _status_parent(path, owner):
    _require(path.name == STATUS_FILENAME and path.is_absolute() and ".." not in path.parts)
    _require(_inspect(path.parent) == path.parent and path.parent.is_dir())
    _check_owner(path.parent, owner)
    _check_ancestry(path.parent, owner)


def _timestamp(value):
    _require(type(value) is str)
    stamp = datetime.fromisoformat(value)
    _require(stamp.utcoffset() == timedelta(0) and stamp.isoformat() == value)
    return stamp


def _decode(raw, profile_id, now):
    result = _parse(raw)
    _require(type(result) is dict and set(result) == {
        "schema_version", "profile_id", "observed_at_utc", "last_attempt", "last_verified_at_utc"
    })
    _require(type(result["schema_version"]) is int and result["schema_version"] == 1)
    _require(_identifier(profile_id) and result["profile_id"] == profile_id)
    observed = _timestamp(result["observed_at_utc"])
    _require(observed <= now)
    attempt = result["last_attempt"]
    _require(type(attempt) is dict and set(attempt) == {"operation", "completed_at_utc", "outcome", "reason"})
    _require(attempt["operation"] in ("capture", "verify") and _timestamp(attempt["completed_at_utc"]) <= observed)
    _require(type(attempt["outcome"]) is str and type(attempt["reason"]) is str
             and attempt["reason"] in _OUTCOMES.get(attempt["outcome"], ()))
    verified = result["last_verified_at_utc"]
    if verified is not None:
        _require(_timestamp(verified) <= _timestamp(attempt["completed_at_utc"]))
    _require(attempt["outcome"] != "verified" or verified is not None)
    _require(attempt["operation"] == "capture" or attempt["outcome"] != "skipped")
    return result


def read_status(path, profile_id, owner, now):
    """Read a stable owner-controlled document without opening any archive."""
    path = Path(path)
    _status_parent(path, owner)
    _require(_inspect(path) == path)
    before = _check_owner(path, owner)
    _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= STATUS_LIMIT)
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require(os.path.samestat(before, opened))
        raw = stream.read(STATUS_LIMIT + 1)
    after = path.lstat()
    _require(len(raw) == before.st_size and os.path.samestat(opened, after)
             and before.st_mtime_ns == after.st_mtime_ns and before.st_size == after.st_size)
    return _decode(raw, profile_id, now)


def summarize_status(path, profile_id, owner, now):
    """Return only fields suitable for the Core operator status response."""
    try:
        doc = read_status(path, profile_id, owner, now)
    except (OSError, ValueError, RuntimeError, TypeError):
        return "unknown", "worker_status_unavailable", {}
    if now - _timestamp(doc["observed_at_utc"]) > STATUS_MAX_AGE:
        return "unknown", "status_stale", {}
    attempt = doc["last_attempt"]
    details = {"last_attempt_outcome": attempt["outcome"]}
    verified = doc["last_verified_at_utc"]
    if verified is not None:
        details["age_seconds"] = (now - _timestamp(verified)).total_seconds()
    if attempt["outcome"] != "verified":
        return "degraded", attempt["reason"], details
    if now - _timestamp(verified) > VERIFIED_MAX_AGE:
        return "degraded", "stale_receipt", details
    return "ok", "archive_verified", details


def _publish(path, owner, doc):
    raw = _json(doc)
    _require(len(raw) <= STATUS_LIMIT)
    fd, name = tempfile.mkstemp(prefix=".status-", dir=path.parent)
    stage = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            if os.name != "nt":
                # Match the deployed setgid directory's reader group.
                os.fchmod(stream.fileno(), 0o640)
            _check_owner(stage, owner)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(stage, path)
        _sync_dir(path.parent)
    finally:
        stage.unlink(missing_ok=True)


def _status_outcome(result, target, operation):
    if result["state"] != "ok":
        reason = result.get("error_code")
        if operation == "capture" and reason == "writer_busy":
            return "skipped", "writer_busy", None
        if result["state"] == "invalid":
            return "failed", "invalid_arguments", None
        return "failed", "capture_failed" if operation == "capture" else "archive_verification_failed", None
    try:
        receipt = result["data"]["receipt"]
        if operation == "capture":
            committed = verify_archive(target.destination, receipt["backup_id"])
            _require(committed == receipt)
        _require((receipt["profile_id"], receipt["host_id"]) == (target.profile_id, target.host_id))
        return "verified", "archive_verified", _timestamp(receipt["verified_at"])
    except (OSError, ValueError, KeyError, TypeError):
        return "failed", "archive_verification_failed", None


def run_with_status(path, profile_path, operation, callback):
    """Serialize attempts through one preprovisioned status directory per profile."""
    from laew.operator_cli import _load_inventory, _load_profile
    from .provenance import validate_worker_media

    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        owner = get_current_user_sid()
    else:
        owner = str(os.geteuid())
    path = Path(path)
    _status_parent(path, owner)
    validate_worker_media(profile_path)
    profile = _load_profile(str(profile_path))
    target = backup_target_from_profile(profile)
    source_paths = [profile[key] for key in ("workspace_root", "launch_cwd", "vault", "fence", "manifest_path")]
    source_paths += [profile_path, target.destination, *profile["config_files"].values(),
                     *(profile[key] for key in ("memory_storage", "knowledge_storage") if profile[key])]
    if operation == "capture":
        source_paths.extend(item.path for item in _load_inventory(profile).sources)
    _require(all(not _overlap(path.parent, _declared_path(item)) for item in source_paths))
    _check_owner(path.parent / FENCE_FILENAME, owner)

    def observe(result):
        nonlocal latest
        status, reason, stamp = _status_outcome(result, target, operation)
        if stamp is not None:
            latest = max(latest, stamp) if latest is not None else stamp
        elif reason == "archive_verification_failed" and operation == "verify":
            # The advisory document does not expose generation identifiers.
            latest = None
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "schema_version": 1, "profile_id": target.profile_id, "observed_at_utc": now,
            "last_attempt": {"operation": operation, "completed_at_utc": now, "outcome": status, "reason": reason},
            "last_verified_at_utc": latest.isoformat() if latest is not None else None,
        }
        try:
            _decode(_json(doc), target.profile_id, _timestamp(now))
            _publish(path, owner, doc)
        except (OSError, ValueError, RuntimeError):
            # A status channel failure does not undo a committed archive.
            print("Backup worker status publication failed.", file=sys.stderr)

    with host_fence(path.parent, mode="maintenance"):
        latest = None
        if os.path.lexists(path):
            current = read_status(path, target.profile_id, owner, datetime.now(timezone.utc))
            if current["last_verified_at_utc"] is not None:
                latest = _timestamp(current["last_verified_at_utc"])
        return callback(observe)
