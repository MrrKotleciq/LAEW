"""Installation-local admission policy for backup operations."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

from .archive import _stage, _sync_dir
from .fence import FENCE_FILENAME, FenceBusyError, host_fence
from .inventory import _inspect, _overlap, backup_target_from_profile
from .restore import _private


def control_path(profile):
    profile = Path(profile)
    return profile.with_name(profile.name + ".control")


def read_private_json(path):
    from laew.operator_cli import _bounded_file, _unique_object

    return json.loads(_bounded_file(path, 65536, private=True), object_pairs_hook=_unique_object)


def atomic_json(path, data, *, mode=None):
    with _stage(path.parent) as (stage, stream):
        if mode is not None:
            os.fchmod(stream.fileno(), mode)
        stream.write(json.dumps(data, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
        stream.close()
        os.replace(stage, path)
        _sync_dir(path.parent)


def profile_digest(profile):
    from laew.operator_cli import _bounded_file

    return hashlib.sha256(_bounded_file(Path(profile), 65536)).hexdigest()


def load_policy(profile):
    root = control_path(profile)
    if not os.path.lexists(root):
        return None
    if _inspect(root) != root:
        raise ValueError("Invalid backup control path.")
    _private(root)
    document = read_private_json(root / "policy.json")
    if (type(document) is not dict or document.keys() != {"schema_version", "profile_sha256", "managed", "revision"}
            or type(document["schema_version"]) is not int or document["schema_version"] != 1
            or document["profile_sha256"] != profile_digest(profile) or type(document["managed"]) is not bool
            or str(UUID(document["revision"])) != document["revision"]):
        raise ValueError("Invalid backup control policy.")
    _private(root / "administration")
    _private(root / "operations")
    return root, document


def initialize_policy(profile, *, managed):
    from laew.operator_cli import _load_profile
    from .provenance import validate_worker_media

    profile = Path(profile)
    validate_worker_media(profile)
    root = control_path(profile)
    _private(root.parent)
    target = backup_target_from_profile(_load_profile(str(profile)))
    if _overlap(root, target.destination):
        raise ValueError("Backup control overlaps archive media.")
    root.mkdir(mode=0o777 if os.name == "nt" else 0o700)
    for name in ("administration", "operations"):
        directory = root / name
        directory.mkdir(mode=0o777 if os.name == "nt" else 0o700)
        _private(directory)
        (directory / FENCE_FILENAME).touch(mode=0o600, exist_ok=False)
    (root / "disabled").touch(mode=0o600, exist_ok=False)
    atomic_json(root / "policy.json", {"schema_version": 1, "profile_sha256": profile_digest(profile),
                                      "managed": managed, "revision": str(uuid4())})


def policy_revision(profile, policy=None):
    policy = load_policy(profile) if policy is None else policy
    digest = profile_digest(profile)
    if policy is not None:
        digest = hashlib.sha256((digest + policy[1]["revision"]).encode("ascii")).hexdigest()
    return digest


def policy_state(profile):
    policy = load_policy(profile)
    if policy is None:
        return "unconfigured"
    root, _ = policy
    if not os.path.lexists(root / "disabled"):
        return "enabled"
    try:
        with host_fence(root / "operations", mode="maintenance"):
            return "disabled"
    except FenceBusyError:
        return "disabling"


def set_enabled(profile, *, enabled, expected_revision=None):
    policy = load_policy(profile)
    if policy is None:
        raise ValueError("Backup policy has not been provisioned.")
    root, _ = policy
    with host_fence(root / "administration", mode="maintenance"):
        policy = load_policy(profile)
        if expected_revision is not None and expected_revision != policy_revision(profile, policy):
            raise ValueError("Backup policy revision changed.")
        marker = root / "disabled"
        changed = {**policy[1], "revision": str(uuid4())}
        if enabled:
            with host_fence(root / "operations", mode="maintenance"):
                atomic_json(root / "policy.json", changed)
                marker.unlink(missing_ok=True)
                _sync_dir(root)
        else:
            if not os.path.lexists(marker):
                marker.touch(mode=0o600, exist_ok=False)
                _sync_dir(root)
            atomic_json(root / "policy.json", changed)
        return policy_state(profile)


@contextmanager
def admission(profile, *, operation, managed=False):
    """Serialize configured operations and preserve the legacy supervised path."""
    policy = load_policy(profile)
    if policy is None:
        if operation != "capture" or managed:
            raise ValueError("Backup policy has not been provisioned.")
        yield
        return
    root, document = policy
    if operation == "capture" and document["managed"] != managed:
        raise ValueError("Capture mode does not match the installation policy.")
    if os.path.lexists(root / "disabled"):
        raise ValueError("Backups are disabled.")
    with host_fence(root / "operations", mode="maintenance"):
        if os.path.lexists(root / "disabled") or load_policy(profile) != policy:
            raise ValueError("Backup policy changed before admission.")
        yield
