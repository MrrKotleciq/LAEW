import json
import shutil
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import yaml

from laew.backup.archive import seal_archive
from laew.operator_cli import dispatch


@pytest.fixture
def profile(tmp_path):
    install = tmp_path / "install"
    for path in (install / "manifests", install / "runtime/sessions", tmp_path / "vault", tmp_path / "backup"):
        path.mkdir(parents=True)
    manifest = {
        "version": "1", "system_name": "fixture", "stage": "test",
        "workspace": {"root": ".", "allowed_paths": [], "restricted_paths": [], "ignored_patterns": []},
        "models": {"roles": {name: {} for name in ("primary", "embedding", "reviewer")}},
        "tools": {"categories": {"filesystem": {"policy": "read_only_by_default"},
                                 "git": {"policy": "inspection_first"},
                                 "terminal": {"policy": "safe_command_allowlist", "allowlist": []},
                                 "web": {"policy": "read_only"}}},
        "memory": {"session": {"storage": "runtime/sessions"}, "second_brain": {}},
        "rag": {"pipeline": {}},
    }
    manifest_path = install / "manifests/system.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    fence = tmp_path / "installation.lock"
    fence.touch()
    data = dict(schema_version=1, profile_id="fixture", host_id="host1", manifest_path=str(manifest_path),
                launch_cwd=str(install), workspace_root=str(install), vault=str(tmp_path / "vault"), destination=str(tmp_path / "backup"),
                fence=str(fence), config_files={}, memory_enabled=False, knowledge_enabled=False,
                memory_storage=None, knowledge_storage=None)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


def _call(capsys, args):
    code = dispatch(args + ["--json"])
    output = capsys.readouterr()
    assert output.err == ""
    return code, json.loads(output.out)


def test_prune_reviews_exact_ledger_and_keeps_pinned_archive(profile, capsys):
    path, data = profile
    staged = path.parent / "staged"
    staged.write_bytes(b"canonical fixture")
    identifier = str(uuid4())
    seal_archive(data["destination"], {"vault/note.txt": staged}, backup_id=identifier,
                 cut_id=str(uuid4()), profile_id="fixture", host_id="host1",
                 capture=dict(directories=["conversations", "vault"], shared_session_root=True,
                              manifest_sha256="1" * 64, package_python_sha256="2" * 64))
    args = ["backup", "prune", "--profile", str(path), "--pin", identifier]
    before = set(path.parent.rglob("*"))
    code, result = _call(capsys, args)
    assert code == 0 and result["command"] == "backup.prune"
    assert set(path.parent.rglob("*")) == before
    review = path.parent / "review.json"
    review.write_text(json.dumps(result), encoding="utf-8")
    assert _call(capsys, args + ["--plan", str(review)])[0] == 2
    code, applied = _call(capsys, args + ["--plan", str(review), "--apply"])
    assert code == 0 and applied["data"]["removed"] == []
    assert _call(capsys, ["backup", "verify", "--profile", str(path), "--id", identifier])[0] == 0


def test_plan_and_empty_list_are_read_only(profile, capsys):
    path, data = profile
    before = set(path.parent.rglob("*"))
    code, result = _call(capsys, ["backup", "plan", "--profile", str(path)])
    assert code == 0 and result["data"]["profile_id"] == "fixture"
    assert {row["logical_id"] for row in result["data"]["sources"]} == {"vault", "conversations", "sessions_named"}
    assert str(path.parent) not in json.dumps(result)
    code, result = _call(capsys, ["backup", "list", "--profile", str(path)])
    assert code == 0 and result["data"]["receipts"] == []
    assert before == set(path.parent.rglob("*"))


def test_list_cached_and_verify_checks_full_archive(profile, capsys):
    path, data = profile
    staged = path.parent / "staged.txt"
    staged.write_text("synthetic", encoding="utf-8")
    identifier = str(uuid4())
    receipt = seal_archive(data["destination"], {"vault/note.txt": staged}, backup_id=identifier,
                           cut_id=str(uuid4()), profile_id="fixture", host_id="host1")
    (path.parent / "backup" / (str(uuid4()) + ".zip")).write_bytes(b"orphan")
    code, result = _call(capsys, ["backup", "list", "--profile", str(path)])
    assert code == 0 and result["data"]["receipts"] == [receipt]
    assert result["data"]["receipt_state"] == "cached"
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", identifier])
    assert code == 0 and result["data"]["receipt_state"] == "verified"
    archive = path.parent / "backup" / (identifier + ".zip")
    archive.write_bytes(archive.read_bytes().replace(b"synthetic", b"tampered!"))
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", identifier])
    assert code == 1 and result["error_code"] == "unavailable_or_invalid"


def test_foreign_receipt_and_malformed_input_are_never_exposed(profile, capsys):
    path, data = profile
    staged = path.parent / "staged.txt"
    staged.write_text("synthetic")
    identifier = str(uuid4())
    seal_archive(data["destination"], {"vault/note": staged}, backup_id=identifier,
                 cut_id=str(uuid4()), profile_id="foreign", host_id="host1")
    code, result = _call(capsys, ["backup", "list", "--profile", str(path)])
    assert code == 0 and result["data"]["receipts"] == []
    assert result["data"]["invalid_receipts"] == 1
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", identifier])
    assert code == 1 and identifier not in json.dumps(result)
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", "SECRET"])
    assert code == 2 and "SECRET" not in json.dumps(result)


def test_rejects_duplicate_profile_json_and_relative_profile(profile, capsys):
    path, _ = profile
    path.write_text('{"SECRET": 1, "SECRET": 2}', encoding="utf-8")
    code, result = _call(capsys, ["backup", "plan", "--profile", str(path)])
    assert code == 1 and "SECRET" not in json.dumps(result)
    code, result = _call(capsys, ["backup", "plan", "--profile", "relative-secret"])
    assert code == 1 and "relative-secret" not in json.dumps(result)


def test_directory_limit_fails_without_partial_listing(profile, capsys):
    path, data = profile
    for index in range(1001):
        (path.parent / "backup" / f"ignored-{index}").touch()
    code, result = _call(capsys, ["backup", "list", "--profile", str(path)])
    assert code == 1
    assert result["data"] is None


def test_oversized_profile_and_missing_option_are_sanitized(profile, capsys):
    path, _ = profile
    path.write_text("x" * 65537, encoding="utf-8")
    code, result = _call(capsys, ["backup", "plan", "--profile", str(path)])
    assert code == 1 and result["error_code"] == "unavailable_or_invalid"
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path)])
    assert code == 2 and result["error_code"] == "invalid_arguments"


def test_list_and_verify_after_source_loss(profile, capsys):
    path, data = profile
    staged = path.parent / "staged.txt"
    staged.write_text("synthetic", encoding="utf-8")
    identifier = str(uuid4())
    seal_archive(data["destination"], {"vault/note.txt": staged}, backup_id=identifier,
                 cut_id=str(uuid4()), profile_id="fixture", host_id="host1")
    shutil.rmtree(path.parent / "install")
    shutil.rmtree(path.parent / "vault")
    code, result = _call(capsys, ["backup", "list", "--profile", str(path)])
    assert code == 0 and result["data"]["receipts"][0]["backup_id"] == identifier
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", identifier])
    assert code == 0 and result["data"]["receipt_state"] == "verified"
    code, result = _call(capsys, ["backup", "plan", "--profile", str(path)])
    assert code == 1 and result["error_code"] == "unavailable_or_invalid"


@pytest.mark.parametrize("args, expected", [
    (["backup", "--help"], "{plan,list,verify,create,prune}"),
    (["backup", "plan", "--help"], "--profile"),
    (["backup", "list", "--help"], "--profile"),
    (["backup", "verify", "--help"], "--id"),
    (["backup", "create", "--help"], "--apply"),
])
def test_operator_help(args, expected, capsys):
    assert dispatch(args) == 0
    output = capsys.readouterr()
    assert output.err == "" and expected in output.out


def test_json_invalid_arguments_do_not_echo_help_or_input(capsys):
    code, result = _call(capsys, ["backup", "verify", "--help", "CANARY"])
    assert code == 2 and result["error_code"] == "invalid_arguments"
    assert "CANARY" not in json.dumps(result)


def _proof(tmp_path):
    doc = {"schema_version": 1, "profile_id": "fixture", "host_id": "host1",
           "backup_id": str(uuid4()), "cut_id": str(uuid4()), "roster": ["cli", "editor"],
           "stopped": ["cli", "editor"], "inventory_complete": True, "restart_inhibited": True,
           "valid_until": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
    path = tmp_path / "acknowledgement.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path, doc


def test_create_requires_apply_and_produces_verified_fixture(profile, capsys):
    path, data = profile
    ack_path, doc = _proof(path.parent)
    (path.parent / "vault" / "note.md").write_text("synthetic", encoding="utf-8")
    before = set(path.parent.rglob("*"))
    args = ["backup", "create", "--profile", str(path), "--acknowledgement", str(ack_path)]
    code, result = _call(capsys, args)
    assert code == 2 and result["error_code"] == "invalid_arguments"
    assert before == set(path.parent.rglob("*"))
    code, result = _call(capsys, args + ["--apply"])
    assert code == 0 and result["data"]["receipt"]["backup_id"] == doc["backup_id"]
    assert result["data"]["receipt"]["cut_id"] == doc["cut_id"]
    code, result = _call(capsys, ["backup", "verify", "--profile", str(path), "--id", doc["backup_id"]])
    assert code == 0 and result["data"]["receipt_state"] == "verified"


@pytest.mark.parametrize("changes", [
    {"valid_until": "2000-01-01T00:00:00+00:00"}, {"valid_until": "2099-01-01T00:00:00"},
    {"stopped": ["cli"]}, {"roster": []}, {"roster": ["unknown"]},
    {"inventory_complete": False}, {"restart_inhibited": False}, {"backup_id": "SECRET"},
    {"profile_id": "foreign"}, {"roster": ["cli", "cli"]},
])
def test_create_rejects_invalid_proof_without_capture(profile, capsys, changes):
    path, data = profile
    ack_path, doc = _proof(path.parent)
    doc.update(changes)
    ack_path.write_text(json.dumps(doc), encoding="utf-8")
    args = ["backup", "create", "--profile", str(path), "--acknowledgement", str(ack_path), "--apply"]
    code, result = _call(capsys, args)
    assert code == 1 and result["error_code"] == "unavailable_or_invalid"
    assert "SECRET" not in json.dumps(result)
    assert list((path.parent / "backup").iterdir()) == []
