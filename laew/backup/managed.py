"""Controller-owned Debian writer gate and single-use capture proof."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
from uuid import UUID

from .capture import WriterAcknowledgement
from .inventory import _inspect
from .policy import control_path, profile_digest

_UNIT = re.compile(r"[a-z0-9][a-z0-9_.-]{0,63}\.service\Z")
_FIELDS = {"schema_version", "phase", "boot_id", "units", "originally_active", "profile_sha256",
           "fence_identity", "backup_id", "cut_id", "valid_until"}


def boot_id():
    if os.name != "posix":
        raise ValueError("Managed capture is currently qualified for Debian fixtures.")
    return str(UUID(Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()))


def protected_path(path):
    """Only the system controller may mutate the gate or replace its ancestors."""
    path = Path(path)
    if not path.is_absolute() or _inspect(path) != path:
        raise ValueError("Invalid managed gate path.")
    for entry in (path, *path.parents):
        info = entry.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("Managed gate is not controller protected.")
    return path


def read_gate(path, *, require_boot=True):
    from laew.operator_cli import _bounded_file, _unique_object

    path = protected_path(path)
    raw = _bounded_file(path, 65536)
    data = json.loads(raw, object_pairs_hook=_unique_object)
    units = data.get("units") if type(data) is dict else None
    active = data.get("originally_active") if type(data) is dict else None
    if (type(data) is not dict or set(data) != _FIELDS or type(data["schema_version"]) is not int
            or data["schema_version"] != 1 or data["phase"] not in ("open", "draining", "held", "resuming")
            or type(units) is not list or not 0 < len(units) <= 16
            or any(type(unit) is not str or not _UNIT.fullmatch(unit) for unit in units)
            or units != sorted(set(units)) or type(active) is not list or active != sorted(set(active))
            or not set(active) <= set(units) or (require_boot and data["boot_id"] != boot_id())):
        raise ValueError("Managed gate unavailable or stale.")
    return data, hashlib.sha256(raw).digest()


def writer_gate_open(path, unit):
    state, _ = read_gate(path)
    allowed = state["units"] if state["phase"] == "open" else state["originally_active"]
    if state["phase"] not in ("open", "resuming") or unit not in allowed:
        raise ValueError("Managed writer start is inhibited.")


def fence_identity(fence):
    path = Path(fence)
    info = _inspect(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("Invalid managed installation fence.")
    return [str(path), info.st_dev, info.st_ino]


class ManagedCut:
    """Use the durable gate as authority, independently of the worker process."""

    def __init__(self, gate, profile, inventory, release):
        self.gate = Path(gate)
        self.profile = Path(profile)
        self.identity = fence_identity(inventory.fence)
        self.release = release
        state, self.digest = read_gate(self.gate)
        for key in ("backup_id", "cut_id"):
            if str(UUID(state[key])) != state[key]:
                raise ValueError("Invalid managed cut identity.")
        self.deadline = datetime.fromisoformat(state["valid_until"])
        if self.deadline.utcoffset() != timedelta(0):
            raise ValueError("Managed cut deadline must be UTC.")
        remaining = (self.deadline - datetime.now(timezone.utc)).total_seconds()
        if not 0 < remaining <= 300:
            raise ValueError("Invalid managed cut lifetime.")
        self.monotonic_deadline = time.monotonic() + remaining
        self.check(inventory.fence)
        units = frozenset(unit.removesuffix(".service").replace(".", "-") for unit in state["units"])
        if len(units) != len(state["units"]) or any(len(unit) > 63 for unit in units):
            raise ValueError("Ambiguous cut roster.")
        self.ack = WriterAcknowledgement(inventory.profile_id, inventory.host_id, state["backup_id"],
                                         state["cut_id"], units, units, True, True, self.deadline)
        cut_log = control_path(profile) / "operations" / ("used-" + state["cut_id"])
        with cut_log.open("xb") as stream:
            stream.write(self.digest.hex().encode("ascii"))
            stream.flush()
            os.fsync(stream.fileno())
        from .archive import _sync_dir
        _sync_dir(cut_log.parent)

    def check(self, fence):
        state, digest = read_gate(self.gate)
        if (digest != self.digest or state["phase"] != "held" or state["profile_sha256"] != profile_digest(self.profile)
                or state["fence_identity"] != self.identity or fence_identity(fence) != self.identity
                or time.monotonic() >= self.monotonic_deadline or datetime.now(timezone.utc) >= self.deadline):
            raise ValueError("Managed writer cut is no longer valid.")

    def __call__(self, inventory, observed):
        self.check(inventory.fence)
        self.release(inventory, observed)

    def record(self, receipt):
        self.release.record(receipt)
