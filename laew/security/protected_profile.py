"""Bind retained diagnostics and project subprocesses to a protected install."""

from __future__ import annotations

import json
import logging
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


_CONFIG_ENV = "LAEW_PROTECTED_PROFILE"
_LOG = logging.getLogger("laew.telemetry")
_LABEL = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")


class ProtectedProfileError(PermissionError):
    """A required protected boundary could not be established."""


@dataclass(frozen=True)
class ProjectSandbox:
    root: Path
    profile_name: str | None
    scratch: Path


@dataclass(frozen=True)
class ProtectedInstallation:
    manifest: Path
    telemetry_root: Path
    backup_roots: tuple[Path, ...]
    projects: tuple[ProjectSandbox, ...]
    executables: dict[str, Path]
    readonly_roots: tuple[Path, ...] = ()


_active: ProtectedInstallation | None = None


def _deny():
    return ProtectedProfileError("Protected installation could not be verified.")


def _path(value):
    if type(value) is not str or not value:
        raise _deny()
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts or path.drive.startswith("\\\\") or
            (os.name == "nt" and any(":" in part for part in path.parts[1:]))):
        raise _deny()
    for component in reversed((path, *path.parents)):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise _deny()
    return path.resolve(strict=True)


def _separate(left, right):
    return not (left.is_relative_to(right) or right.is_relative_to(left))


def _unique_pairs(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise _deny()
        values[key] = value
    return values


def _linux_private(path, identity):
    info = path.stat()
    if info.st_uid != identity or info.st_mode & 0o077:
        raise _deny()


def _linux_trusted(path, identity):
    info = path.stat()
    if info.st_uid not in {identity, 0} or info.st_mode & 0o022:
        raise _deny()


def _load():
    config = os.environ.get(_CONFIG_ENV)
    if not config:
        return None
    if os.name == "nt":
        from laew.security.windows_security import (
            assert_private_owned_path, assert_trusted_owned_path, get_current_user_sid, get_path_owner_sid,
        )
        identity = get_current_user_sid()
        private_path, trusted_path, owner_of = assert_private_owned_path, assert_trusted_owned_path, get_path_owner_sid
    elif sys.platform == "linux" and os.geteuid() != 0:
        identity = os.geteuid()
        private_path, trusted_path = _linux_private, _linux_trusted
        def owner_of(path):
            return path.stat().st_uid
    else:
        raise _deny()

    installation = Path(__file__).resolve().parents[2]
    profile = _path(config)
    if not profile.is_relative_to(installation) or not profile.is_file():
        raise _deny()
    trusted_path(installation, identity)
    for parent in profile.parents:
        if parent != installation and parent.is_relative_to(installation):
            trusted_path(parent, identity)
    private_path(profile, identity)
    with profile.open("rb") as stream:
        raw = stream.read(32769)
    if len(raw) > 32768:
        raise _deny()
    settings = json.loads(raw, object_pairs_hook=_unique_pairs)
    required = {"schema_version", "legacy_installation", "manifest", "telemetry_root", "backup_roots",
                "projects", "executables"}
    if os.name != "nt":
        required.add("readonly_roots")
    if (type(settings) is not dict or set(settings) != required or
            type(settings["schema_version"]) is not int or settings["schema_version"] != 1):
        raise _deny()
    legacy = _path(settings["legacy_installation"])
    if not _separate(legacy, installation) or owner_of(legacy) == identity:
        raise _deny()
    manifest = _path(settings["manifest"])
    if not manifest.is_relative_to(installation) or not manifest.is_file():
        raise _deny()
    private_path(manifest, identity)
    telemetry_root = _path(settings["telemetry_root"])
    if type(settings["backup_roots"]) is not list or len(settings["backup_roots"]) > 8:
        raise _deny()
    backup_roots = tuple(_path(value) for value in settings["backup_roots"])
    private_roots = (telemetry_root, *backup_roots)
    for root in private_roots:
        if not root.is_dir() or not _separate(root, legacy):
            raise _deny()
        private_path(root, identity)
        private_path(root.parent, identity)
    if type(settings["projects"]) is not list or not 1 <= len(settings["projects"]) <= 32:
        raise _deny()
    projects = []
    for entry in settings["projects"]:
        if type(entry) is not dict or set(entry) != {"root", "appcontainer", "scratch"}:
            raise _deny()
        root, scratch = _path(entry["root"]), _path(entry["scratch"])
        name = entry["appcontainer"]
        valid_name = type(name) is str and _LABEL.fullmatch(name) if os.name == "nt" else name is None
        if (not valid_name or not root.is_dir() or not scratch.is_dir() or
                any(not _separate(path, boundary) for path in (root, scratch)
                    for boundary in (installation, *private_roots)) or
                any((name is not None and name == other.profile_name) or not _separate(root, other.root) or
                    not _separate(scratch, other.scratch) or not _separate(root, other.scratch) or
                    not _separate(scratch, other.root) for other in projects)):
            raise _deny()
        projects.append(ProjectSandbox(root, name, scratch))
    configured_executables = settings["executables"]
    if type(configured_executables) is not dict or not 1 <= len(configured_executables) <= 32:
        raise _deny()
    readonly = ()
    if os.name != "nt":
        declared = settings["readonly_roots"]
        if type(declared) is not list or not 1 <= len(declared) <= 16:
            raise _deny()
        readonly = tuple(_path(path) for path in declared)
        forbidden = (profile, manifest, *private_roots, *(p.root for p in projects), *(p.scratch for p in projects))
        for root in readonly:
            if not root.is_dir() or any(not _separate(root, path) for path in forbidden):
                raise _deny()
            for parent in (root, *root.parents):
                trusted_path(parent, identity)
    executables = {}
    for label, value in configured_executables.items():
        if not _LABEL.fullmatch(label):
            raise _deny()
        path = _path(value)
        boundaries = readonly or (installation,)
        if not path.is_file() or not any(path.is_relative_to(root) for root in boundaries):
            raise _deny()
        for parent in path.parents:
            if parent.is_relative_to(installation):
                trusted_path(parent, identity)
        trusted_path(path, identity)
        executables[label] = path
    return ProtectedInstallation(manifest, telemetry_root, backup_roots, tuple(projects), executables, readonly)


def _telemetry_root(profile, manifest_path):
    from laew.manifest import load_manifest
    candidate = Path(manifest_path or profile.manifest)
    if not candidate.is_absolute():
        candidate = profile.manifest.parent.parent / candidate
    if _path(str(candidate)) != profile.manifest:
        raise _deny()
    config = load_manifest(profile.manifest).get("telemetry", {})
    if not config.get("enabled", False):
        return None
    if _path(config["root"]) != profile.telemetry_root:
        raise _deny()
    return profile.telemetry_root


def read_telemetry_root(manifest_path=None):
    """Resolve a private trace directory without starting any OS process."""
    profile = _load()
    return _telemetry_root(profile, manifest_path) if profile is not None else None


def _environment(project, executables):
    system = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    return {"SYSTEMROOT": str(system), "WINDIR": str(system), "LOCALAPPDATA": str(project.scratch),
            "TEMP": str(project.scratch), "TMP": str(project.scratch), "HOME": str(project.scratch),
            "PATH": os.pathsep.join(dict.fromkeys(str(path.parent) for path in executables.values())),
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C", "LC_ALL": "C"}


def _launch(profile, project, argv, cwd, timeout):
    if os.name == "nt":
        from laew.security.windows_appcontainer import run_appcontainer
        return run_appcontainer(argv, profile_name=project.profile_name, cwd=cwd,
                                env=_environment(project, profile.executables), timeout=timeout)
    from laew.security.linux_landlock import run_restricted
    private = (profile.telemetry_root, *profile.backup_roots,
               *(p.root for p in profile.projects if p is not project),
               *(p.scratch for p in profile.projects if p is not project))
    result = run_restricted(argv, project=project.root, scratch=project.scratch, cwd=cwd,
                            readonly_roots=profile.readonly_roots, private_roots=private,
                            env={"LANG": "C", "LC_ALL": "C"}, timeout=timeout)
    if result.state == "timeout":
        raise subprocess.TimeoutExpired("project process", timeout)
    if result.state != "completed":
        raise _deny()
    return subprocess.CompletedProcess(argv, result.returncode, result.stdout.decode("utf-8", "replace"),
                                       result.stderr.decode("utf-8", "replace"))


def _probe(profile):
    python = profile.executables.get("python")
    if python is None:
        raise _deny()
    program = """
import os, sys
with os.scandir(sys.argv[1]):
    pass
for path in sys.argv[2:]:
    try:
        with os.scandir(path):
            pass
    except PermissionError:
        continue
    sys.exit(7)
"""
    for project in profile.projects:
        private = (profile.telemetry_root, *profile.backup_roots,
                   *(other.root for other in profile.projects if other is not project),
                   *(other.scratch for other in profile.projects if other is not project))
        argv = [str(python), "-I", "-c", program, str(project.root), *map(str, private)]
        result = _launch(profile, project, argv, project.root, 3.0)
        if result.returncode != 0:
            raise _deny()


def activate_runtime_protection(manifest_path=None, *, retain=True):
    """Fail closed for tool processes when a configured boundary is unavailable."""
    global _active
    try:
        profile = _load()
        if profile is None:
            return None
        root = _telemetry_root(profile, manifest_path)
        if profile != _active:
            _probe(profile)
            _active = profile
        if root is not None and retain:
            from laew.telemetry import TelemetrySink
            return TelemetrySink(root, announce=True)
    except Exception:
        _active = None
        _LOG.warning("protected_installation_unavailable")
    return None


def requires_isolation():
    return _active is not None or bool(os.environ.get(_CONFIG_ENV))


def run_project_process(argv, *, cwd, timeout):
    """Run project commands through the verified AppContainer, never a fallback."""
    profile = _active
    if profile is None:
        raise _deny()
    try:
        directory = _path(str(cwd))
        project = next((candidate for candidate in profile.projects if directory.is_relative_to(candidate.root)), None)
        executable = profile.executables.get(argv[0].casefold()) if argv else None
        if project is None or executable is None:
            raise _deny()
        return _launch(profile, project, [str(executable), *argv[1:]], directory, timeout)
    except subprocess.TimeoutExpired:
        raise subprocess.TimeoutExpired("project process", timeout) from None
    except (OSError, TypeError, ValueError):
        raise _deny() from None
