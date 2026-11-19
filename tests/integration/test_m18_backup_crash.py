"""Single-host fenced capture on synthetic sessions, vault and WAL databases."""

from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import hashlib
import os
import sqlite3
import subprocess
import sys
from uuid import uuid4
import zipfile

import pytest

from laew.backup import capture
from laew.backup.archive import verify_archive
from laew.backup.capture import CaptureError, WriterAcknowledgement, capture_backup
from laew.backup.fence import FENCE_FILENAME, FenceBusyError, host_fence
from laew.backup.inventory import Inventory, Source, manifest_content_digest
from laew.console.session_store import SessionStore, SessionStoreError, make_chat_payload
from laew.knowledge.store import KnowledgeStore
from laew.memory.store import MemoryStore


@pytest.fixture
def fixture(tmp_path):
    sessions, vault, media, locks = [tmp_path / name for name in ("sessions", "vault", "media", "locks")]
    for directory in (sessions, vault, media, locks):
        directory.mkdir(mode=0o700)
    fence = locks / FENCE_FILENAME
    fence.touch()
    (vault / "note.md").write_text("first", encoding="utf-8")
    (vault / ".env").write_text("synthetic private fixture", encoding="utf-8")
    plugin = vault / ".obsidian" / "plugins"
    plugin.mkdir(parents=True)
    (plugin / "conf.json").write_text("{}", encoding="utf-8")
    config = tmp_path / "settings.json"
    config.write_text('{"documentation_language":"pl"}', encoding="utf-8")
    session_store = SessionStore(sessions)
    session_store.save("chat", make_chat_payload("manifest.yaml", []))
    conversation = session_store.create_conversation("general", None)
    memory = MemoryStore(tmp_path / "memory" / "memory.db")
    knowledge = KnowledgeStore(tmp_path / "knowledge" / "curation.db")
    sources = (Source("sessions_named", sessions, "directory"), Source("conversations", sessions, "directory"),
               Source("vault", vault, "directory"), Source("config_settings", config, "file"),
               Source("memory_db", memory.path, "sqlite"), Source("curation_db", knowledge.path, "sqlite"))
    manifest = tmp_path / "manifest.yaml"
    manifest.write_bytes(b"secret: fixture-canary\n")
    inv = Inventory("fixture", "test_host", media, fence, sources, manifest_path=manifest,
                    manifest_content_digest=manifest_content_digest({"secret": "fixture-canary"}))
    roster = frozenset({"workbench", "editor", "sync"})
    cut = str(uuid4())
    backup = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    proof = WriterAcknowledgement(inv.profile_id, inv.host_id, backup, cut, roster, roster, True, True, expires)
    return inv, dict(cut_id=cut, backup_id=backup, writers=proof), conversation["id"]


def test_fenced_snapshot_includes_committed_wal_and_pending_jobs(fixture, tmp_path):
    inv, args, conversation = fixture
    (tmp_path / "vault" / "empty" / "nested").mkdir(parents=True)
    memory = next(row.path for row in inv.sources if row.logical_id == "memory_db")
    with closing(sqlite3.connect(memory)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO extraction_jobs(id,conversation_id,start_sequence,end_sequence,model_json,"
                       "created_at) VALUES(?,?,0,1,'{}',1)", ("pending-job", conversation))
        writer.commit()
        assert memory.with_name(memory.name + "-wal").stat().st_size > 0
        receipt = capture_backup(inv, **args)
    assert verify_archive(inv.destination, args["backup_id"]) == receipt
    with zipfile.ZipFile(inv.destination / (args["backup_id"] + ".zip")) as container:
        manifest = json.loads(container.read("manifest.json"))
        metadata = manifest["capture"]
        assert metadata["directories"] == ["conversations", "vault", "vault/empty", "vault/empty/nested"]
        assert metadata["shared_session_root"] is True
        assert metadata["manifest_sha256"] == hashlib.sha256(inv.manifest_path.read_bytes()).hexdigest()
        assert len(bytes.fromhex(metadata["package_python_sha256"])) == 32
        assert b"fixture-canary" not in container.read("manifest.json")
        names = {row["name"] for row in manifest["members"]}
        assert names == {"vault/note.md", "config_settings/settings.json", "memory_db/memory.db",
                         "curation_db/curation.db", "conversations/chat.json",
                         f"conversations/conversation-{conversation}.json"}
        snapshot = tmp_path / "snapshot.db"
        snapshot.write_bytes(container.read("data/memory_db/memory.db"))
        raw = json.loads(container.read("data/conversations/chat.json"))
        assert raw["manifest_path"] == "manifest.yaml"
    with closing(sqlite3.connect(snapshot.as_uri() + "?mode=ro&immutable=1", uri=True)) as check:
        assert check.execute("SELECT id,status FROM extraction_jobs").fetchall() == [("pending-job", "pending")]
        assert check.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert not list(inv.destination.glob("*.partial"))
    assert not list(inv.destination.glob(".m18-capture-*"))


@pytest.mark.parametrize("changes", [{"stopped": frozenset({"workbench"})}, {"inventory_complete": False},
                                     {"restart_inhibited": False}, {"cut_id": "other"}, {"roster": frozenset()},
                                     {"backup_id": "other"}, {"valid_until": datetime(2025, 1, 1, tzinfo=timezone.utc)}])
def test_unconfirmed_external_writer_stops_capture(fixture, changes):
    inv, args, _ = fixture
    args["writers"] = replace(args["writers"], **changes)
    with pytest.raises(CaptureError):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


def test_active_cooperating_writer_denies_capture(fixture):
    inv, args, _ = fixture
    with host_fence(inv.fence.parent, mode="writer"), pytest.raises(FenceBusyError):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


@pytest.mark.parametrize("fault", ["session", "conversation", "secret_config", "unknown_session", "hardlink", "db"])
def test_invalid_required_source_is_not_omitted(fixture, fault):
    inv, args, conversation = fixture
    roots = {row.logical_id: row.path for row in inv.sources}
    if fault == "session":
        (roots["sessions_named"] / "broken.json").write_text("{}", encoding="utf-8")
    elif fault == "conversation":
        (roots["conversations"] / f"conversation-{conversation}.json").write_text("{}", encoding="utf-8")
    elif fault == "secret_config":
        roots["config_settings"].write_text('{"private_field":"fake"}', encoding="utf-8")
    elif fault == "unknown_session":
        (roots["conversations"] / "mystery.bin").write_bytes(b"?")
    elif fault == "hardlink":
        os.link(roots["vault"] / "note.md", roots["vault"] / "alias.md")
    else:
        with closing(sqlite3.connect(roots["memory_db"])) as db:
            db.execute("PRAGMA user_version=100")
    with pytest.raises((CaptureError, SessionStoreError)):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


def test_changed_source_at_publication_has_no_receipt(fixture, monkeypatch):
    inv, args, _ = fixture
    original = capture.seal_archive
    vault = next(src.path for src in inv.sources if src.logical_id == "vault")

    def inject(*args, before_publish, **kwargs):
        def changed():
            (vault / "new.md").write_text("changed", encoding="utf-8")
            before_publish()
        return original(*args, before_publish=changed, **kwargs)

    monkeypatch.setattr(capture, "seal_archive", inject)
    with pytest.raises(CaptureError):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


def test_process_exit_mid_capture_leaves_no_generation_and_releases_fence(fixture):
    inv, args, _ = fixture
    script = """
import json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from laew.backup import capture
from laew.backup.inventory import Source, Inventory, manifest_content_digest
from laew.backup.capture import WriterAcknowledgement
media, fence, backup, cut, sources = sys.argv[1:]
inv = Inventory('fixture', 'test_host', Path(media), Path(fence), tuple(
    Source(key, Path(path), kind) for key, path, kind in json.loads(sources)),
    manifest_path=Path(media).parent / 'manifest.yaml',
    manifest_content_digest=manifest_content_digest({'secret': 'fixture-canary'}))
roster = frozenset({'workbench', 'editor', 'sync'})
writers = WriterAcknowledgement('fixture', 'test_host', backup, cut, roster, roster, True, True,
                                datetime.now(timezone.utc) + timedelta(minutes=10))
copy = capture._copy
def die(*args):
    copy(*args)
    os._exit(73)
capture._copy = die
capture.capture_backup(inv, backup_id=backup, cut_id=cut, writers=writers)
"""
    sources = json.dumps([(row.logical_id, str(row.path), row.kind) for row in inv.sources])
    result = subprocess.run([sys.executable, "-c", script, str(inv.destination), str(inv.fence),
                             args["backup_id"], args["cut_id"], sources], timeout=15, capture_output=True)
    assert result.returncode == 73, result.stderr
    assert not list(inv.destination.glob("*.zip"))
    assert not list(inv.destination.glob("*.receipt.json"))
    leftovers = list(inv.destination.glob(".m18-capture-*"))
    assert len(leftovers) == 1
    assert capture_backup(inv, **args)["backup_id"] == args["backup_id"]
    assert leftovers[0].exists()


def test_low_space_stops_before_staging(fixture, monkeypatch):
    inv, args, _ = fixture
    usage = capture.shutil.disk_usage(inv.destination)._replace(free=1)
    monkeypatch.setattr(capture.shutil, "disk_usage", lambda _: usage)
    monkeypatch.setattr(capture.tempfile, "TemporaryDirectory", lambda **kwargs: pytest.fail("began staging"))
    with pytest.raises(CaptureError, match="space"):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


def test_authored_manifest_changed_after_inventory(fixture):
    inv, args, _ = fixture
    inv.manifest_path.write_bytes(b"alternate: configuration\n")
    with pytest.raises(CaptureError, match="inventoried"):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


def test_distinct_empty_session_roots_are_preserved(fixture, tmp_path):
    inv, args, _ = fixture
    sources = []
    for source in inv.sources:
        if source.logical_id in {"conversations", "sessions_named"}:
            path = tmp_path / source.logical_id
            path.mkdir()
            source = replace(source, path=path)
        sources.append(source)
    capture_backup(replace(inv, sources=tuple(sources)), **args)
    with zipfile.ZipFile(inv.destination / (args["backup_id"] + ".zip")) as container:
        metadata = json.loads(container.read("manifest.json"))["capture"]
        assert metadata["directories"] == ["conversations", "sessions_named", "vault"]
        assert metadata["shared_session_root"] is False


def test_reject_same_device_mount_from_namespace_inventory(fixture, monkeypatch):
    inv, args, _ = fixture
    vault = next(src.path for src in inv.sources if src.logical_id == "vault")
    assumed_mount = vault / "new-root"
    assumed_mount.mkdir()
    monkeypatch.setattr(capture, "_mounts", lambda: {assumed_mount})
    with pytest.raises(CaptureError):
        capture_backup(inv, **args)
    assert not list(inv.destination.iterdir())


@pytest.mark.parametrize("status,index,actual,valid", [
    ("approved", "not_written", None, True), ("approved", "not_written", "proposed", True),
    ("approved", "not_written", "divergent", False), ("applied", "pending", "proposed", True),
    ("applied", "pending", "divergent", False), ("applied", "superseded", "later", True),
])
def test_curation_publication_cut_never_replays(fixture, status, index, actual, valid):
    inv, args, _ = fixture
    roots = {row.logical_id: row.path for row in inv.sources}
    target = roots["vault"] / "published.md"
    if actual is not None:
        target.write_text(actual, encoding="utf-8")
    row = dict(target="@knowledge/published.md", approved_version=1, index_status=index,
               base_content="", base_sha256="", content="proposed")
    with closing(sqlite3.connect(roots["curation_db"])) as db:
        db.execute("INSERT INTO knowledge_proposals VALUES('p',NULL,?,3,'key',?,0,0)", (status, json.dumps(row)))
        db.commit()
    if valid:
        assert capture_backup(inv, **args)["member_count"] >= 6
    else:
        with pytest.raises(CaptureError):
            capture_backup(inv, **args)
        assert not list(inv.destination.iterdir())
    assert (target.read_text(encoding="utf-8") if target.exists() else None) == actual
