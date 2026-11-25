from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from laew.backup import controller, managed, policy
from laew.backup.archive import seal_archive
from laew.operator_cli import _load_inventory, dispatch
from tests.integration.test_m18_operator_backup import profile


@pytest.fixture
def controlled(profile, monkeypatch):
    path, doc = profile
    if os.name == "nt":
        # The sandbox injects a trustee into fixture DACLs.
        monkeypatch.setattr("laew.security.windows_security.assert_private_owned_path", lambda *_: None)
    else:
        for folder in (path.parent, Path(doc["destination"])):
            folder.chmod(0o700)
        path.chmod(0o600)
    return path, doc


def test_disable_serializes_new_admissions_and_preserves_archives(controlled):
    path, doc = controlled
    staged = path.parent / "note.md"
    staged.write_bytes(b"fixture")
    identifier = str(uuid4())
    seal_archive(doc["destination"], {"vault/note.md": staged}, backup_id=identifier,
                 cut_id=str(uuid4()), profile_id=doc["profile_id"], host_id=doc["host_id"])
    media = Path(doc["destination"])
    originals = {entry.name: entry.read_bytes() for entry in media.iterdir()}
    policy.initialize_policy(path, managed=False)
    assert policy.policy_state(path) == "disabled"
    old_revision = policy.policy_revision(path)
    policy.set_enabled(path, enabled=True, expected_revision=old_revision)
    with pytest.raises(ValueError, match="revision"):
        policy.set_enabled(path, enabled=False, expected_revision=old_revision)
    with policy.admission(path, operation="capture"):
        assert policy.set_enabled(path, enabled=False) == "disabling"
        with pytest.raises(ValueError, match="disabled"):
            with policy.admission(path, operation="replicate"):
                pytest.fail("Disabled operations must not enter.")
    assert policy.policy_state(path) == "disabled"
    assert originals == {entry.name: entry.read_bytes() for entry in media.iterdir()}
    assert dispatch(["backup", "verify", "--profile", str(path), "--id", identifier, "--json"]) == 0


class TestServiceManager:
    __test__ = False

    def __init__(self, *, orphan=False, fail=False):
        self.states = {"core.service": "active", "maintenance.service": "inactive", "worker.service": "inactive"}
        self.actions = []
        self.orphan = orphan
        self.fail = fail

    def state(self, unit):
        phase = self.states[unit]
        return {"ActiveState": phase, "ControlGroup": "/" + unit if phase == "active" else "",
                "Result": "success", "ExecMainCode": "1", "ExecMainStatus": "0"}

    def empty(self, group):
        return not self.orphan or group != "/core.service"

    def stop(self, unit):
        self.states[unit] = "inactive"
        self.actions.append(("stop", unit))

    def start(self, unit, *, wait=False):
        self.actions.append(("start", unit))
        if wait:
            if self.fail:
                self.states[unit] = "active"
                raise ValueError("Lost controller/worker response")
        else:
            self.states[unit] = "active"


@pytest.fixture
def coordinator(controlled, monkeypatch):
    path, doc = controlled
    units = ["core.service", "maintenance.service"]
    root = path.parent / "gate"
    root.mkdir()
    (root / "installation.lock").touch()
    stable_boot = str(uuid4())
    gate = root / "gate.json"
    monkeypatch.setattr(controller, "configuration", lambda _: (root, path, doc["fence"], units, "worker.service", {}))
    monkeypatch.setattr(controller, "_system_operator", lambda: True)
    for module in (controller, managed):
        monkeypatch.setattr(module, "protected_path", Path)
        monkeypatch.setattr(module, "boot_id", lambda: stable_boot)
    # Install a synthetic controller-owned open record. ACL ownership is tested on the Debian host separately.
    gate.write_text(json.dumps(dict(schema_version=1, phase="open", boot_id=stable_boot, units=units,
                                    originally_active=[], profile_sha256=policy.profile_digest(path),
                                    fence_identity=managed.fence_identity(doc["fence"]), backup_id=None,
                                    cut_id=None, valid_until=None)), encoding="utf-8")
    return path, doc, gate


def test_controller_resumes_only_initially_active_services(coordinator, monkeypatch):
    _, _, gate = coordinator
    manager = TestServiceManager()
    def verified(*_):
        assert managed.read_gate(gate)[0]["phase"] == "held"
        manager.actions.append(("verify", "generation"))
    monkeypatch.setattr(controller, "_verify_generation", verified)
    assert controller.run_controller(gate, "capture", manager=manager)
    assert manager.actions == [("stop", "core.service"), ("start", "worker.service"),
                               ("verify", "generation"), ("start", "core.service")]
    managed.writer_gate_open(gate, "core.service")


def test_missing_archive_receipt_cannot_release_gate(coordinator):
    _, _, gate = coordinator
    manager = TestServiceManager()
    with pytest.raises((OSError, ValueError)):
        controller.run_controller(gate, "capture", manager=manager)
    assert managed.read_gate(gate)[0]["phase"] == "held"
    assert ("start", "core.service") not in manager.actions


@pytest.mark.parametrize("orphan", [True, False])
def test_uncertain_writer_or_worker_state_keeps_gate_closed(coordinator, orphan):
    _, _, gate = coordinator
    manager = TestServiceManager(orphan=orphan, fail=not orphan)
    with pytest.raises(ValueError):
        controller.run_controller(gate, "capture", manager=manager)
    with pytest.raises(ValueError, match="inhibited"):
        managed.writer_gate_open(gate, "core.service")
    assert ("start", "core.service") not in manager.actions
    if not orphan:
        with pytest.raises(ValueError, match="still running"):
            controller.run_controller(gate, "recover", manager=manager)
        manager.states["worker.service"] = "inactive"
        controller.run_controller(gate, "recover", manager=manager)
        managed.writer_gate_open(gate, "core.service")


def test_managed_cut_is_single_use_and_bound_to_live_gate(coordinator):
    path, doc, gate = coordinator
    policy.initialize_policy(path, managed=True)
    policy.set_enabled(path, enabled=True)
    inv = _load_inventory(doc)
    state, _ = managed.read_gate(gate)
    proof = {**state, "phase": "held", "backup_id": str(uuid4()), "cut_id": str(uuid4()),
             "valid_until": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()}
    gate.write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(ValueError, match="mode"):
        with policy.admission(path, operation="capture"):
            pytest.fail("Supervised capture bypassed managed policy.")
    with policy.admission(path, operation="capture", managed=True):
        cut = managed.ManagedCut(gate, path, inv, None)
        cut.check(inv.fence)
        with pytest.raises(FileExistsError):
            managed.ManagedCut(gate, path, inv, None)
        gate.write_text(json.dumps({**proof, "phase": "resuming"}), encoding="utf-8")
        with pytest.raises(ValueError, match="no longer valid"):
            cut.check(inv.fence)


def test_managed_worker_publishes_a_real_fixture_generation(coordinator, monkeypatch):
    import hashlib
    from laew import backup_worker
    from laew.backup.capture import package_python_sha256

    path, doc, gate = coordinator
    policy.initialize_policy(path, managed=True)
    policy.set_enabled(path, enabled=True)
    state, _ = managed.read_gate(gate)
    proof = {**state, "phase": "held", "backup_id": str(uuid4()), "cut_id": str(uuid4()),
             "valid_until": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()}
    gate.write_text(json.dumps(proof), encoding="utf-8")
    (Path(doc["vault"]) / "note.md").write_bytes(b"synthetic")
    core = path.parent / "core"
    core.mkdir()
    (core / "__init__.py").write_text("# reviewed fixture", encoding="utf-8")
    review_dir = path.parent / "review"
    review_dir.mkdir(mode=0o700 if os.name != "nt" else 0o777)
    review = review_dir / "release.json"
    review.write_text(json.dumps(dict(schema_version=1, profile_id=doc["profile_id"], host_id=doc["host_id"],
                           core_release="fixture", core_package_root=str(core),
                           core_package_python_sha256=package_python_sha256(core),
                           worker_package_python_sha256=package_python_sha256(Path(backup_worker.__file__).parent),
                           profile_sha256=policy.profile_digest(path),
                           manifest_sha256=hashlib.sha256(Path(doc["manifest_path"]).read_bytes()).hexdigest())), encoding="utf-8")
    if os.name != "nt":
        review.chmod(0o600)
    monkeypatch.setattr("laew.backup.provenance.validate_worker_runtime", lambda: None)
    args = ["managed-create", "--profile", str(path), "--gate", str(gate), "--provenance", str(review), "--apply", "--json"]
    assert backup_worker.main(args) == 0
    assert backup_worker.main(args) == 1
    controller._verify_generation(path, proof["backup_id"], proof["cut_id"])


def test_workbench_projection_excludes_unapproved_fields_and_stale_health(controlled, monkeypatch):
    from laew.backup import controls

    path, _ = controlled
    view = controls._view(path)
    view.update(local_backup="ok", connection="connected", remote="verified",
                observed_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat())
    parent = path.parent / "public"
    parent.mkdir()
    projection = parent / "backup-settings.json"
    projection.write_text(json.dumps(view), encoding="utf-8")
    # This case checks the projection payload with a synthetic owner.
    monkeypatch.setattr("laew.backup.health._check_owner", lambda *_: None)
    monkeypatch.setattr("laew.backup.health._check_ancestry", lambda *_: None)
    result = controls.workbench_view(projection, "publisher")
    assert result["local_backup"] == "unknown"
    assert result["remote"] == "unconfigured"
    projection.write_text(json.dumps({**view, "private_key": "inadmissible"}), encoding="utf-8")
    assert controls.workbench_view(projection, "publisher")["revision"] is None


def test_operator_proposal_matches_profile_and_destination_only(controlled, tmp_path):
    from argparse import Namespace
    from laew.backup import controls

    path, doc = controlled
    proposal = tmp_path / "proposal.json"
    values = dict(schema_version=1, operation="settings", revision=policy.policy_revision(path), enabled=False,
                  directory=doc["destination"], host="", port=None, user="", remote_directory="", key="")
    proposal.write_text(json.dumps(values), encoding="utf-8")
    assert controls._validate_proposal(Namespace(profile=path, proposal=proposal), "settings") == values
    proposal.write_text(json.dumps({**values, "directory": doc["vault"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="new backup profile"):
        controls._validate_proposal(Namespace(profile=path, proposal=proposal), "settings")


def test_systemd_252_show_omits_empty_environmentfiles(monkeypatch):
    import hashlib

    unit = "bw08-worker.service"
    fragment = "# fixture unit\n[Service]\nType=oneshot\n"
    manager = controller.Systemd({unit: hashlib.sha256(fragment.encode()).hexdigest()})
    output = """Type=oneshot
Restart=no
RemainAfterExit=no
Result=success
ExecMainCode=0
ExecMainStatus=0
ExecStart={ path=/fixture/venv/bin/python ; argv[]=/fixture/venv/bin/python ; }
ControlGroup=
Delegate=no
Environment=
User=bw08worker
NoNewPrivileges=yes
KillMode=mixed
Id=bw08-worker.service
TriggeredBy=
LoadState=loaded
ActiveState=inactive
SubState=dead
FragmentPath=/etc/systemd/system/bw08-worker.service
DropInPaths=
Job=
NeedDaemonReload=no
"""
    monkeypatch.setattr(controller, "protected_path", Path)
    monkeypatch.setattr(manager, "_run", lambda command, *_: fragment if command == "cat" else output)
    assert manager.state(unit)["ActiveState"] == "inactive"
    output += "EnvironmentFiles=/fixture/other.env (ignore_errors=no)\n"
    with pytest.raises(ValueError, match="semantics"):
        manager.state(unit)
