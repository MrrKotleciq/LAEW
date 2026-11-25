from datetime import datetime, timedelta, timezone
import os
import stat

import pytest

from laew.backup import health
from laew.backup.archive import _json
from laew.status import collect_status
from tests.integration.test_m18_worker_wheel import _private_directory


@pytest.fixture
def channel(tmp_path, monkeypatch):
    # Portable status-contract tests still validate the channel and file ACLs.
    # Real ancestry requires a separately provisioned Windows path.
    monkeypatch.setattr(health, "_check_ancestry", lambda *args: None)
    directory = tmp_path / "advisory"
    _private_directory(directory)
    if os.name == "nt":
        from laew.security.windows_security import get_current_user_sid
        owner = get_current_user_sid()
    else:
        owner = str(os.geteuid())
    return directory / "status.json", owner


def _document(now, outcome="verified", reason="archive_verified", last=None):
    last = last or now
    return dict(schema_version=1, profile_id="fixture", observed_at_utc=now.isoformat(),
                last_attempt=dict(operation="capture", completed_at_utc=now.isoformat(),
                                  outcome=outcome, reason=reason),
                last_verified_at_utc=last.isoformat())


def test_status_contract_staleness_and_preserved_previous_generation(channel):
    path, owner = channel
    now = datetime.now(timezone.utc)
    call = lambda: health.summarize_status(path, "fixture", owner, now)
    assert call() == ("unknown", "worker_status_unavailable", {})
    health._publish(path, owner, _document(now))
    assert call() == ("ok", "archive_verified", {"last_attempt_outcome": "verified", "age_seconds": 0})
    result = health.summarize_status(path, "fixture", owner, now + timedelta(hours=25))
    assert result[:2] == ("degraded", "stale_receipt")
    result = health.summarize_status(path, "fixture", owner, now + timedelta(hours=27))
    assert result == ("unknown", "status_stale", {})

    one_hour_ago = now - timedelta(hours=1)
    health._publish(path, owner, _document(now, "failed", "capture_failed", last=one_hour_ago))
    assert call() == ("degraded", "capture_failed", {"last_attempt_outcome": "failed", "age_seconds": 3600})
    health._publish(path, owner, _document(now, "skipped", "writer_busy", last=one_hour_ago))
    assert call() == ("degraded", "writer_busy", {"last_attempt_outcome": "skipped", "age_seconds": 3600})


@pytest.mark.parametrize("fault", ["oversized", "future", "schema", "owner", "hardlink", "extra_field"])
def test_untrusted_status_fails_soft(channel, fault):
    path, owner = channel
    now = datetime.now(timezone.utc)
    doc = _document(now)
    if fault == "future":
        doc = _document(now + timedelta(hours=1))
    if fault == "schema":
        doc["schema_version"] = 2
    if fault == "extra_field":
        doc["private_path"] = "private-canary"
    path.write_bytes(_json(doc) if fault != "oversized" else b"x" * (health.STATUS_LIMIT + 1))
    if fault == "owner":
        owner = "S-1-5-18" if os.name == "nt" else str(int(owner) + 1)
    if fault == "hardlink":
        os.link(path, path.with_name("hardlink"))
    assert health.summarize_status(path, "fixture", owner, now) == ("unknown", "worker_status_unavailable", {})


def test_atomic_replace_failure_keeps_old_status(channel, monkeypatch):
    path, owner = channel
    now = datetime.now(timezone.utc)
    health._publish(path, owner, _document(now))
    before = path.read_bytes()

    def refuse(*args):
        raise PermissionError("reader holds an incompatible handle")

    monkeypatch.setattr(health.os, "replace", refuse)
    with pytest.raises(PermissionError):
        health._publish(path, owner, _document(now, "failed", "capture_failed"))
    assert path.read_bytes() == before
    assert list(path.parent.iterdir()) == [path]


def test_core_reads_advisory_without_archive_or_profile(channel, monkeypatch, tmp_path):
    path, owner = channel
    now = datetime.now(timezone.utc)
    health._publish(path, owner, _document(now))
    from laew.backup import inventory

    def refuse(*args):
        pytest.fail("Core must not open private backup metadata for worker status")

    monkeypatch.setattr(inventory, "backup_target_from_profile", refuse)
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("workspace: {root: .}\n", encoding="utf-8")
    monkeypatch.setattr("laew.status.load_manifest", lambda _: {"workspace": {"root": "."}})
    result = collect_status(manifest, worker_status=(path, "fixture", owner), now=now)
    backup = next(check for check in result["checks"] if check["component"] == "backup")
    assert backup["state"] == "ok" and backup["required"] is True
    assert backup["source"] == "worker_status" and str(path) not in str(backup)


def test_ancestry_rejects_untrusted_directory(monkeypatch):
    from types import SimpleNamespace

    class Directory:
        def __init__(self, uid, mode):
            self.uid, self.mode = uid, mode
        def lstat(self):
            return SimpleNamespace(st_uid=self.uid, st_mode=stat.S_IFDIR | self.mode)

    class Ancestry:
        def __init__(self, directories):
            self.directories = directories
            self.parents = directories[1:]
        def lstat(self):
            return self.directories[0].lstat()

    monkeypatch.setattr(health, "os", SimpleNamespace(name="posix"))
    private = Directory(1000, 0o700)
    sticky = Directory(0, 0o1777)
    root = Directory(0, 0o755)
    health._check_ancestry(Ancestry([private, sticky, root]), "1000")
    with pytest.raises(ValueError):
        health._check_ancestry(Ancestry([private, Directory(0, 0o777), root]), "1000")
    with pytest.raises(ValueError):
        health._check_ancestry(Ancestry([private, Directory(2000, 0o700), root]), "1000")
    with pytest.raises(ValueError):
        health._check_ancestry(Ancestry([private, Directory(2000, 0o1777), root]), "1000")


def test_workbench_view_rejects_untrusted_ancestry(monkeypatch, tmp_path):
    from laew.backup.controls import workbench_view

    path = tmp_path / "backup-settings.json"
    path.write_text("{}", encoding="ascii")
    monkeypatch.setattr(health, "_check_owner", lambda *args: None)
    def reject(*args):
        raise ValueError("untrusted ancestor")
    monkeypatch.setattr(health, "_check_ancestry", reject)
    assert workbench_view(path, "owner")["local"] == "unavailable"


def test_windows_ancestry_rejects_untrusted_grant(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from laew.security import windows_security

    monkeypatch.setattr(health, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(windows_security, "get_path_owner_sid", lambda path: "S-1-5-18")
    visited = []
    def check(path, owner):
        visited.append(path)
        if path == tmp_path.parent:
            raise windows_security.WindowsSecurityError("untrusted access grant")
    monkeypatch.setattr(windows_security, "assert_trusted_owned_path", check)
    with pytest.raises(windows_security.WindowsSecurityError):
        health._check_ancestry(tmp_path, "S-1-5-21-100")
    assert visited == list(reversed(tmp_path.parents))


@pytest.mark.skipif(os.name != "posix", reason="native POSIX ancestry")
def test_native_posix_private_ancestry(tmp_path):
    health._check_ancestry(tmp_path, str(os.geteuid()))
