"""Explicit single-host source inventory. This module does not capture data.

The caller supplies an already loaded manifest and explicit overrides from the
launch environment. Root metadata is inspected, never file contents. This is
not a tree scan, a writer fence, ACL verification, or authorization to capture.
In particular it does not establish that bind mounts or aliases below a root
are absent. Capture must fail closed until those boundaries are proven under
the fence on a supported filesystem.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import re
import stat
import yaml
from fnmatch import fnmatchcase

from laew.backup.fence import FENCE_FILENAME
from laew.console.session_store import session_storage_from_manifest
from laew.storage_paths import knowledge_storage_path, memory_collection_name, memory_storage_path
from laew.rag.config import resolve_project_root

_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
# Capture code must apply these independently of RAG indexing exclusions.
DEFAULT_EXCLUSIONS = (
    ".env", ".env.*", "*.log", "*.tmp", "*.lock", "*.pyc",
    "__pycache__", ".git", ".obsidian/workspace*", ".obsidian/cache",
    ".obsidian/plugins", "credentials*", "*token*", "*secret*",
    "*.key", "*.pem", "*.p12", "*.pfx", "models", "node_modules",
)


class InventoryError(ValueError):
    """An unsupported or unsafe profile or source boundary."""


@dataclass(frozen=True)
class Source:
    logical_id: str
    path: Path
    kind: str


@dataclass(frozen=True)
class Inventory:
    profile_id: str
    host_id: str
    destination: Path
    fence: Path
    sources: tuple[Source, ...]
    exclusions: tuple[str, ...] = DEFAULT_EXCLUSIONS
    manifest_path: Path | None = None
    manifest_content_digest: str | None = None
    memory_namespace_sha256: str | None = None


def manifest_content_digest(manifest):
    return hashlib.sha256(yaml.safe_dump(manifest, sort_keys=True).encode()).hexdigest()


def memory_namespace_sha256(storage_override):
    """Fingerprint the actual collection identity without serializing a private path."""
    return hashlib.sha256(memory_collection_name(storage_override).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class BackupTarget:
    profile_id: str
    host_id: str
    destination: Path


def is_excluded(relative_path):
    """Apply the conservative default policy to an archive-relative path."""
    path = Path(relative_path)
    if path.is_absolute() or not path.parts or any(part in (".", "..") for part in path.parts):
        raise InventoryError("invalid relative path")
    parts = tuple(part.casefold() for part in path.parts)
    for pattern in DEFAULT_EXCLUSIONS:
        pattern = pattern.casefold()
        if "/" in pattern:
            if any(fnmatchcase("/".join(parts[:end]), pattern) for end in range(1, len(parts) + 1)):
                return True
        elif any(fnmatchcase(part, pattern) for part in parts):
            return True
    return False


def _identifier(value):
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise InventoryError("invalid logical identifier")
    return value


def _path(value):
    if not isinstance(value, (str, Path)) or not str(value):
        raise InventoryError("path must be explicit")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or path.drive.startswith("\\\\"):
        raise InventoryError("path must be absolute and normalized")
    return path


def _inspect(path):
    """Reject symlinks, junctions, missing components and nested mounts."""
    previous_device = None
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
            if (stat.S_ISLNK(info.st_mode) or
                    getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
                raise InventoryError("links and junctions are unsupported")
            if previous_device is not None and info.st_dev != previous_device:
                raise InventoryError("cross-device paths are unsupported")
            if component != Path(component.anchor) and os.path.ismount(component):
                raise InventoryError("nested mounts are unsupported")
            previous_device = info.st_dev
        except OSError as exc:
            raise InventoryError("path metadata unavailable") from exc
    return path.resolve(strict=True)


def _overlap(a, b):
    return a == b or a in b.parents or b in a.parents


def _present(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise InventoryError("store metadata unavailable") from exc
    return True


def _profile_identifiers(profile):
    allowed = {"schema_version", "profile_id", "host_id", "manifest_path",
               "launch_cwd", "workspace_root", "vault", "destination", "fence", "config_files",
               "memory_enabled", "knowledge_enabled", "memory_storage", "knowledge_storage"}
    if (type(profile) is not dict or set(profile) != allowed or
            type(profile["schema_version"]) is not int or profile["schema_version"] != 1):
        raise InventoryError("unsupported profile")
    for key in ("memory_enabled", "knowledge_enabled"):
        if type(profile[key]) is not bool:
            raise InventoryError("store enablement must be explicit")
    configs = profile["config_files"]
    if type(configs) is not dict or len(configs) > 64:
        raise InventoryError("configuration files must be explicit and bounded")
    return _identifier(profile["profile_id"]), _identifier(profile["host_id"])


def _declared_path(raw):
    path = _path(raw)
    existing = path
    while not _present(existing):
        if existing == existing.parent:
            break  # A source volume can be absent after a disaster.
        existing = existing.parent
    if _present(existing):
        return _inspect(existing) / path.relative_to(existing)
    return path


def backup_target_from_profile(profile):
    """Resolve a read-only archive target without requiring original stores."""
    profile_id, host_id = _profile_identifiers(profile)
    destination = _inspect(_path(profile["destination"]))
    if not destination.is_dir():
        raise InventoryError("invalid backup destination")
    manifest = _declared_path(profile["manifest_path"])
    base = manifest.parent.parent if manifest.parent.name.casefold() == "manifests" else manifest.parent
    fence = _declared_path(profile["fence"])
    if fence.name != FENCE_FILENAME:
        raise InventoryError("invalid operator fence path")
    protected = [base, fence]
    protected.extend(_declared_path(profile[key]) for key in ("launch_cwd", "workspace_root", "vault"))
    for key in ("memory_storage", "knowledge_storage"):
        if profile[key] is not None:
            if not profile[key.replace("storage", "enabled")]:
                raise InventoryError("disabled store has an override")
            protected.append(_declared_path(profile[key]))
    for key, raw in profile["config_files"].items():
        _identifier(key)
        protected.append(_declared_path(raw))
    if any(_overlap(destination, path) for path in protected):
        raise InventoryError("operator paths overlap a workspace or installation")
    return BackupTarget(profile_id, host_id, destination)


def build_inventory(profile, manifest):
    """Validate an explicit v1 profile and return its authoritative roots.

    Profile keys: schema_version=1, profile_id, host_id, manifest_path,
    launch_cwd, workspace_root, vault, destination, fence, config_files (ID -> absolute file),
    memory_enabled, knowledge_enabled, memory_storage and knowledge_storage.
    Overrides must be explicitly null when absent. All paths must exist;
    no directories are created.
    The two booleans describe enabled application owners, not index settings.
    """
    pid, host = _profile_identifiers(profile)
    manifest_path, cwd = _path(profile.get("manifest_path")), _path(profile.get("launch_cwd"))
    workspace = _inspect(_path(profile.get("workspace_root")))
    if not _inspect(manifest_path).is_file() or not _inspect(cwd).is_dir() or not workspace.is_dir():
        raise InventoryError("invalid launch paths")
    storage = session_storage_from_manifest(manifest).expanduser()
    if ".." in storage.parts:
        raise InventoryError("session path must be normalized")
    base = manifest_path.parent.parent if manifest_path.parent.name.casefold() == "manifests" else manifest_path.parent
    named = storage if storage.is_absolute() else cwd / storage
    conversations = storage if storage.is_absolute() else base / storage
    raw = [Source("sessions_named", named, "directory"),
           Source("conversations", conversations, "directory"),
           Source("vault", _path(profile.get("vault")), "directory")]
    for enabled, key, logical_id, resolver in (
        (profile["memory_enabled"], "memory_storage", "memory_db", memory_storage_path),
        (profile["knowledge_enabled"], "knowledge_storage", "curation_db", knowledge_storage_path),
    ):
        override = profile.get(key)
        if override is not None:
            override = _path(override)
        if not enabled and override is not None:
            raise InventoryError("disabled store has an override")
        path = resolver(conversations, override)
        if enabled or _present(path):
            raw.append(Source(logical_id, path, "sqlite"))
    configs = profile.get("config_files")
    for key, value in configs.items():
        config_path = _path(value)
        if is_excluded(config_path.name):
            raise InventoryError("excluded configuration file")
        raw.append(Source("config_" + _identifier(key), config_path, "file"))
    destination, fence = _inspect(_path(profile.get("destination"))), _inspect(_path(profile.get("fence")))
    if not destination.is_dir() or fence.name != FENCE_FILENAME or not fence.is_file():
        raise InventoryError("invalid operator paths")
    project = resolve_project_root(manifest, base_dir=base)
    if any(_overlap(root, operator_path) for root in (workspace, cwd, project, base)
           for operator_path in (destination, fence)):
        raise InventoryError("operator paths overlap a workspace or installation")
    sources = []
    for source in raw:
        path = _inspect(source.path)
        if (source.kind == "directory" and not path.is_dir()) or (source.kind != "directory" and not path.is_file()):
            raise InventoryError("source type mismatch")
        if source.kind != "directory" and path.stat().st_nlink > 1:
            raise InventoryError("hard-linked source is unsupported")
        if _overlap(path, destination) or _overlap(path, fence):
            raise InventoryError("operator and source paths overlap")
        for prior in sources:
            if _overlap(path, prior.path) or (path.is_file() and prior.path.is_file() and os.path.samefile(path, prior.path)):
                # Legacy and current sessions may intentionally share exactly one root.
                if not (path == prior.path and {source.logical_id, prior.logical_id} == {"sessions_named", "conversations"}):
                    raise InventoryError("source paths overlap")
        sources.append(Source(source.logical_id, path, source.kind))
    if _overlap(destination, fence):
        raise InventoryError("operator paths overlap")
    if any(_overlap(manifest_path, source.path) for source in sources):
        raise InventoryError("manifest overlaps a capture source")
    namespace = (memory_namespace_sha256(profile["memory_storage"])
                 if any(source.logical_id == "memory_db" for source in sources) else None)
    return Inventory(pid, host, destination, fence, tuple(sources), manifest_path=manifest_path,
                     manifest_content_digest=manifest_content_digest(manifest), memory_namespace_sha256=namespace)
