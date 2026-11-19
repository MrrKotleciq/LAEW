from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from uuid import uuid4

import pytest

from laew.backup.archive import seal_archive
from laew.backup.capture import WriterAcknowledgement
from laew.backup.fence import FENCE_FILENAME, host_fence
from laew.backup.inventory import Inventory, Source
from laew.console.session_store import SessionStore
from laew.knowledge.store import KnowledgeStore
from laew.memory.store import MemoryStore
from laew.retention import (
    MARKS_FILENAME, RetentionError, SessionRetentionAcknowledgement, apply_session_retention, plan_session_retention,
)


def dump(path, doc):
    path.write_text(json.dumps(doc), encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o600)


def apply_review(inventory, plan, **options):
    owners = frozenset({"fixture"})
    writers = WriterAcknowledgement(inventory.profile_id, inventory.host_id, options["backup_id"], str(uuid4()),
                                    owners, owners, True, True, datetime.now(timezone.utc) + timedelta(minutes=1))
    acknowledgement = SessionRetentionAcknowledgement(writers, plan["review_sha256"])
    return apply_session_retention(inventory, reviewed_plan=plan, acknowledgement=acknowledgement, **options)


@pytest.fixture
def fixture(tmp_path):
    media, sessions, vault, lock = (tmp_path / p for p in ("media", "sessions", "vault", "lock"))
    for path in (media, sessions, vault, lock):
        path.mkdir(mode=0o777 if os.name == "nt" else 0o700)
    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        subprocess.run(["icacls", str(media), "/inheritance:r", "/grant:r",
                        f"*{get_current_user_sid()}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                        "*S-1-5-32-544:(OI)(CI)F"], check=True, capture_output=True)
    fence = lock / FENCE_FILENAME
    fence.touch()
    doc = SessionStore(sessions).create_conversation("general", None)
    # Fix the clock so the exact 90-day boundary is deterministic.
    stamp = datetime(2025, 12, 10, tzinfo=timezone.utc)
    doc.update(created_at=stamp.isoformat(), updated_at=stamp.isoformat())
    path = sessions / ("conversation-" + doc["id"] + ".json")
    dump(path, doc)
    member = "conversations/" + path.name
    mark = dict(member=member, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                archived_at=stamp.isoformat(), pinned=False, inactive=True)
    marks = dict(schema_version=1, profile_id="fixture", host_id="host", revision=str(uuid4()), marks=[mark])
    sidecar = media / MARKS_FILENAME
    dump(sidecar, marks)
    memory = MemoryStore(tmp_path / "memory.db")
    knowledge = KnowledgeStore(tmp_path / "curation.db")
    sources = (Source("sessions_named", sessions, "directory"), Source("conversations", sessions, "directory"),
               Source("vault", vault, "directory"), Source("memory_db", memory.path, "sqlite"),
               Source("curation_db", knowledge.path, "sqlite"))
    inv = Inventory("fixture", "host", media, fence, sources)
    backup_id = str(uuid4())
    seal_archive(media, {member: path}, backup_id=backup_id, cut_id=str(uuid4()), profile_id="fixture", host_id="host",
                 capture=dict(directories=["conversations", "vault"], shared_session_root=True,
                              manifest_sha256="1" * 64, package_python_sha256="2" * 64))
    return inv, dict(marks_path=sidecar, backup_id=backup_id, now=stamp + timedelta(days=90)), marks, doc, path


def test_exact_boundary_deterministic_review_and_single_file_apply(fixture):
    inv, args, _, _, path = fixture
    other = path.with_name("legacy.json")
    other.write_bytes(b"protected unmarked history")
    plan = plan_session_retention(inv, **args)
    assert plan["ledger"][0]["reason"] == "eligible"
    assert str(path) not in json.dumps(plan) and path.name not in json.dumps(plan)
    assert plan == plan_session_retention(inv, **args) and path.exists()
    assert apply_review(inv, plan, **args)["removed"] == 1
    assert not path.exists() and other.read_bytes() == b"protected unmarked history"
    with pytest.raises(RetentionError, match="reviewed_plan_changed"):
        apply_review(inv, plan, **args)


@pytest.mark.parametrize(("case", "reason"), [
    ("pinned", "pinned"), ("active", "active"), ("recent", "archive_too_recent"), ("legacy", "legacy"),
    ("changed", "changed"), ("pending", "pending"), ("backup", "no_exact_backup"),
    ("memory", "referenced"), ("checkpoint", "referenced"), ("job", "referenced"),
    ("proposal", "referenced"), ("nested_source", "referenced"),
])
def test_protected_cases(fixture, case, reason):
    inv, args, marks, doc, path = fixture
    mark = marks["marks"][0]
    if case == "pinned":
        mark["pinned"] = True
    elif case == "active":
        mark["inactive"] = False
    elif case == "recent":
        args["now"] -= timedelta(microseconds=1)
    elif case == "legacy":
        mark["member"] = "conversations/legacy.json"
    elif case in {"changed", "pending", "backup"}:
        doc["title"] = "different"
        if case == "pending":
            doc["events"].append(dict(id="e", sequence=0, kind="run", status="pending", content="", created_at="t"))
        dump(path, doc)
        if case != "changed":
            mark["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        roots = {item.logical_id: item.path for item in inv.sources}
        dbpath = roots["memory_db" if case in {"memory", "checkpoint"} else "curation_db"]
        db = sqlite3.connect(dbpath)
        with db:
            if case == "memory":
                db.execute("INSERT INTO memory_sources VALUES('s',NULL,NULL,?,'e','manual',1)", (doc["id"],))
            elif case == "checkpoint":
                db.execute("INSERT INTO extraction_checkpoints VALUES(?,0)", (doc["id"],))
            elif case == "job":
                db.execute("INSERT INTO knowledge_jobs(id,conversation_id,start_sequence,end_sequence,selection,"
                           "created_at) VALUES('j',?,0,1,'{}',1)", (doc["id"],))
            else:
                payload = dict(conversation_id=str(uuid4()) if case == "nested_source" else doc["id"],
                               sources=[dict(conversation_id=doc["id"])])
                db.execute("INSERT INTO knowledge_proposals VALUES('p',NULL,'pending',1,'k',?,1,1)",
                           (json.dumps(payload),))
        db.close()
    dump(args["marks_path"], marks)
    plan = plan_session_retention(inv, **args)
    assert plan["ledger"][0]["reason"] == reason
    assert apply_review(inv, plan, **args)["removed"] == 0
    assert path.exists()


@pytest.mark.parametrize("change", ["pin", "file", "reference", "receipt", "corrupt", "malformed_proposal",
                                     "writer", "link", "wrong_root", "wrong_host", "reviewed"])
def test_recheck_fails_closed(fixture, change):
    inv, args, marks, doc, path = fixture
    plan = plan_session_retention(inv, **args)
    if change == "pin":
        marks["marks"][0]["pinned"] = True
        dump(args["marks_path"], marks)
    elif change == "file":
        doc["title"] = "modified"
        dump(path, doc)
    elif change in {"reference", "malformed_proposal"}:
        db = sqlite3.connect(next(src.path for src in inv.sources if src.logical_id == "curation_db"))
        with db:
            if change == "reference":
                db.execute("INSERT INTO knowledge_checkpoints VALUES(?,0)", (doc["id"],))
            else:
                db.execute("INSERT INTO knowledge_proposals VALUES('p',NULL,'pending',1,'k','{}',1,1)")
        db.close()
    elif change == "receipt":
        (inv.destination / (args["backup_id"] + ".receipt.json")).unlink()
    elif change == "corrupt":
        archive = inv.destination / (args["backup_id"] + ".zip")
        archive.write_bytes(b"broken")
    elif change == "writer":
        with host_fence(inv.fence.parent, mode="writer"), pytest.raises(RetentionError):
            apply_review(inv, plan, **args)
        assert path.exists()
        return
    elif change == "link":
        os.link(path, path.with_suffix(".copy"))
    elif change == "wrong_root":
        marks["marks"][0]["member"] = "sessions_named/" + path.name
        dump(args["marks_path"], marks)
    elif change == "wrong_host":
        inv = replace(inv, host_id="other")
    else:
        plan["schema_version"] = True
    with pytest.raises(RetentionError):
        apply_review(inv, plan, **args)
    assert path.exists()


def test_active_native_run_or_write_lock_blocks_reviewed_apply(fixture):
    inv, args, _, doc, path = fixture
    plan = plan_session_retention(inv, **args)
    store = SessionStore(path.parent)
    for acquire in (store.conversation_run, store._conversation_lock):
        with acquire(doc["id"]):
            assert plan_session_retention(inv, **args)["ledger"][0]["reason"] == "active"
            with pytest.raises(RetentionError, match="reviewed_plan_changed"):
                apply_review(inv, plan, **args)
    assert path.exists()


def test_wal_reference_visible_before_checkpoint(fixture):
    inv, args, _, doc, path = fixture
    plan = plan_session_retention(inv, **args)
    dbpath = next(src.path for src in inv.sources if src.logical_id == "memory_db")
    db = sqlite3.connect(dbpath)
    try:
        db.execute("PRAGMA wal_autocheckpoint=0")
        db.execute("INSERT INTO extraction_checkpoints VALUES(?,0)", (doc["id"],))
        db.commit()
        assert dbpath.with_name(dbpath.name + "-wal").stat().st_size > 0
        assert plan_session_retention(inv, **args)["ledger"][0]["reason"] == "referenced"
        with pytest.raises(RetentionError, match="reviewed_plan_changed"):
            apply_review(inv, plan, **args)
    finally:
        db.close()
    assert path.exists()


def test_incomplete_wal_refuses_even_if_main_database_has_no_reference(fixture):
    inv, args, _, _, path = fixture
    dbpath = next(src.path for src in inv.sources if src.logical_id == "memory_db")
    dbpath.with_name(dbpath.name + "-wal").write_bytes(b"unverified WAL")
    with pytest.raises(RetentionError, match="uncertain_references"):
        plan_session_retention(inv, **args)
    assert path.exists()


def test_untrusted_marks_location_or_hardlink_refused(fixture):
    inv, args, _, _, path = fixture
    alternate = path.parent / "marks.json"
    os.link(args["marks_path"], alternate)
    for source in (alternate, args["marks_path"]):
        with pytest.raises(RetentionError):
            plan_session_retention(inv, **dict(args, marks_path=source))
    assert path.exists()


def test_duplicate_identity_in_distinct_session_roots_is_protected(fixture):
    inv, args, _, _, path = fixture
    named = path.parent.with_name("named")
    named.mkdir()
    (named / path.name).write_bytes(path.read_bytes())
    sources = tuple(replace(src, path=named) if src.logical_id == "sessions_named" else src for src in inv.sources)
    inv = replace(inv, sources=sources)
    args["backup_id"] = str(uuid4())
    seal_archive(inv.destination, {"conversations/" + path.name: path, "sessions_named/" + path.name: named / path.name},
                 backup_id=args["backup_id"], cut_id=str(uuid4()), profile_id="fixture", host_id="host",
                 capture=dict(directories=["conversations", "sessions_named", "vault"], shared_session_root=False,
                              manifest_sha256="1" * 64, package_python_sha256="2" * 64))
    assert plan_session_retention(inv, **args)["ledger"][0]["reason"] == "ambiguous_identity"


def test_partial_apply_leaves_exact_backup_and_requires_fresh_review(fixture, monkeypatch):
    inv, args, marks, doc, first = fixture
    doc["id"] = str(uuid4())
    second = first.with_name("conversation-" + doc["id"] + ".json")
    dump(second, doc)
    marks["marks"].append(dict(marks["marks"][0], member="conversations/" + second.name,
                               sha256=hashlib.sha256(second.read_bytes()).hexdigest()))
    dump(args["marks_path"], marks)
    args["backup_id"] = str(uuid4())
    seal_archive(inv.destination, {"conversations/" + p.name: p for p in (first, second)},
                 backup_id=args["backup_id"], cut_id=str(uuid4()), profile_id="fixture", host_id="host",
                 capture=dict(directories=["conversations", "vault"], shared_session_root=True,
                              manifest_sha256="1" * 64, package_python_sha256="2" * 64))
    plan = plan_session_retention(inv, **args)
    original = Path.unlink
    def refuse_second(path, **kwargs):
        if path == max(first, second):
            raise OSError("synthetic removal fault")
        return original(path, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", refuse_second)
        with pytest.raises(RetentionError, match="partial_apply_1"):
            apply_review(inv, plan, **args)
    with pytest.raises(RetentionError, match="reviewed_plan_changed"):
        apply_review(inv, plan, **args)
    fresh = plan_session_retention(inv, **args)
    assert {r["reason"] for r in fresh["ledger"]} == {"eligible", "missing"}
    assert apply_review(inv, fresh, **args)["removed"] == 1
