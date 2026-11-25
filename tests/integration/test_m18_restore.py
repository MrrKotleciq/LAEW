import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from laew.backup import restore
from laew.backup.archive import ArchiveError, seal_archive
from laew.backup.restore import RestoreError, restore_backup, verify_restore


@pytest.fixture
def generation(tmp_path):
    install = tmp_path / "installation"
    media = tmp_path / "media"
    recovery = tmp_path / "recovery"
    for folder in (install, media, recovery):
        folder.mkdir(mode=0o777 if os.name == "nt" else 0o700)
    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        subprocess.run(["icacls", str(recovery), "/inheritance:r", "/grant:r",
                        f"*{get_current_user_sid()}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
                        "*S-1-5-32-544:(OI)(CI)F"], check=True, capture_output=True)
    path = install / "note.md"
    path.write_bytes(b"canonical fixture")
    profile = dict(schema_version=1, profile_id="fixture", host_id="host", manifest_path=install / "system.yaml",
                   launch_cwd=install, workspace_root=install, vault=install / "vault", destination=media,
                   fence=install / "installation.lock", config_files={}, memory_enabled=False, knowledge_enabled=False,
                   memory_storage=None, knowledge_storage=None)
    capture = dict(directories=["conversations", "vault", "vault/empty"], shared_session_root=True,
                   manifest_sha256="1" * 64, package_python_sha256="2" * 64)
    identity = dict(backup_id=str(uuid4()), cut_id=str(uuid4()), profile_id="fixture", host_id="host")
    receipt = seal_archive(media, {"vault/note.md": path}, capture=capture, **identity)
    return profile, receipt, recovery / "restored"


@pytest.mark.parametrize("existing", [False, True])
def test_checked_restore_and_repeat(generation, existing):
    profile, receipt, target = generation
    if existing:
        restore._mkdir(target)
    assert verify_restore(profile, receipt["backup_id"]) == receipt
    def validate(stage, manifest):
        assert stage != target
        assert not target.exists() or not list(target.iterdir())
        assert (stage / "vault/empty").is_dir()
        assert (stage / "vault/note.md").read_bytes() == b"canonical fixture"
        assert manifest["capture"]["shared_session_root"] is True
    result = restore_backup(profile, receipt["backup_id"], target=target, validate_staged=validate)
    assert result == json.loads((target / "restore.receipt.json").read_bytes())
    assert result["manifest_sha256"] == receipt["manifest_sha256"]
    with pytest.raises(RestoreError, match="empty"):
        restore_backup(profile, receipt["backup_id"], target=target, validate_staged=validate)
    assert not list(target.parent.glob(".m18-restore-*"))


def test_operator_restore_verification_and_explicit_apply(generation, capsys):
    from laew.operator_cli import dispatch

    profile, receipt, target = generation
    profile_path = target.parent / "profile.json"
    profile_path.write_text(json.dumps(profile, default=str), encoding="utf-8")
    command = ["restore", "--profile", str(profile_path), "--id", receipt["backup_id"], "--json"]
    assert dispatch([*command, "--verify-only"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["verification"] == "archive"
    assert not target.exists()
    assert dispatch([*command, "--target", str(target)]) == 2
    assert json.loads(capsys.readouterr().out)["error_code"] == "invalid_arguments"
    assert not target.exists()
    assert dispatch([*command, "--target", str(target), "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["verification"] == "isolated"
    assert (target / "restore.receipt.json").is_file()


@pytest.mark.parametrize("change", ["reject", "mutate", "extra", "hardlink", "missing"])
def test_semantic_or_postvalidation_failure_preserves_target(generation, change):
    profile, receipt, target = generation
    restore._mkdir(target)
    def validate(stage, manifest):
        file = stage / "vault/note.md"
        if change == "reject":
            raise RestoreError("identity mismatch")
        if change == "mutate":
            file.write_bytes(b"wrong")
        elif change == "extra":
            (stage / "extra").mkdir()
        elif change == "hardlink":
            os.link(file, stage / "vault/copy.md")
        else:
            file.unlink()
    with pytest.raises(ValueError):
        restore_backup(profile, receipt["backup_id"], target=target, validate_staged=validate)
    assert list(target.iterdir()) == []
    assert list(target.parent.iterdir()) == [target]


def test_partial_publication_or_racing_target(generation, monkeypatch):
    profile, receipt, target = generation
    publish = restore._publish
    def interrupted(stage, target):
        target.mkdir()
        (target / "other").write_bytes(b"keep")
        publish(stage, target)
    monkeypatch.setattr(restore, "_publish", interrupted)
    with pytest.raises(OSError):
        restore_backup(profile, receipt["backup_id"], target=target, validate_staged=lambda *_: None)
    assert (target / "other").read_bytes() == b"keep"
    assert list(target.parent.iterdir()) == [target]


def test_refuse_targets_aliases_and_profile_mismatch(generation):
    profile, receipt, target = generation
    for unsafe in (profile["destination"] / "target", profile["workspace_root"] / "target", Path("../target")):
        with pytest.raises(ValueError):
            restore_backup(profile, receipt["backup_id"], target=unsafe, validate_staged=lambda *_: None)
    with pytest.raises(RestoreError):
        verify_restore(dict(profile, host_id="other"), receipt["backup_id"])
    with pytest.raises(RestoreError):
        restore_backup(profile, receipt["backup_id"], target=target, validate_staged=None)
    assert not target.exists()


def test_legacy_archive_read_only_and_corrupt_bytes(generation):
    profile, receipt, target = generation
    identity = dict(backup_id=str(uuid4()), cut_id=str(uuid4()), host_id="host", profile_id="fixture")
    legacy = seal_archive(profile["destination"], {}, **identity)
    assert verify_restore(profile, identity["backup_id"]) == legacy
    with pytest.raises(RestoreError, match="identity"):
        restore_backup(profile, identity["backup_id"], target=target, validate_staged=lambda *_: None)
    archive = profile["destination"] / (receipt["backup_id"] + ".zip")
    data = archive.read_bytes().replace(b"canonical fixture", b"changed   fixture")
    archive.write_bytes(data)
    with pytest.raises(ArchiveError):
        restore_backup(profile, receipt["backup_id"], target=target, validate_staged=lambda *_: None)
    assert not target.exists()


def test_process_interruption_leaves_target_and_backup_usable(generation):
    profile, receipt, target = generation
    restore._mkdir(target)
    script = """
import json, os, sys
from laew.backup.restore import restore_backup
profile, backup_id, target = sys.argv[1:]
restore_backup(json.loads(profile), backup_id, target=target, validate_staged=lambda *_: os._exit(74))
"""
    result = subprocess.run([sys.executable, "-c", script, json.dumps(profile, default=str),
                             receipt["backup_id"], str(target)], capture_output=True, timeout=20)
    assert result.returncode == 74, result.stderr
    assert not list(target.iterdir())
    assert verify_restore(profile, receipt["backup_id"]) == receipt
    assert len(list(target.parent.glob(".m18-restore-*"))) == 1
    assert restore_backup(profile, receipt["backup_id"], target=target,
                          validate_staged=lambda *_: None)["state"] == "isolated"


def test_directory_alias_is_rejected(generation):
    profile, receipt, target = generation
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(target), str(profile["destination"])],
                       check=True, capture_output=True)
    else:
        target.symlink_to(profile["destination"], target_is_directory=True)
    try:
        with pytest.raises(ValueError):
            restore_backup(profile, receipt["backup_id"], target=target, validate_staged=lambda *_: None)
        assert not (target / "restore.receipt.json").exists()
    finally:
        if os.name == "nt":
            target.rmdir()
        else:
            target.unlink()


def test_unknown_logical_member_rejected_before_validator(generation):
    profile, _, target = generation
    backup_id = str(uuid4())
    capture = dict(directories=["conversations", "vault"], shared_session_root=True,
                   manifest_sha256="1"*64, package_python_sha256="2"*64)
    seal_archive(profile["destination"], {"unknown/file": profile["workspace_root"] / "note.md"},
                 backup_id=backup_id, cut_id=str(uuid4()), profile_id="fixture", host_id="host", capture=capture)
    with pytest.raises(RestoreError, match="Unknown logical"):
        restore_backup(profile, backup_id, target=target, validate_staged=lambda *_: pytest.fail("unexpected runtime"))
    assert not target.exists()


def test_receipt_persists_only_allowlisted_semantic_block(generation):
    profile, receipt, target = generation
    result = restore_backup(profile, receipt['backup_id'], target=target,
                            validate_staged=lambda *_: {'status': 'validated', 'blocked_missing_jobs': 2,
                                                       'missing_historical_references': 3, 'secret': 'canary'})
    summary = result['recovery_validation']
    assert summary == {'status': 'reported', 'activation_blocked': True, 'blocked_missing_jobs': 2,
                       'missing_historical_references': 3, 'memory_namespace': 'not_applicable'}
    assert json.loads((target / 'restore.receipt.json').read_text())['recovery_validation'] == summary
    assert 'canary' not in json.dumps(result)


def test_legacy_callback_has_unknown_validation(generation):
    profile, receipt, target = generation
    result = restore_backup(profile, receipt['backup_id'], target=target, validate_staged=lambda *_: None)
    assert result['recovery_validation']['status'] == 'not_reported'
    assert result['recovery_validation']['activation_blocked'] is None


@pytest.mark.parametrize('namespace', ['matched', 'mismatch', 'unknown'])
def test_memory_namespace_identity_and_legacy_unknown(generation, namespace):
    from laew.backup.inventory import memory_namespace_sha256
    profile, _, target = generation
    memory_path = target.parent.parent / 'fixture-memory.db'
    memory_path.write_bytes(b'synthetic db')
    profile.update(memory_enabled=True, memory_storage=memory_path)
    metadata = dict(directories=['conversations', 'vault'], shared_session_root=True,
                    manifest_sha256='1' * 64, package_python_sha256='2' * 64)
    if namespace != 'unknown':
        metadata['memory_namespace_sha256'] = (memory_namespace_sha256(memory_path) if namespace == 'matched'
                                                 else '0' * 64)
    key = str(uuid4())
    seal_archive(profile['destination'], {'memory_db/memory.db': memory_path}, backup_id=key,
                 cut_id=str(uuid4()), profile_id='fixture', host_id='host', capture=metadata)
    if namespace == 'mismatch':
        with pytest.raises(RestoreError):
            restore_backup(profile, key, target=target, validate_staged=lambda *_: None)
        assert not target.exists()
    else:
        result = restore_backup(profile, key, target=target, validate_staged=lambda *_: None)
        assert result['recovery_validation']['memory_namespace'] == namespace
