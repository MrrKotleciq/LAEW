"""Offline single-host capture of an explicitly inventoried installation."""

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
import yaml

from laew.console.session_store import SessionStore, validate_payload, validate_session_name
from laew.console.state import SessionState
from laew.project_config import validate_language, validate_rag_source_allowlist
from .archive import ArchiveLimits, seal_archive, validate_member_name
from .fence import FENCE_FILENAME, host_fence
from .inventory import DEFAULT_EXCLUSIONS, is_excluded, manifest_content_digest


class CaptureError(ValueError):
    """The capture cannot establish a supported, consistent cut."""


@dataclass(frozen=True)
class WriterAcknowledgement:
    """Owner attestation for this cut, including external editors and workers."""
    profile_id: str
    host_id: str
    backup_id: str
    cut_id: str
    roster: frozenset[str]
    stopped: frozenset[str]
    inventory_complete: bool
    restart_inhibited: bool
    valid_until: datetime


def _require(condition, message):
    if not condition:
        raise CaptureError(message)


def _acknowledged(inventory, backup_id, cut_id, proof):
    _require(isinstance(proof, WriterAcknowledgement) and
             (proof.profile_id, proof.host_id, proof.backup_id, proof.cut_id) ==
             (inventory.profile_id, inventory.host_id, backup_id, cut_id)
             and proof.inventory_complete is True and proof.restart_inhibited is True
             and type(proof.roster) is frozenset and type(proof.stopped) is frozenset
             and 0 < len(proof.roster) <= 256 and proof.stopped == proof.roster
             and all(isinstance(owner, str) and owner != "unknown" and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", owner)
                     for owner in proof.roster), "Writer ownership or quiescence is unconfirmed.")
    _require(type(proof.valid_until) is datetime and proof.valid_until.utcoffset() == timedelta(0),
             "Writer acknowledgement deadline must be UTC.")
    remaining = (proof.valid_until - datetime.now(timezone.utc)).total_seconds()
    _require(remaining > 0, "Writer acknowledgement expired.")
    return time.monotonic() + remaining


def _mounts():
    # stat/ismount cannot distinguish a same-device Linux bind mount.
    if not sys.platform.startswith("linux"):
        return frozenset()
    with open("/proc/self/mountinfo", "rb") as stream:
        data = stream.read((8 << 20) + 1)
    _require(len(data) <= 8 << 20, "Mount inventory exceeds limit.")
    mounts = set()
    for line in data.splitlines():
        fields = line.split(b" ")
        _require(len(fields) >= 10 and b"-" in fields, "Unsupported mount inventory.")
        raw = re.sub(rb"\\([0-7]{3})", lambda match: bytes([int(match[1], 8)]), fields[4])
        mounts.add(Path(os.fsdecode(raw)))
    _require(Path("/") in mounts, "Incomplete mount inventory.")
    return mounts


def _stat(path, device=None, mounts=()):
    info = path.lstat()
    _require(not stat.S_ISLNK(info.st_mode) and not
             getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT and
             (stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1)),
             "Source contains an unsupported filesystem entry.")
    _require(device is None or (info.st_dev == device and path not in mounts and not os.path.ismount(path)),
             "Source crosses a mount boundary.")
    return info


def _root(path, mounts):
    _require(path.is_absolute() and ".." not in path.parts, "Unresolved source root.")
    device = None
    for part in (*reversed(path.parents), path):
        info = _stat(part, device, mounts)
        device = info.st_dev
    return info


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


_SESSIONS = {"sessions_named", "conversations"}
_DBS = {"memory_db": "memory.db", "curation_db": "curation.db"}
_CONVERSATION = re.compile(r"conversation-([a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})")


def _sources(inventory):
    _require(inventory.fence.name == FENCE_FILENAME and inventory.exclusions == DEFAULT_EXCLUSIONS,
             "Unsupported installation fence or exclusion policy.")
    sources = {}
    occupied = [inventory.destination, inventory.fence]
    _require(inventory.destination != inventory.fence and inventory.destination not in inventory.fence.parents
             and inventory.fence not in inventory.destination.parents, "Operator roots overlap.")
    for source in inventory.sources:
        key, path = source.logical_id, source.path
        _require(key not in sources and (key in _SESSIONS | {"vault"} and source.kind == "directory"
                 or key in _DBS and source.kind == "sqlite" or key.startswith("config_") and source.kind == "file"),
                 "Unsupported or duplicate source.")
        _require(not any(path == other or path in other.parents or other in path.parents for other in occupied),
                 "Capture and operator roots overlap.")
        for prior in sources.values():
            if path == prior.path and {prior.logical_id, key} == _SESSIONS:
                continue
            _require(path != prior.path and path not in prior.path.parents and prior.path not in path.parents,
                     "Capture sources overlap.")
        sources[key] = source
    _require(_SESSIONS | {"vault"} <= sources.keys(), "Required source root missing.")
    if sources["sessions_named"].path == sources["conversations"].path:
        del sources["sessions_named"]
    return sources


def _snapshot(sources, limits):
    tree, files = {}, {}
    directories = []
    total = 0
    mounts = _mounts()
    for key, source in sources.items():
        root = source.path
        info = _root(root, mounts)
        _require(stat.S_ISDIR(info.st_mode) == (source.kind == "directory"), "Source type changed.")
        tree[root] = _stamp(info)
        if source.kind == "sqlite":
            for suffix in ("-wal", "-shm", "-journal"):
                side = root.with_name(root.name + suffix)
                if os.path.lexists(side):
                    sideinfo = _stat(side, info.st_dev, mounts)
                    _require(stat.S_ISREG(sideinfo.st_mode) and suffix != "-journal", "Unsupported SQLite journal.")
                    # SQLite readers may update shared-memory lock metadata.
                    tree[side] = _stamp(sideinfo)[:4] if suffix == "-shm" else _stamp(sideinfo)
            _require(root.with_name(root.name + "-wal") not in tree or root.with_name(root.name + "-shm") in tree,
                     "WAL requires an existing shared-memory index.")
            files[key + "/" + _DBS[key]] = root
        elif source.kind == "file":
            _require(root.name in {"settings.json", ".laew-project.json"} and not is_excluded(root.name),
                     "Configuration file has no approved declarative schema.")
            files[validate_member_name(key + "/" + root.name)] = root
        else:
            directories.append(key)
            pending = [root]
            while pending:
                parent = pending.pop()
                for entry in parent.iterdir():
                    child = _stat(entry, info.st_dev, mounts)
                    tree[entry] = _stamp(child)
                    _require(len(tree) <= 4 * limits.max_members + 128, "Source inventory limit exceeded.")
                    rel = entry.relative_to(root).as_posix()
                    if is_excluded(rel) or any(part.casefold() == ".obsidian" for part in rel.split("/")):
                        _require(key not in _SESSIONS or entry.suffix.lower() != ".json",
                                 "Session classification requires operator review.")
                        continue
                    if key in _SESSIONS and rel == ".locks" and stat.S_ISDIR(child.st_mode):
                        continue
                    name = validate_member_name(key + "/" + rel)
                    if stat.S_ISDIR(child.st_mode):
                        _require(key == "vault", "Unsupported nested session directory.")
                        directories.append(name)
                        pending.append(entry)
                    else:
                        _require(key == "vault" or entry.suffix == ".json", "Unknown session store member.")
                        files[name] = entry
    _require(len(files) + len(directories) <= limits.max_members, "Too many capture members.")
    for path in files.values():
        size = tree[path][3]
        _require(size <= limits.max_member_bytes, "Source member exceeds budget.")
        total += size
    _require(total <= limits.max_total_bytes, "Source tree exceeds budget.")
    return tree, files, sorted(directories)


def _provenance(inventory, mounts):
    manifest = inventory.manifest_path
    _require(manifest is not None, "Missing authored manifest.")
    info = _root(manifest, mounts)
    _require(stat.S_ISREG(info.st_mode) and info.st_size <= 1 << 20, "Invalid authored manifest.")
    with manifest.open("rb") as stream:
        raw = stream.read((1 << 20) + 1)
        _require(len(raw) == info.st_size and _stamp(os.fstat(stream.fileno()))[:5] == _stamp(info)[:5]
                 and _stamp(manifest.lstat()) == _stamp(info), "Authored manifest changed.")
    _require(manifest_content_digest(yaml.safe_load(raw)) == inventory.manifest_content_digest,
             "Authored manifest differs from inventoried configuration.")
    # Frame each relative UTF-8 module name and its SHA-256 digest, so a
    # dirty checkout and an installed Python package both have content identity.
    root = Path(__file__).resolve().parents[1]
    package = hashlib.sha256()
    total = 0
    count = 0
    def fail(error):
        raise error
    for directory, children, files in os.walk(root, onerror=fail):
        children[:] = sorted(name for name in children if name != "__pycache__")
        for child in children:
            _stat(Path(directory) / child, root.stat().st_dev, mounts)
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            module = Path(directory) / name
            size = _stat(module, root.stat().st_dev, mounts).st_size
            count += 1
            total += size
            _require(count <= 4096 and size <= 8 << 20 and total <= 64 << 20, "Package evidence exceeds budget.")
            with module.open("rb") as stream:
                data = stream.read(size + 1)
            _require(len(data) == size, "Package source changed.")
            path = module.relative_to(root).as_posix().encode()
            package.update(len(path).to_bytes(4, "big") + path + hashlib.sha256(data).digest())
    _require(count > 0, "Missing package source evidence.")
    return dict(manifest_sha256=hashlib.sha256(raw).hexdigest(), package_python_sha256=package.hexdigest())


def _check_space(destination, tree, files, directories, limits):
    # WAL pages may grow the standalone database beyond the main file size.
    payload = sum(tree[path][3] for path in files.values())
    payload += sum(stamp[3] for path, stamp in tree.items() if path.name.endswith("-wal"))
    payload = min(payload, limits.max_total_bytes)
    # Reserve two payloads for staging and stored ZIP, plus metadata and
    # per-entry filesystem allocation. Verification streams the staged ZIP.
    required = 2 * payload + limits.max_manifest_bytes + 8192 * (len(files) + len(directories) + 4)
    _require(shutil.disk_usage(destination).free >= required, "Insufficient capture staging space.")


def _json(raw):
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            _require(key not in obj, "Ambiguous structured record.")
            obj[key] = value
        return obj

    def invalid(value):
        raise CaptureError("Invalid structured number.")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def _validate_session(path):
    doc = _json(path.read_bytes())
    match = _CONVERSATION.fullmatch(path.stem)
    if match:
        SessionStore._validate_conversation_record(doc, SessionStore._conversation_id(match.group(1)))
    else:
        validate_session_name(path.stem)
        envelope = validate_payload(doc)
        if envelope["kind"] == "console":
            SessionState.from_payload(doc)


def _validate_config(path):
    doc = _json(path.read_bytes())
    keys = {"documentation_language"}
    if path.name == ".laew-project.json":
        keys.add("rag_source_allowlist")
    _require(type(doc) is dict and not doc.keys() - keys, "Unapproved configuration field.")
    if "documentation_language" in doc:
        validate_language(doc["documentation_language"])
    if "rag_source_allowlist" in doc:
        validate_rag_source_allowlist(doc["rag_source_allowlist"])


def _copy(source, target, stamp):
    with source.open("rb") as reader, target.open("xb") as writer:
        # Windows path stat and fd stat can report different ctime semantics.
        # Compare ctime on the path, and identity, mode, size and mtime on both.
        _require(_stamp(source.lstat()) == stamp and _stamp(os.fstat(reader.fileno()))[:5] == stamp[:5],
                 "Source changed before staging.")
        remaining = stamp[3]
        while remaining:
            data = reader.read(min(1 << 20, remaining))
            _require(data, "Source was truncated during staging.")
            writer.write(data)
            remaining -= len(data)
        _require(not reader.read(1) and _stamp(os.fstat(reader.fileno()))[:5] == stamp[:5]
                 and _stamp(source.lstat()) == stamp, "Source changed during staging.")
    os.utime(target, ns=(stamp[4], stamp[4]))


def _validate_database(db, key):
    from laew.knowledge.store import SCHEMA as knowledge_schema
    from laew.memory.store import SCHEMA as memory_schema

    expected_version = 2 if key == "memory_db" else 0
    _require(db.execute("PRAGMA user_version").fetchone() == (expected_version,), "Unsupported SQLite schema version.")
    with closing(sqlite3.connect(":memory:")) as expected:
        expected.executescript(memory_schema if key == "memory_db" else knowledge_schema)
        query = "SELECT type,name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
        _require(db.execute(query).fetchall() == expected.execute(query).fetchall(), "Unsupported SQLite schema.")
    _require(db.execute("PRAGMA integrity_check(1)").fetchone() == ("ok",) and
             db.execute("PRAGMA foreign_key_check").fetchone() is None, "SQLite consistency check failed.")


def _backup_database(source, target, key, maximum, timeout):
    deadline = time.monotonic() + timeout
    # With a confirmed quiescent cut and no WAL, immutable mode also prevents
    # creation of empty WAL/SHM files in a previously clean WAL-mode directory.
    uri = source.as_uri() + "?mode=ro"
    if not source.with_name(source.name + "-wal").exists():
        uri += "&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=.05)) as src, closing(sqlite3.connect(target)) as out:
        src.execute("PRAGMA query_only=ON")
        page = src.execute("PRAGMA page_size").fetchone()[0]
        _require(page * src.execute("PRAGMA page_count").fetchone()[0] <= maximum, "SQLite snapshot exceeds budget.")

        def progress(status, remaining, total):
            _require(time.monotonic() < deadline and total * page <= maximum, "SQLite snapshot timeout or size limit.")

        src.backup(out, pages=64, progress=progress, sleep=.01)
        out.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        _require(out.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",), "Snapshot has external journal.")
        _validate_database(out, key)
    _require(target.stat().st_size <= maximum and
             not any(target.with_name(target.name + suffix).exists() for suffix in ("-wal", "-shm", "-journal")),
             "Incomplete standalone snapshot.")


def _curation(staged, vault, tree, timeout):
    database = staged.get("curation_db/curation.db")
    if database is None:
        return
    deadline = time.monotonic() + timeout
    namespace = {}
    for path, stamp in tree.items():
        if path != vault and path.is_relative_to(vault):
            rel = path.relative_to(vault).as_posix()
            namespace[rel.casefold()] = (rel, stat.S_ISDIR(stamp[2]))
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)) as db:
        db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        for status, version, raw in db.execute("SELECT status,version,payload FROM knowledge_proposals "
                                              "WHERE status IN ('approved','applied')"):
            _require(time.monotonic() < deadline, "Publication validation timed out.")
            row = _json(raw)
            _require(type(row) is dict, "Invalid publication record.")
            target, approved = row.get("target"), row.get("approved_version")
            _require(isinstance(target, str) and target.startswith("@knowledge/") and target.endswith(".md")
                     and type(approved) is int and 0 < approved < version, "Invalid approved revision.")
            name = validate_member_name("vault/" + target.removeprefix("@knowledge/"))
            parts = name.split("/")[1:]
            for i in range(1, len(parts) + 1):
                prefix = "/".join(parts[:i])
                existing = namespace.get(prefix.casefold())
                _require(existing is None or existing == (prefix, i < len(parts)),
                         "Ambiguous publication target path.")
            _require(not is_excluded(name.removeprefix("vault/")) and not any(
                part.casefold() == ".obsidian" for part in name.split("/")), "Excluded publication target.")
            base, proposed = row.get("base_content"), row.get("content")
            _require(isinstance(base, str) and isinstance(proposed, str) and proposed
                     and row.get("base_sha256") == (hashlib.sha256(base.encode()).hexdigest() if base else ""),
                     "Invalid publication digest.")
            path = staged.get(name)
            actual = None
            if path is not None:
                with path.open("rb") as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if status == "approved":
                _require(row.get("index_status") == "not_written" and
                         actual in {hashlib.sha256(proposed.encode()).hexdigest(),
                                    hashlib.sha256(base.encode()).hexdigest() if base else None},
                         "Ambiguous approved publication.")
            else:
                index = row.get("index_status")
                _require(index in {"pending", "indexed", "superseded"} and
                         (index == "superseded" or actual == hashlib.sha256(proposed.encode()).hexdigest()),
                         "Ambiguous applied publication.")


def capture_backup(inventory, *, backup_id, cut_id, writers, limits=ArchiveLimits(), fence_timeout=0.0,
                   sqlite_timeout=5.0):
    """Capture an explicitly quiesced, single-host source inventory."""
    acknowledgement_deadline = _acknowledged(inventory, backup_id, cut_id, writers)
    _require(math.isfinite(sqlite_timeout) and 0 < sqlite_timeout <= 300, "Invalid SQLite deadline.")
    sources = _sources(inventory)
    mounts = _mounts()
    _root(inventory.destination, mounts)
    _root(inventory.fence, mounts)
    with host_fence(inventory.fence.parent, mode="maintenance", timeout=fence_timeout):
        _require(time.monotonic() < acknowledgement_deadline and datetime.now(timezone.utc) < writers.valid_until,
                 "Writer acknowledgement expired.")
        tree, files, directories = _snapshot(sources, limits)
        _check_space(inventory.destination, tree, files, directories, limits)
        provenance = _provenance(inventory, mounts)
        with tempfile.TemporaryDirectory(prefix=".m18-capture-", dir=inventory.destination) as temporary:
            staged = {}
            total = 0
            for name, source in files.items():
                key = name.split("/", 1)[0]
                target = Path(temporary).joinpath(*name.split("/"))
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if key in _DBS:
                    _backup_database(source, target, key, min(limits.max_member_bytes, limits.max_total_bytes - total),
                                     sqlite_timeout)
                    os.utime(target, ns=(tree[source][4], tree[source][4]))
                else:
                    _require(tree[source][3] <= limits.max_total_bytes - total, "Capture staging exceeds budget.")
                    _copy(source, target, tree[source])
                    if key in _SESSIONS or key.startswith("config_"):
                        _require(target.stat().st_size <= 32 << 20, "Oversized structured source.")
                        if key in _SESSIONS:
                            _validate_session(target)
                        else:
                            _validate_config(target)
                staged[name] = target
                total += target.stat().st_size
            _curation(staged, sources["vault"].path, tree, sqlite_timeout)

            def unchanged():
                _require(_snapshot(sources, limits) == (tree, files, directories)
                         and _provenance(inventory, mounts) == provenance, "Source inventory changed during capture.")
                _require(time.monotonic() < acknowledgement_deadline and datetime.now(timezone.utc) < writers.valid_until,
                         "Writer acknowledgement expired.")

            unchanged()
            return seal_archive(inventory.destination, staged, backup_id=backup_id, cut_id=cut_id,
                                profile_id=inventory.profile_id, host_id=inventory.host_id, limits=limits,
                                before_publish=unchanged, capture=dict(provenance, directories=directories,
                                shared_session_root="sessions_named" not in sources))
