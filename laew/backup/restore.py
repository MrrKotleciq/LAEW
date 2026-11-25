"""Verify and publish an isolated, inactive logical recovery tree."""

import ctypes
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
from uuid import uuid4

from .archive import ArchiveLimits, copy_verified_member, validate_member_name, verify_archive
from .capture import _mounts, _root
from .inventory import _overlap, _path, backup_target_from_profile, is_excluded


class RestoreError(ValueError):
    """The requested isolated restore cannot establish its preconditions."""


def _require(condition, message):
    if not condition:
        raise RestoreError(message)


def _check_permissions(path, info):
    if os.name == "nt":
        from laew.security.windows_security import assert_private_owned_path, get_current_user_sid
        assert_private_owned_path(path, get_current_user_sid())
    else:
        _require(info.st_uid == os.geteuid() and not info.st_mode & 0o077, "Restore path is not private.")


def _private(directory):
    info = directory.lstat()
    _require(stat.S_ISDIR(info.st_mode), "A private directory is required.")
    _check_permissions(directory, info)
    return info


def _mkdir(path):
    # On Windows inherit the provisioned private parent DACL. Python's 0700
    # creates an independent DACL with additional synthetic trustees.
    path.mkdir(mode=0o777 if os.name == "nt" else 0o700)


@contextmanager
def _new_file(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        _check_permissions(path, path.lstat())
        yield stream
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def _staging(parent):
    holder = parent / (".m18-restore-" + uuid4().hex)
    _mkdir(holder)
    try:
        _private(holder)
        yield holder
    finally:
        shutil.rmtree(holder)


def _publish(stage, target):
    # Both supported primitives fail atomically when the destination exists.
    if os.name == "nt":
        function = ctypes.WinDLL("kernel32", use_last_error=True).MoveFileExW
        function.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
        function.restype = ctypes.c_int
        if not function(str(stage), str(target), 8):  # MOVEFILE_WRITE_THROUGH
            raise ctypes.WinError(ctypes.get_last_error())
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        function = getattr(libc, "renameat2", None)
        _require(function is not None, "Atomic no-replace publication is unavailable.")
        function.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        function.restype = ctypes.c_int
        if function(-100, os.fsencode(stage), -100, os.fsencode(target), 1):  # AT_FDCWD, RENAME_NOREPLACE
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
    else:
        raise RestoreError("Unsupported restore platform.")


def _sync_directory(path):
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _identity(profile, manifest):
    _require((manifest["host_id"], manifest["profile_id"]) == (profile["host_id"], profile["profile_id"]),
             "Archive does not match the requested profile and host.")


def verify_restore(profile, backup_id, *, limits=ArchiveLimits()):
    """Verify the complete archive against the explicit host/profile without extraction."""
    source = backup_target_from_profile(profile)
    _root(source.destination, _mounts())
    def inspect(container, manifest):
        _identity(profile, manifest)
        if "capture" in manifest:
            _expected(profile, manifest)
    return verify_archive(source.destination, backup_id, limits=limits, on_verified=inspect)


def _expected(profile, manifest):
    _require("capture" in manifest, "Recovery requires recorded directory and session identity.")
    directories = set(manifest["capture"]["directories"])
    for directory in directories:
        if "/" in directory:
            root, relative = directory.split("/", 1)
            _require(root == "vault" and _vault_member(relative), "Unexpected captured directory.")
    files = {}
    for row in manifest["members"]:
        name = row["name"]
        root, relative = name.split("/", 1)
        if root in {"conversations", "sessions_named"}:
            _require("/" not in relative and relative.endswith(".json"), "Unknown session member.")
        elif root in {"memory_db", "curation_db"}:
            expected = {"memory_db": "memory.db", "curation_db": "curation.db"}
            _require(relative == expected[root], "Unknown database member.")
        elif root.startswith("config_"):
            configured = profile["config_files"].get(root.removeprefix("config_"))
            _require(configured and Path(configured).name == relative
                     and relative in {"settings.json", ".laew-project.json"}, "Unknown configuration member.")
        else:
            _require(root == "vault" and _vault_member(relative), "Unknown logical source.")
        directories.add(name.rpartition("/")[0])
        files[name] = row
    namespace = manifest['capture'].get('memory_namespace_sha256')
    if namespace is not None:
        from laew.backup.inventory import memory_namespace_sha256
        _require(namespace == memory_namespace_sha256(profile['memory_storage']),
                 "Memory namespace does not match the recovery profile.")
    for enabled, name in (("memory_enabled", "memory_db/memory.db"), ("knowledge_enabled", "curation_db/curation.db")):
        _require(not profile[enabled] or name in files, "Missing required database.")
    for key, path in profile["config_files"].items():
        _require("config_" + key + "/" + Path(path).name in files, "Missing required configuration.")
    return directories, files


def _vault_member(relative):
    return not is_excluded(relative) and ".obsidian" not in relative.casefold().split("/")


def _audit(stage, directories, files, mounts):
    _root(stage, mounts)
    seen_dirs, seen_files = set(), set()
    def fail(error):
        raise error
    for base, children, entries in os.walk(stage, onerror=fail):
        for child in children:
            path = Path(base) / child
            name = path.relative_to(stage).as_posix()
            _require(name in directories and stat.S_ISDIR(_root(path, mounts).st_mode), "Unexpected restored directory.")
            _private(path)
            seen_dirs.add(name)
        for entry in entries:
            path = Path(base) / entry
            name = path.relative_to(stage).as_posix()
            row = files.get(name)
            info = _root(path, mounts)
            _require(row is not None and stat.S_ISREG(info.st_mode) and info.st_size == row["size"],
                     "Unexpected restored file.")
            _check_permissions(path, info)
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                remaining = row["size"]
                while remaining:
                    data = stream.read(min(1 << 20, remaining))
                    _require(data, "Truncated restored file.")
                    digest.update(data)
                    remaining -= len(data)
                _require(not stream.read(1) and digest.hexdigest() == row["sha256"], "Restored digest mismatch.")
            seen_files.add(name)
    _require(seen_dirs == directories and seen_files == files.keys(), "Incomplete restored tree.")


def restore_backup(profile, backup_id, *, target, validate_staged, limits=ArchiveLimits()):
    """Require an operator-private parent and read-only semantic/identity validator.

    Recover into a fresh name or an explicitly empty private target. A prior
    publication remains available on repeat calls. Never start a runtime here.
    """
    _require(callable(validate_staged), "Recovery requires staged identity validation.")
    source = backup_target_from_profile(profile)
    target = _path(target)
    validate_member_name("target/" + target.name)
    parent = target.parent
    # Reuse P04 profile admission for every declared installation/source boundary.
    backup_target_from_profile(dict(profile, destination=parent))
    _require(not _overlap(parent, source.destination), "Recovery parent overlaps backup storage.")
    mounts = _mounts()
    _root(source.destination, mounts)
    _root(parent, mounts)
    parent_identity = _private(parent)
    existing = None
    if os.path.lexists(target):
        _root(target, mounts)
        existing = _private(target)
        _require(not any(target.iterdir()), "Recovery target is not empty.")

    with _staging(parent) as holder:
        stage = holder / "recovery"
        _mkdir(stage)
        _private(stage)

        validation = {"status": "not_reported", "activation_blocked": None,
                      "blocked_missing_jobs": None, "missing_historical_references": None,
                      "memory_namespace": "not_applicable"}

        def extract(container, manifest):
            _identity(profile, manifest)
            directories, files = _expected(profile, manifest)
            size = sum(row["size"] for row in files.values()) + (len(files) + len(directories) + 4) * 8192
            _require(shutil.disk_usage(stage).free >= size, "Insufficient recovery space.")
            for name in sorted(directories):
                _mkdir(stage / name)
                _private(stage / name)
            for name, row in files.items():
                path = stage / name
                with _new_file(path) as out:
                    copy_verified_member(container, row, out)
                os.utime(path, ns=(row["mtime_ns"], row["mtime_ns"]))
            _audit(stage, directories, files, mounts)
            # The validator may create a separate disposable runtime for its drill.
            # Give it an independent object so it cannot change our expected hashes.
            reported = validate_staged(stage, json.loads(json.dumps(manifest)))
            has_memory = "memory_db/memory.db" in files
            validation['memory_namespace'] = (
                "matched" if has_memory and "memory_namespace_sha256" in manifest['capture'] else
                "unknown" if has_memory else "not_applicable")
            if reported is not None:
                _require(type(reported) is dict and reported.get('status') == 'validated',
                         "Invalid semantic validation result.")
                blocked = reported.get('blocked_missing_jobs')
                missing = reported.get('missing_historical_references')
                _require(type(blocked) is int and 0 <= blocked <= 1000000 and
                         type(missing) is int and 0 <= missing <= 1000000,
                         "Invalid semantic validation counts.")
                validation.update(status="reported", activation_blocked=bool(blocked),
                                  blocked_missing_jobs=blocked, missing_historical_references=missing)
            _audit(stage, directories, files, mounts)
            for name in sorted(directories, reverse=True):
                _sync_directory(stage / name)

        verified = verify_archive(source.destination, backup_id, limits=limits, on_verified=extract)
        receipt = {key: verified[key] for key in ("schema_version", "backup_id", "cut_id", "profile_id", "host_id",
                                                  "archive_sha256", "manifest_sha256", "member_count")}
        receipt.update(restored_at=datetime.now(timezone.utc).isoformat(), state="isolated",
                       recovery_validation=validation)
        with _new_file(stage / "restore.receipt.json") as out:
            out.write(json.dumps(receipt, sort_keys=True).encode())
        _sync_directory(stage)
        _root(parent, mounts)
        _require(os.path.samestat(parent_identity, _private(parent)), "Recovery parent changed.")
        if existing is not None:
            _root(target, mounts)
            _require(os.path.samestat(existing, _private(target)), "Recovery target changed.")
            target.rmdir()  # The OS refuses a nonempty directory even if a concurrent writer raced.
        try:
            _publish(stage, target)
        except BaseException:
            if existing is not None and not os.path.lexists(target):
                _mkdir(target)
            raise
        _sync_directory(parent)
    return receipt
