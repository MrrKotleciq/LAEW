"""Reviewed, fenced retention of explicitly archived conversation records."""

from contextlib import ExitStack, closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from uuid import UUID

from laew.backup.archive import validate_member_name, verify_archive
from laew.backup.capture import (
    CaptureError, WriterAcknowledgement, _CONVERSATION, _DBS, _acknowledged, _json,
    _mounts, _root, _sources, _stamp, _validate_database,
)
from laew.backup.fence import host_fence
from laew.backup.restore import _check_permissions, _private
from laew.console.session_store import SessionStore, validate_session_name
from laew.knowledge.integration import knowledge_storage_path
from laew.memory.integration import memory_storage_path
from laew.rag.process_lock import CollectionLock


MARKS_FILENAME = "session-archive-marks.json"
_MAX_MARKS = 4096
_HASH = re.compile(r"[0-9a-f]{64}")


class RetentionError(ValueError):
    """Stable reason code suitable for an operator CLI."""


@dataclass(frozen=True)
class SessionRetentionAcknowledgement:
    """Operator attestation that all writers are stopped for the reviewed deletion."""

    writers: WriterAcknowledgement
    review_sha256: str


def _require(condition, code):
    if not condition:
        raise RetentionError(code)


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _utc(value):
    try:
        stamp = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise RetentionError("invalid_timestamp") from None
    _require(stamp.utcoffset() == timedelta(0), "invalid_timestamp")
    return stamp


def _read(path, maximum, mounts, *, private=False):
    info = _root(path, mounts)
    _require(stat.S_ISREG(info.st_mode) and info.st_size <= maximum, "unsafe_input")
    if private:
        _check_permissions(path, info)
    stamp = _stamp(info)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
        _require(len(raw) == info.st_size and _stamp(os.fstat(stream.fileno()))[:5] == stamp[:5]
                 and _stamp(path.lstat()) == stamp, "unstable_input")
    return raw, stamp


def _marks(inventory, path, mounts):
    _require(path == inventory.destination / MARKS_FILENAME, "invalid_marks_location")
    _private(inventory.destination)
    raw, _ = _read(path, 2 << 20, mounts, private=True)
    doc = _json(raw)
    _require(type(doc) is dict and set(doc) == {"schema_version", "profile_id", "host_id", "revision", "marks"}
             and type(doc["schema_version"]) is int and doc["schema_version"] == 1
             and (doc["profile_id"], doc["host_id"]) == (inventory.profile_id, inventory.host_id)
             and type(doc["marks"]) is list and len(doc["marks"]) <= _MAX_MARKS, "invalid_marks")
    _require(str(UUID(doc["revision"])) == doc["revision"], "invalid_marks")
    seen = set()
    for mark in doc["marks"]:
        _require(type(mark) is dict and set(mark) == {"member", "sha256", "archived_at", "pinned", "inactive"}
                 and type(mark["pinned"]) is bool and type(mark["inactive"]) is bool
                 and isinstance(mark["sha256"], str) and _HASH.fullmatch(mark["sha256"]), "invalid_marks")
        name = validate_member_name(mark["member"])
        parts = name.split("/")
        _require(len(parts) == 2 and parts[0] in {"conversations", "sessions_named"}
                 and parts[1].endswith(".json") and name.casefold() not in seen, "invalid_marks")
        validate_session_name(parts[1][:-5])
        seen.add(name.casefold())
        _utc(mark["archived_at"])
    return doc["marks"], _hash(raw)


def _references(sources, mounts):
    refs = set()
    deadline = time.monotonic() + 15
    for key, resolver in (("memory_db", memory_storage_path), ("curation_db", knowledge_storage_path)):
        source = sources.get(key)
        path = source.path if source else resolver(sources["conversations"].path)
        sides = {suffix: path.with_name(path.name + suffix) for suffix in ("-wal", "-shm", "-journal")}
        if source is None:
            _require(not any(os.path.lexists(p) for p in (path, *sides.values())), "database_inventory_changed")
            continue
        info = _root(path, mounts)
        _require(stat.S_ISREG(info.st_mode) and info.st_size <= 2 << 30, "uncertain_references")
        present = {suffix for suffix, p in sides.items() if os.path.lexists(p)}
        _require(not present or present == {"-wal", "-shm"}, "uncertain_references")
        for suffix in present:
            _require(stat.S_ISREG(_root(sides[suffix], mounts).st_mode), "uncertain_references")
        uri = path.as_uri() + ("?mode=ro" if present else "?mode=ro&immutable=1")
        with closing(sqlite3.connect(uri, uri=True, timeout=0.2)) as db:
            db.execute("PRAGMA query_only=ON")
            db.execute("BEGIN")
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            _validate_database(db, key)
            tables = ("memory_sources", "extraction_checkpoints", "extraction_jobs") if key == "memory_db" else (
                "knowledge_checkpoints", "knowledge_jobs")
            for table in tables:
                for (cid,) in db.execute(f"SELECT conversation_id FROM {table} WHERE conversation_id IS NOT NULL"):
                    refs.add(SessionStore._conversation_id(cid))
                    _require(len(refs) <= 100_000 and time.monotonic() < deadline, "uncertain_references")
            if key == "curation_db":
                for size, raw in db.execute("SELECT length(CAST(payload AS BLOB)),"
                                            "CASE WHEN length(CAST(payload AS BLOB))<=2097152 THEN payload END "
                                            "FROM knowledge_proposals"):
                    _require(size <= 2 << 20 and time.monotonic() < deadline, "uncertain_references")
                    proposal = _json(raw)
                    refs.add(SessionStore._conversation_id(proposal["conversation_id"]))
                    _require(type(proposal["sources"]) is list and 0 < len(proposal["sources"]) <= 20,
                             "uncertain_references")
                    for item in proposal["sources"]:
                        refs.add(SessionStore._conversation_id(item["conversation_id"]))
                    _require(len(refs) <= 100_000, "uncertain_references")
    return refs


@contextmanager
def _conversation_leases(path, mounts, *, observe):
    # Match SessionStore.conversation_run and _conversation_lock. Planning
    # probes only existing files. Apply establishes both leases before removal.
    directory = path.parent / ".locks"
    cid = path.stem.removeprefix("conversation-")
    with ExitStack() as leases:
        if os.path.lexists(directory):
            _require(stat.S_ISDIR(_root(directory, mounts).st_mode), "unsafe_lock")
        for kind in ("run", "write"):
            lock_path = directory / f"{cid}.{kind}.lock"
            if os.path.lexists(lock_path):
                _require(stat.S_ISREG(_root(lock_path, mounts).st_mode), "unsafe_lock")
            elif observe:
                continue
            lock = CollectionLock("conversation:" + cid, timeout=0)
            lock.path = lock_path
            lock.acquire()
            leases.callback(lock.release)
        yield


def _inspect(inventory, marks_path, backup_id, now):
    mounts = _mounts()
    sources = _sources(inventory)
    marks, marks_digest = _marks(inventory, Path(marks_path), mounts)
    _require(isinstance(now, datetime) and now.utcoffset() == timedelta(0), "invalid_clock")
    backed = {}
    shared = "sessions_named" not in sources
    def collect(container, manifest):
        _require((manifest["profile_id"], manifest["host_id"]) == (inventory.profile_id, inventory.host_id)
                 and manifest.get("capture", {}).get("shared_session_root") is shared, "backup_identity_mismatch")
        backed.update((row["name"], row["sha256"]) for row in manifest["members"])
    receipt = verify_archive(inventory.destination, backup_id, on_verified=collect)
    for key, filename in _DBS.items():
        _require(key in sources or key + "/" + filename not in backed, "database_inventory_changed")
    refs = _references(sources, mounts)
    ledger, candidates = [], []
    remaining_bytes = 256 << 20
    for mark in sorted(marks, key=lambda row: row["member"]):
        member = mark["member"]
        root, filename = member.split("/")
        _require(root in sources, "ambiguous_session_root")
        path = sources[root].path / filename
        match = _CONVERSATION.fullmatch(path.stem)
        stamp = None
        if not match or root != "conversations":
            reason = "legacy"
        elif mark["pinned"]:
            reason = "pinned"
        elif not mark["inactive"]:
            reason = "active"
        elif now - _utc(mark["archived_at"]) < timedelta(days=90):
            reason = "archive_too_recent"
        elif not shared and os.path.lexists(sources["sessions_named"].path / filename):
            reason = "ambiguous_identity"
        elif not os.path.lexists(path):
            reason = "missing"
        else:
            raw, stamp = _read(path, min(remaining_bytes, 32 << 20), mounts)
            remaining_bytes -= len(raw)
            digest = _hash(raw)
            doc = _json(raw)
            cid = SessionStore._conversation_id(match.group(1))
            SessionStore._validate_conversation_record(doc, cid)
            if digest != mark["sha256"] or _utc(doc["updated_at"]) > _utc(mark["archived_at"]):
                reason = "changed"
            elif doc.get("pinned") is not None and doc["pinned"] is not False:
                reason = "pinned"
            elif any(event["status"] in {"pending", "running"} for event in doc["events"]):
                reason = "pending"
            elif cid in refs:
                reason = "referenced"
            elif backed.get(member) != digest:
                reason = "no_exact_backup"
            else:
                try:
                    with _conversation_leases(path, mounts, observe=True):
                        reason = "eligible"
                        candidates.append((path, stamp))
                except TimeoutError:
                    reason = "active"
        row = dict(item_id=_hash(member.encode()), action="delete" if reason == "eligible" else "keep", reason=reason)
        if reason == "eligible":
            row["source_guard"] = _hash(json.dumps(stamp).encode())
        ledger.append(row)
    plan = dict(schema_version=1, profile_id=inventory.profile_id, host_id=inventory.host_id, backup_id=backup_id,
                archive_sha256=receipt["archive_sha256"], marks_sha256=marks_digest, ledger=ledger)
    plan["review_sha256"] = _hash(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode())
    return plan, candidates


def _writer_deadline(inventory, backup_id, reviewed, acknowledgement):
    _require(isinstance(acknowledgement, SessionRetentionAcknowledgement)
             and isinstance(reviewed, dict)
             and isinstance(acknowledgement.review_sha256, str)
             and _HASH.fullmatch(acknowledgement.review_sha256)
             and acknowledgement.review_sha256 == reviewed.get("review_sha256")
             and isinstance(acknowledgement.writers, WriterAcknowledgement), "writer_acknowledgement_unverified")
    writers = acknowledgement.writers
    try:
        UUID(writers.cut_id)
        return _acknowledged(inventory, backup_id, writers.cut_id, writers)
    except (CaptureError, ValueError, TypeError, AttributeError):
        raise RetentionError("writer_acknowledgement_unverified") from None


def _run(inventory, marks_path, backup_id, now, reviewed, *, apply, acknowledgement=None):
    removed = 0
    try:
        deadline = _writer_deadline(inventory, backup_id, reviewed, acknowledgement) if apply else None
        with host_fence(inventory.fence.parent, mode="maintenance"):
            plan, candidates = _inspect(inventory, marks_path, backup_id, now or datetime.now(timezone.utc))
            if not apply:
                return plan
            # A canonical JSON comparison distinguishes integer versions from boolean values.
            _require(json.dumps(plan, sort_keys=True) == json.dumps(reviewed, sort_keys=True), "reviewed_plan_changed")
            with ExitStack() as leases:
                mounts = _mounts()
                for path, stamp in candidates:
                    leases.enter_context(_conversation_leases(path, mounts, observe=False))
                    _require(_stamp(_root(path, mounts)) == stamp, "candidate_changed")
                for path, stamp in candidates:
                    _require(_stamp(path.lstat()) == stamp, "candidate_changed")
                    _require(time.monotonic() < deadline and datetime.now(timezone.utc) < acknowledgement.writers.valid_until,
                             "writer_acknowledgement_unverified")
                    path.unlink()
                    removed += 1
            return dict(schema_version=1, removed=removed, backup_id=backup_id)
    except Exception as exc:
        if removed:
            raise RetentionError(f"partial_apply_{removed}") from None
        if isinstance(exc, RetentionError):
            raise
        raise RetentionError("retention_unverified") from None


def plan_session_retention(inventory, *, marks_path, backup_id, now=None):
    """Observe marked records and reference stores without deleting or initializing stores."""
    return _run(inventory, marks_path, backup_id, now, None, apply=False)


def apply_session_retention(inventory, *, marks_path, backup_id, reviewed_plan, acknowledgement, now=None):
    """Reverify the reviewed plan under an exclusive fence and remove only eligible files."""
    return _run(inventory, marks_path, backup_id, now, reviewed_plan, apply=True, acknowledgement=acknowledgement)
