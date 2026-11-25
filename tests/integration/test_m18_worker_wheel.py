"""An installed worker and a frozen Core checkout exchange synthetic v1 archives."""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4
import zipfile

import pytest

from laew.backup.capture import package_python_sha256
from laew.backup.fence import host_fence
from laew.console.session_store import SessionStore, make_chat_payload
from laew.knowledge.store import KnowledgeStore
from laew.memory.store import MemoryStore
from laew.rag.identity import canonical_project_path
from tests.integration.test_m18_operator_backup import profile  # pytest fixture


def _configured_path(name):
    if not os.environ.get(name):
        pytest.skip(f"{name} is required for the standalone release drill")
    return Path(os.environ[name]).resolve(strict=True)


def _exec(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def _success(args, cwd, env=None):
    result = _exec(args, cwd, env)
    assert result.returncode == 0, (result.stdout, result.stderr)
    return result.stdout


def _private_directory(path):
    path.mkdir(mode=0o777 if os.name == "nt" else 0o700)
    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        _success(["icacls", str(path), "/inheritance:r", "/grant:r",
                  f"*{get_current_user_sid()}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                  "*S-1-5-32-544:(OI)(CI)F"], path.parent)


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    if os.name != "nt":
        path.chmod(0o600)


def _manifest(media, backup_id):
    with zipfile.ZipFile(media / f"{backup_id}.zip") as archive:
        return json.loads(archive.read("manifest.json"))


def test_installed_worker_and_frozen_core_roundtrip(tmp_path, profile):
    wheel = _configured_path("LAEW_TEST_WORKER_WHEEL")
    wheelhouse = _configured_path("LAEW_TEST_WORKER_WHEELHOUSE")
    legacy = _configured_path("LAEW_TEST_LEGACY_ROOT")
    home = tmp_path / "standalone"
    if os.name == "nt":
        _private_directory(home)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PYTHON", "PIP_"))}
    env["PIP_CONFIG_FILE"] = os.devnull
    _success([sys.executable, "-I", "-B", "-m", "venv", "--copies", str(home)], tmp_path, env)
    python = home / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    _success([str(python), "-I", "-B", "-m", "pip", "install", "--no-index", "--find-links",
              str(wheelhouse), str(wheel)], tmp_path, env)
    probe = """
import importlib.util, json, sys, sysconfig
from pathlib import Path
import laew
from laew.backup.capture import package_python_sha256
from laew.backup.provenance import validate_worker_runtime
validate_worker_runtime()
root = Path(laew.__file__).parent
assert root.is_relative_to(Path(sysconfig.get_path('purelib')))
assert all(importlib.util.find_spec(n) is None for n in ('numpy', 'requests', 'chromadb', 'laew.web'))
assert not any(n.startswith(('laew.agent', 'laew.llm', 'laew.runtime', 'laew.telemetry')) for n in sys.modules)
print(json.dumps(package_python_sha256(root)))
"""
    worker_digest = json.loads(_success([str(python), "-I", "-B", "-c", probe], tmp_path, env))

    _, base_profile = profile
    base_profile.update(memory_enabled=True, knowledge_enabled=True)
    source = Path(base_profile["launch_cwd"])
    media = tmp_path / "owned-media"
    _private_directory(media)
    base_profile["destination"] = str(media)
    vault = Path(base_profile["vault"])
    (vault / "note.md").write_text("Synthetic recovery source", encoding="utf-8")
    (vault / ".env").write_text("synthetic-excluded-canary", encoding="utf-8")
    sessions = SessionStore(source / "runtime/sessions")
    sessions.save("legacy", make_chat_payload("manifest.yaml", []))
    project = source / "fixture-project"
    project.mkdir()
    project_id = hashlib.sha256(canonical_project_path(project).encode()).hexdigest()[:16]
    conversation = sessions.create_conversation("project", project_id)
    memory = MemoryStore(source / "runtime/memory/memory.db")
    KnowledgeStore(source / "runtime/knowledge/curation.db")
    for name in ("controls", "restores", "advisory"):
        _private_directory(tmp_path / name)
    controls = tmp_path / "controls"
    profile_path = controls / "profile.json"
    _write_json(profile_path, base_profile)
    active_manifest = Path(base_profile["manifest_path"])
    core_digest = package_python_sha256(legacy / "laew")
    review = controls / "release.json"
    evidence = dict(schema_version=1, profile_id="fixture", host_id="host1", core_release="eff4284",
                    core_package_root=str(legacy / "laew"), core_package_python_sha256=core_digest,
                    worker_package_python_sha256=worker_digest,
                    profile_sha256=hashlib.sha256(profile_path.read_bytes()).hexdigest(),
                    manifest_sha256=hashlib.sha256(active_manifest.read_bytes()).hexdigest())
    _write_json(review, evidence)
    (tmp_path / "advisory/installation.lock").touch(mode=0o600)
    status = tmp_path / "advisory/status.json"

    def cli(surface, *args, code=0):
        command = ([str(python), "-I", "-B", "-m", "laew.backup_worker"] if surface == "worker" else
                   [sys.executable, "-B", "-m", "laew.cli"])
        result = _exec(command + [*args, "--profile", str(profile_path), "--json"],
                       tmp_path if surface == "worker" else legacy, env)
        assert result.returncode == code, (result.stdout, result.stderr)
        return json.loads(result.stdout)

    assert cli("legacy", "backup", "plan") == cli("worker", "backup", "plan")
    assert cli("worker", "backup", "list")["data"]["receipts"] == []

    def ack(expires=None):
        path = controls / "ack.json"
        generation = str(uuid4())
        expires = expires or datetime.now(timezone.utc) + timedelta(minutes=3)
        _write_json(path, dict(schema_version=1, profile_id="fixture", host_id="host1",
                                backup_id=generation, cut_id=str(uuid4()), roster=["fixture-writer"],
                                stopped=["fixture-writer"], inventory_complete=True, restart_inhibited=True,
                                valid_until=expires.isoformat()))
        return generation, ("backup", "create", "--acknowledgement", str(path), "--apply")

    status_options = ("--status-file", str(status))
    provenance = ("--provenance", str(review))
    if os.name == "nt":
        from laew.backup.health import _status_parent
        from laew.security.windows_security import get_current_user_sid

        try:
            _status_parent(status, get_current_user_sid())
        except (ValueError, OSError, RuntimeError):
            # A Windows temp tree can be appropriate for isolated archives
            # and still fail the stricter advisory ancestry requirement.
            _, create = ack()
            cli("worker", *create, *provenance, *status_options, code=1)
            assert not status.exists() and not list(media.iterdir())
            status_options = ()
    worker_options = (*provenance, *status_options)
    if status_options:
        with host_fence(status.parent, mode="writer"):
            _, create = ack()
            cli("worker", *create, *worker_options, code=1)
            assert not status.exists() and not list(media.iterdir())
    _, create = ack(datetime(2000, 1, 1, tzinfo=timezone.utc))
    cli("worker", *create, *worker_options, code=1)
    with host_fence(Path(base_profile["fence"]).parent, mode="writer"):
        _, create = ack()
        cli("worker", *create, *worker_options, code=1)
        if status_options:
            assert json.loads(status.read_bytes())["last_attempt"]["outcome"] == "skipped"
    _write_json(review, {**evidence, "worker_package_python_sha256": "0" * 64})
    _, create = ack()
    cli("worker", *create, *worker_options, code=1)
    assert not list(media.iterdir())
    _write_json(review, evidence)

    # Keep a synthetic writer connection idle to retain committed WAL for both captures.
    with closing(sqlite3.connect(memory.path)) as connection:
        connection.execute("PRAGMA wal_autocheckpoint=0")
        connection.execute("INSERT INTO extraction_checkpoints VALUES(?, -1)", (conversation["id"],))
        connection.commit()
        wal = memory.path.with_name("memory.db-wal")
        original_wal = wal.read_bytes()
        golden, create = ack()
        legacy_receipt = cli("legacy", *create)["data"]["receipt"]
        fresh, create = ack()
        worker_receipt = cli("worker", *create, *worker_options)["data"]["receipt"]
        assert wal.read_bytes() == original_wal and original_wal

    golden_manifest, worker_manifest = (_manifest(media, item) for item in (golden, fresh))
    assert golden_manifest["capture"]["package_python_sha256"] == core_digest
    assert worker_manifest["capture"]["package_python_sha256"] == worker_digest
    assert {row["name"] for row in golden_manifest["members"]} == {
        row["name"] for row in worker_manifest["members"]}
    assert all(".env" not in row["name"] for row in worker_manifest["members"])
    record = json.loads((controls / f"backup-release-{fresh}.json").read_bytes())
    assert record["archive_sha256"] == worker_receipt["archive_sha256"]
    assert record["core_package_python_sha256"] == core_digest
    if status_options:
        assert json.loads(status.read_bytes())["last_verified_at_utc"] == worker_receipt["verified_at"]

    for reader, generation, receipt in (("worker", golden, legacy_receipt), ("legacy", fresh, worker_receipt)):
        assert cli(reader, "backup", "verify", "--id", generation)["data"]["receipt"] == receipt
        assert cli(reader, "restore", "--id", generation, "--verify-only")["state"] == "ok"
        target = tmp_path / "restores" / reader
        options = ("restore", "--id", generation, "--target", str(target), "--apply",
                   "--project-root", str(project))
        cli(reader, *options)
        assert (target / "vault/note.md").read_bytes() == (vault / "note.md").read_bytes()
        assert (target / "conversations" / f"conversation-{conversation['id']}.json").is_file()
        with closing(sqlite3.connect((target / "memory_db/memory.db").as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
            assert db.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert db.execute("SELECT sequence FROM extraction_checkpoints").fetchall() == [(-1,)]
        cli(reader, *options, code=1)

    # Verify a corrupt committed generation through the real worker and invalidate health.
    archive = media / f"{fresh}.zip"
    raw = archive.read_bytes()
    archive.write_bytes(raw.replace(b"Synthetic recovery source", b"synthetic recovery source"))
    cli("worker", "backup", "verify", "--id", fresh, *status_options, code=1)
    cli("worker", "backup", "verify", "--id", golden, *status_options)
    if status_options:
        assert json.loads(status.read_bytes())["last_verified_at_utc"] == legacy_receipt["verified_at"]
