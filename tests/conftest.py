"""Shared test-suite configuration for LAEW."""

import os
import shutil
from pathlib import Path

import pytest


def _locate_git_usr_bin() -> Path | None:
    """
    Locate the directory providing Unix inspector commands on Windows.

    LAEW's terminal tool contract allowlists POSIX-style inspector commands
    (``ls``, ``cat``, ``git status``, ...). On Unix those are system commands;
    on Windows they ship with Git for Windows under ``usr\\bin``. CI runs on
    ubuntu, but a developer shell (e.g. PowerShell) may not have that
    directory on PATH, which makes the terminal tool tests fail with
    ``FileNotFoundError`` (WinError 2). Prepend the directory when present.
    """
    git = shutil.which("git")
    if git:
        # e.g. C:\\Program Files\\Git\\cmd\\git.exe -> C:\\Program Files\\Git\\usr\\bin
        candidate = Path(git).resolve().parent
        for _ in range(3):
            probe = candidate / "usr" / "bin"
            if probe.is_dir():
                return probe
            candidate = candidate.parent
    # Fall back to well-known install roots (e.g. GitHub Desktop's git shim
    # does not expose usr\\bin through `shutil.which("git")`).
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(var)
        if root:
            probe = Path(root) / "Git" / "usr" / "bin"
            if probe.is_dir():
                return probe
    return None


@pytest.fixture(scope="session", autouse=True)
def _windows_unix_tools_on_path():
    """
    Make Git for Windows' POSIX tools resolvable on Windows test runs.

    Only mutates ``PATH`` on Windows, and only when the directory exists on
    disk but is missing from ``PATH``; on POSIX shells (and CI's ubuntu
    runner) it is a no-op. It does not change any LAEW runtime code or
    security policy -- it mirrors the environment a Unix shell provides so the
    same allowlist/blacklist/boundary tests run meaningfully everywhere.
    """
    if os.name != "nt":
        yield
        return

    usr_bin = _locate_git_usr_bin()
    if usr_bin is None:
        yield
        return

    path = os.environ.get("PATH", "")
    if str(usr_bin).lower() not in path.lower():
        os.environ["PATH"] = f"{usr_bin}{os.pathsep}{path}"
    yield