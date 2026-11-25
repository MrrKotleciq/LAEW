"""On-demand Debian controller for a fixed fixture writer topology."""

import argparse
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import shlex
from uuid import uuid4

from .fence import host_fence
from .managed import _UNIT, boot_id, fence_identity, protected_path, read_gate
from .policy import atomic_json, control_path, profile_digest


class Systemd:
    """Use the system manager and never accept a shell command from config."""

    def _run(self, *args):
        return subprocess.run([str(protected_path(Path("/usr/bin/systemctl"))),
                               "--no-pager", "--no-ask-password", *args],
                              check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd="/", env={"LANG": "C", "PATH": "/usr/bin:/bin"}, timeout=90).stdout

    def __init__(self, pins):
        self.pins = pins

    def state(self, unit):
        names = ("Id", "LoadState", "ActiveState", "SubState", "FragmentPath", "ControlGroup", "Job",
                 "Result", "ExecMainCode", "ExecMainStatus", "User", "DropInPaths", "Restart",
                 "NeedDaemonReload", "Environment", "EnvironmentFiles", "NoNewPrivileges", "Delegate",
                 "ExecStart", "TriggeredBy", "KillMode", "Type", "RemainAfterExit")
        result = dict(line.split("=", 1) for line in
                      self._run("show", "--all", "--property=" + ",".join(names), "--", unit).splitlines())
        # systemctl 252 prints no line for an empty EnvironmentFiles array,
        # even with --all. A configured file still prints a nonempty entry.
        if (set(result) | {"EnvironmentFiles"} != set(names)
                or result["Id"] != unit or result["LoadState"] != "loaded"
                or not result["FragmentPath"] or result["Job"] not in ("", "0")):
            raise ValueError("Systemd unit is not in a reviewed terminal state.")
        protected_path(Path(result["FragmentPath"]))
        for dropin in shlex.split(result["DropInPaths"]):
            protected_path(Path(dropin))
        content = self._run("cat", "--", unit)
        if (hashlib.sha256(content.encode("utf-8")).hexdigest() != self.pins[unit]
                or result["NeedDaemonReload"] != "no" or result["Restart"] != "no"
                or result["Delegate"] != "no" or result["NoNewPrivileges"] != "yes"
                or result.get("EnvironmentFiles") or result["TriggeredBy"]
                or result["KillMode"] not in ("control-group", "mixed")):
            raise ValueError("Systemd service semantics or reviewed unit changed.")
        executable = result["ExecStart"].partition("{ path=")[2].partition(" ;")[0]
        if not executable:
            raise ValueError("Managed units require one protected entry point.")
        protected_path(Path(executable))
        return result

    def empty(self, group):
        if not group:
            return True
        path = Path(group)
        if not path.is_absolute() or path == Path("/") or ".." in path.parts:
            raise ValueError("Invalid systemd process group.")
        directory = Path("/sys/fs/cgroup") / path.relative_to("/")
        if not directory.exists():
            return True
        events = dict(line.split() for line in (directory / "cgroup.events").read_text().splitlines())
        return events.get("populated") == "0"

    def stop(self, unit):
        self._run("stop", "--", unit)

    def start(self, unit, *, wait=False):
        self._run("start", *(("--wait",) if wait else ()), "--", unit)

    @contextmanager
    def retain_exit_status(self, units):
        """Keep the named units loaded until their exit codes are checked."""
        import ctypes
        import sysconfig

        if "DBUS_SYSTEM_BUS_ADDRESS" in os.environ:
            raise ValueError("The controller requires the local system bus.")
        arch = sysconfig.get_config_var("MULTIARCH")
        if not isinstance(arch, str) or not arch.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Unknown Debian system library path.")
        library = Path("/usr/lib") / arch / "libsystemd.so.0"
        protected_path(library.parent)
        sd = ctypes.CDLL(str(protected_path(library.resolve(strict=True))))
        pointer = ctypes.c_void_p
        string = ctypes.c_char_p
        sd.sd_bus_open_system.argtypes = (ctypes.POINTER(pointer),)
        sd.sd_bus_open_system.restype = ctypes.c_int
        sd.sd_bus_set_method_call_timeout.argtypes = (pointer, ctypes.c_uint64)
        sd.sd_bus_set_method_call_timeout.restype = ctypes.c_int
        sd.sd_bus_call_method.argtypes = (pointer, string, string, string, string, pointer, pointer, string)
        sd.sd_bus_call_method.restype = ctypes.c_int
        sd.sd_bus_close_unref.argtypes = (pointer,)
        sd.sd_bus_close_unref.restype = pointer
        bus = pointer()
        if sd.sd_bus_open_system(ctypes.byref(bus)) < 0:
            raise ValueError("Cannot establish the local system manager session.")
        try:
            if sd.sd_bus_set_method_call_timeout(bus, 5_000_000) < 0:
                raise ValueError("Cannot bound the unit reference timeout.")
            for unit in units:
                result = sd.sd_bus_call_method(bus, b"org.freedesktop.systemd1", b"/org/freedesktop/systemd1",
                                               b"org.freedesktop.systemd1.Manager", b"RefUnit", None, None,
                                               b"s", string(unit.encode("ascii")))
                if result < 0:
                    raise ValueError("Cannot retain a reviewed writer unit.")
            yield
        finally:
            sd.sd_bus_close_unref(bus)


def configuration(path):
    from laew.operator_cli import _bounded_file, _load_profile, _unique_object

    config_file = protected_path(path)
    doc = json.loads(_bounded_file(config_file, 65536), object_pairs_hook=_unique_object)
    fields = {"schema_version", "profile", "writer_services", "worker_service", "unit_sha256"}
    if type(doc) is not dict or doc.keys() != fields or type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
        raise ValueError("Invalid managed controller configuration.")
    writers, worker = doc["writer_services"], doc["worker_service"]
    if (type(writers) is not list or not 0 < len(writers) <= 16
            or any(type(name) is not str or not _UNIT.fullmatch(name) for name in writers)
            or len(set(writers)) != len(writers) or type(worker) is not str
            or not _UNIT.fullmatch(worker) or worker in writers):
        raise ValueError("Invalid fixed unit roster.")
    from .archive import _digest
    pins = doc["unit_sha256"]
    if type(pins) is not dict or set(pins) != set(writers) | {worker} or not all(_digest(v) for v in pins.values()):
        raise ValueError("Each exact systemd unit requires an approved digest.")
    profile = Path(doc["profile"])
    if not profile.is_absolute() or ".." in profile.parts:
        raise ValueError("Invalid managed profile path.")
    fence = _load_profile(str(profile))["fence"]
    return config_file.parent, profile, fence, sorted(writers), worker, pins


def _drained(manager, unit, previous_group=""):
    state = manager.state(unit)
    return (state["ActiveState"] == "inactive" and manager.empty(previous_group)
            and manager.empty(state["ControlGroup"]))


def _system_operator():
    return os.name == "posix" and os.geteuid() == 0


def _managed_policy_ready(profile, worker_user):
    import pwd
    from laew.operator_cli import _bounded_file, _unique_object
    from .inventory import _inspect

    if not worker_user:
        raise ValueError("The backup service requires a dedicated worker account.")
    uid = pwd.getpwnam(worker_user).pw_uid
    root = control_path(profile)
    path = root / "policy.json"
    for entry in (root, path):
        info = _inspect(entry).lstat()
        if uid == 0 or info.st_uid != uid or info.st_mode & 0o077:
            raise ValueError("Invalid managed worker policy ownership.")
    document = json.loads(_bounded_file(path, 65536), object_pairs_hook=_unique_object)
    if (not stat.S_ISREG(path.lstat().st_mode) or document.get("managed") is not True
            or document.get("profile_sha256") != profile_digest(profile)
            or os.path.lexists(root / "disabled")):
        raise ValueError("Managed capture policy is disabled or invalid.")


def _validate_units(manager, root, fence, units, worker):
    import pwd

    worker_state = manager.state(worker)
    if worker_state["Type"] != "oneshot" or worker_state["RemainAfterExit"] != "no" or not worker_state["User"]:
        raise ValueError("Managed worker must be a terminal oneshot service.")
    owners = set()
    gate = root / "gate.json"
    info = gate.lstat() if gate.exists() else root.lstat()
    root_mode = root.lstat().st_mode
    if root_mode & (stat.S_ISGID | stat.S_IXGRP) != (stat.S_ISGID | stat.S_IXGRP):
        raise ValueError("Gate directory requires setgid and reader traversal.")
    if gate.exists() and (not info.st_mode & stat.S_IRGRP or info.st_gid != root.lstat().st_gid):
        raise ValueError("Gate did not inherit the reviewed reader group.")
    for unit in [*units, worker]:
        state = worker_state if unit == worker else manager.state(unit)
        if not state["User"]:
            raise ValueError("Managed services need explicit accounts.")
        account = pwd.getpwnam(state["User"])
        groups = os.getgrouplist(account.pw_name, account.pw_gid)
        if account.pw_uid == 0 or info.st_gid not in groups:
            raise ValueError("Managed service identity cannot use the protected reader group.")
        for parent in root.parents:
            ancestor = parent.lstat()
            required = stat.S_IXGRP if ancestor.st_gid in groups else stat.S_IXOTH
            if not ancestor.st_mode & required:
                raise ValueError("A managed service cannot traverse the gate ancestry.")
        if unit != worker:
            owners.add(account.pw_uid)
            environment = dict(item.split("=", 1) for item in shlex.split(state["Environment"]))
            if any(environment.get(key) != value for key, value in {
                "LAEW_INSTALLATION_FENCE": str(fence),
                "LAEW_MANAGED_WRITER_GATE": str(gate),
                "LAEW_MANAGED_WRITER_UNIT": unit,
            }.items()):
                raise ValueError("A writer unit is missing mandatory gate enrollment.")
    if len(owners) != 1 or pwd.getpwnam(worker_state["User"]).pw_uid in owners:
        raise ValueError("Managed writer and worker identities must be distinct.")
    return worker_state["User"]


def _verify_generation(profile, backup_id, cut_id):
    from laew.operator_cli import _load_profile
    from .archive import verify_archive
    from .inventory import backup_target_from_profile

    target = backup_target_from_profile(_load_profile(str(profile)))
    receipt = verify_archive(target.destination, backup_id)
    if (receipt["cut_id"], receipt["profile_id"], receipt["host_id"]) != (cut_id, target.profile_id, target.host_id):
        raise ValueError("The worker did not commit this managed generation.")


def run_controller(config_file, action, *, manager=None):
    """Keep the restart gate durable on every uncertain state or exception."""
    if not _system_operator():
        raise ValueError("The Debian controller requires the system operator.")
    root, profile, fence, units, worker, pins = configuration(config_file)
    native = manager is None
    manager = manager if manager is not None else Systemd(pins)
    gate = root / "gate.json"

    def publish(phase, active=(), backup_id=None, cut_id=None, until=None):
        atomic_json(gate, {"schema_version": 1, "phase": phase, "boot_id": boot_id(), "units": units,
                           "originally_active": list(active), "profile_sha256": profile_digest(profile),
                           "fence_identity": fence_identity(fence), "backup_id": backup_id,
                           "cut_id": cut_id, "valid_until": until}, mode=0o640)
        protected_path(gate)

    def resume(active):
        if not _drained(manager, worker):
            raise ValueError("Worker still running or terminal state uncertain.")
        publish("resuming", active)
        for unit in active:
            if _drained(manager, unit):
                manager.start(unit)
            if manager.state(unit)["ActiveState"] != "active":
                raise ValueError("An originally active writer did not resume.")
        publish("open")

    with host_fence(root, mode="maintenance"):
        worker_user = _validate_units(manager, root, fence, units, worker) if native else None
        if action == "initialize":
            if os.path.lexists(gate) or not _drained(manager, worker) or any(not _drained(manager, unit) for unit in units):
                raise ValueError("Gate initialization requires inactive reviewed units.")
            publish("open")
            return
        previous, _ = read_gate(gate, require_boot=action != "recover")
        if (previous["units"] != units or previous["profile_sha256"] != profile_digest(profile)
                or previous["fence_identity"] != fence_identity(fence)):
            raise ValueError("Fixed controller topology changed.")
        if action == "recover":
            if previous["phase"] == "open" and previous["boot_id"] == boot_id():
                return
            resume(previous["originally_active"])
            return
        if action != "capture" or previous["phase"] != "open" or not _drained(manager, worker):
            raise ValueError("Controller requires a fresh open gate and idle worker.")
        if native:
            _managed_policy_ready(profile, worker_user)
        initial = {unit: manager.state(unit) for unit in units}
        if any(state["ActiveState"] not in ("active", "inactive") for state in initial.values()):
            raise ValueError("Unknown writer state.")
        active = [unit for unit in units if initial[unit]["ActiveState"] == "active"]
        references = manager.retain_exit_status(active) if native and active else nullcontext()
        with references:
            publish("draining", active)
            for unit in active:
                manager.stop(unit)
            if any(not _drained(manager, unit, initial[unit]["ControlGroup"]) for unit in units):
                raise ValueError("A writer or its descendants have not drained.")
            for unit in active:
                state = manager.state(unit)
                if (state["Result"], state["ExecMainCode"], state["ExecMainStatus"]) != ("success", "1", "0"):
                    raise ValueError("Writer did not acknowledge a graceful process exit.")
        backup_id, cut_id = str(uuid4()), str(uuid4())
        deadline = (datetime.now(timezone.utc) + timedelta(seconds=75)).isoformat()
        publish("held", active, backup_id, cut_id, deadline)
        manager.start(worker, wait=True)
        _verify_generation(profile, backup_id, cut_id)
        resume(active)
        return backup_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "capture", "recover"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = run_controller(args.config, args.action)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError):
        print("Managed controller refused the operation. Inspect the protected gate and unit state.")
        return 1
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
