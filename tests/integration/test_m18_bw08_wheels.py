"""Opt-in upgrade rehearsal with both reviewed standalone wheel artifacts."""

from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from uuid import uuid4

from laew.backup.capture import package_python_sha256
from laew.knowledge.store import KnowledgeStore
from laew.memory.store import MemoryStore
from tests.integration.test_m18_operator_backup import profile
from tests.integration.test_m18_worker_wheel import _configured_path, _exec, _private_directory, _success, _write_json


def test_worker_upgrade_and_supervised_rollback(tmp_path, profile):
    wheels = (_configured_path("LAEW_TEST_PREVIOUS_WORKER_WHEEL"), _configured_path("LAEW_TEST_WORKER_WHEEL"))
    wheelhouse = _configured_path("LAEW_TEST_WORKER_WHEELHOUSE")
    env = {name: value for name, value in os.environ.items() if not name.startswith(("PIP_", "PYTHON"))}
    env["PIP_CONFIG_FILE"] = os.devnull
    binaries = {}
    digests = {}
    for version, wheel in zip(("0.1.0", "0.2.0"), wheels, strict=True):
        prefix = tmp_path / ("worker-" + version)
        _private_directory(prefix)
        _success([sys.executable, "-I", "-B", "-m", "venv", "--copies", str(prefix)], tmp_path, env)
        python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        _success([str(python), "-I", "-B", "-m", "pip", "install", "--no-index", "--find-links",
                  str(wheelhouse), str(wheel)], tmp_path, env)
        probe = ("from pathlib import Path; import laew; from importlib.metadata import version; "
                 "from laew.backup.provenance import validate_worker_runtime; "
                 "from laew.backup.capture import package_python_sha256; validate_worker_runtime(); "
                 "print(version('laew-backup-worker')); print(package_python_sha256(Path(laew.__file__).parent))")
        actual, digests[version] = _success([str(python), "-I", "-B", "-c", probe], tmp_path, env).splitlines()
        assert actual == version
        binaries[version] = python
    assert len(set(digests.values())) == 2

    _, document = profile
    for name in ("controls", "archives", "recovery"):
        _private_directory(tmp_path / name)
    document.update(destination=str(tmp_path / "archives"), memory_enabled=True, knowledge_enabled=True)
    install = Path(document["launch_cwd"])
    memory = MemoryStore(install / "runtime/memory/memory.db")
    KnowledgeStore(install / "runtime/knowledge/curation.db")
    note = Path(document["vault"]) / "note.md"
    note.write_bytes(b"BW08 upgrade fixture")
    core = tmp_path / "reviewed-core"
    core.mkdir()
    (core / "__init__.py").write_bytes(b"# synthetic reviewed release\n")
    controls = tmp_path / "controls"
    conf = controls / "profile.json"
    _write_json(conf, document)

    def cli(version, *args, code=0):
        result = _exec([str(binaries[version]), "-I", "-B", "-m", "laew.backup_worker",
                        *args, "--profile", str(conf)], tmp_path, env)
        assert result.returncode == code, (result.stdout, result.stderr)
        return json.loads(result.stdout)

    def capture(version):
        identifier = str(uuid4())
        ack = controls / "ack.json"
        review = controls / ("review-" + version + ".json")
        _write_json(ack, dict(schema_version=1, profile_id=document["profile_id"], host_id=document["host_id"],
                              backup_id=identifier, cut_id=str(uuid4()), roster=["fixture"], stopped=["fixture"],
                              inventory_complete=True, restart_inhibited=True,
                              valid_until=(datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()))
        _write_json(review, dict(schema_version=1, profile_id=document["profile_id"], host_id=document["host_id"],
                                 core_release="fixture", core_package_root=str(core),
                                 core_package_python_sha256=package_python_sha256(core),
                                 worker_package_python_sha256=digests[version],
                                 profile_sha256=hashlib.sha256(conf.read_bytes()).hexdigest(),
                                 manifest_sha256=hashlib.sha256(Path(document["manifest_path"]).read_bytes()).hexdigest()))
        receipt = cli(version, "backup", "create", "--acknowledgement", str(ack), "--provenance", str(review),
                      "--apply", "--json")["data"]["receipt"]
        return identifier, receipt

    old = capture("0.1.0")
    assert cli("0.2.0", "backup", "verify", "--id", old[0], "--json")["data"]["receipt"] == old[1]
    new = capture("0.2.0")
    media = Path(document["destination"])
    before = {path.name: hashlib.sha256(path.read_bytes()).digest() for path in media.iterdir()}
    assert cli("0.2.0", "control", "initialize", "--apply")["state"] == "disabled"
    assert cli("0.2.0", "backup", "list", "--json")["data"]["invalid_receipts"] == 0
    for version, (identifier, receipt) in (("0.2.0", old), ("0.1.0", new)):
        assert cli(version, "backup", "verify", "--id", identifier, "--json")["data"]["receipt"] == receipt
        target = tmp_path / "recovery" / version
        assert cli(version, "restore", "--id", identifier, "--target", str(target), "--apply",
                   "--json")["data"]["receipt"]["state"] == "isolated"
        assert (target / "vault/note.md").read_bytes() == note.read_bytes()
        for db in (target / "memory_db/memory.db", target / "curation_db/curation.db"):
            with closing(sqlite3.connect(db.as_uri() + "?mode=ro&immutable=1", uri=True)) as check:
                assert check.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    assert {path.name: hashlib.sha256(path.read_bytes()).digest() for path in media.iterdir()} == before
    assert memory.path.is_file()
