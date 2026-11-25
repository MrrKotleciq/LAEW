"""Bind a supervised worker capture to an operator-reviewed release pair."""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import sysconfig

from .archive import _digest, _json, _publish, _stage, _uuid
from .capture import package_python_sha256
from .inventory import _inspect, _overlap, backup_target_from_profile
from .restore import _private


def _require(condition):
    if not condition:
        raise ValueError("Backup worker release evidence unavailable or invalid.")


def validate_worker_runtime():
    """Reject an editable package or a non-isolated writer invocation."""
    prefix = Path(sys.prefix)
    package = Path(__file__).resolve().parents[1]
    site = Path(sysconfig.get_path("purelib")).resolve()
    _require(sys.flags.isolated and prefix != Path(sys.base_prefix)
             and site.is_relative_to(prefix.resolve()) and package == site / "laew")
    _require(_inspect(prefix) == prefix and _inspect(Path(sys.executable)) == Path(sys.executable))
    _require(not any(site.glob("__editable__*")))


def _read_private(path):
    from laew.operator_cli import _bounded_file
    return _bounded_file(path, 65536, private=True)


def validate_worker_media(profile_path):
    """Require an owner-private profile and archive root for a worker apply."""
    from laew.operator_cli import _unique_object
    profile = json.loads(_read_private(Path(profile_path)), object_pairs_hook=_unique_object)
    _private(backup_target_from_profile(profile).destination)


class ReleaseProof:
    """A private operator attestation plus checks of the actual inputs."""

    def __init__(self, path, profile_path):
        from laew.operator_cli import _unique_object

        self.path = Path(path)
        self.profile = Path(profile_path)
        self.raw = _read_private(self.path)
        self.review = json.loads(self.raw, object_pairs_hook=_unique_object)
        keys = {"schema_version", "profile_id", "host_id", "profile_sha256", "manifest_sha256",
                "core_release", "core_package_root", "core_package_python_sha256",
                "worker_package_python_sha256"}
        _require(type(self.review) is dict and self.review.keys() == keys
                 and type(self.review["schema_version"]) is int and self.review["schema_version"] == 1)
        _require(all(_digest(self.review[key]) for key in keys if key.endswith("_sha256")))
        release = self.review["core_release"]
        _require(type(release) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,79}", release))
        core = self.review["core_package_root"]
        _require(type(core) is str and Path(core).is_absolute() and ".." not in Path(core).parts)
        self.core_root = _inspect(Path(core))
        _require(not _overlap(self.core_root, Path(__file__).resolve().parents[1]))

    def __call__(self, inventory, observed):
        review = self.review
        _private(inventory.destination)
        _require(self.raw == _read_private(self.path))
        _require(hashlib.sha256(_read_private(self.profile)).hexdigest() == review["profile_sha256"])
        _require((review["profile_id"], review["host_id"]) == (inventory.profile_id, inventory.host_id))
        _require(not any(_overlap(self.path.parent, root) for root in
                         (inventory.destination, *(source.path for source in inventory.sources))))
        _require(observed["manifest_sha256"] == review["manifest_sha256"]
                 and observed["package_python_sha256"] == review["worker_package_python_sha256"])
        _require(package_python_sha256(self.core_root) == review["core_package_python_sha256"])

    def record(self, receipt):
        """Record release evidence alongside the private attestation, outside the archive."""
        _require(self.raw == _read_private(self.path))
        review = self.review
        path = self.path.parent / ("backup-release-" + _uuid(receipt["backup_id"]) + ".json")
        data = {key: review[key] for key in ("core_release", "core_package_python_sha256", "worker_package_python_sha256",
                                            "profile_sha256", "manifest_sha256")}
        data.update(schema_version=1, backup_id=receipt["backup_id"], archive_sha256=receipt["archive_sha256"],
                    release_proof_sha256=hashlib.sha256(self.raw).hexdigest())
        with _stage(self.path.parent) as (stage, stream):
            stream.write(_json(data))
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            _publish(stage, path)
