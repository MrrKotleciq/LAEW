"""Temporary storage for standalone validation entry points."""

from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys
import tempfile
from unittest.mock import patch

if __package__:
    from .run_isolated import OPERATIONAL_BACKUP_ENV, REPARSE_POINT, REPO, WindowsJob, finish, make_run_directory
else:
    from run_isolated import OPERATIONAL_BACKUP_ENV, REPARSE_POINT, REPO, WindowsJob, finish, make_run_directory


@contextmanager
def validation_environment(workspace):
    temp = workspace / "locks"
    temp.mkdir(exist_ok=True)
    with patch.dict(os.environ, {
        "TEMP": str(temp), "TMP": str(temp), "TMPDIR": str(temp),
        "LAEW_WORKSPACE_ROOT": str(workspace),
        "LAEW_MEMORY_STORAGE": str(workspace / "runtime" / "memory" / "memory.db"),
        "LAEW_KNOWLEDGE_STORAGE": str(workspace / "runtime" / "knowledge" / "curation.db"),
    }), patch.object(tempfile, "tempdir", str(temp)):
        for key in OPERATIONAL_BACKUP_ENV:
            os.environ.pop(key, None)
        yield


@contextmanager
def validation_workspace(keep=False):
    job = WindowsJob() if os.name == "nt" else None
    try:
        workspace = make_run_directory()
        original = workspace.lstat()
        print(f"Validation workspace: {workspace}", file=sys.stderr, flush=True)
        try:
            with validation_environment(workspace):
                yield workspace
        finally:
            finish(workspace, original, keep, None, job)
    finally:
        if job:
            job.close()


def retained_m17_workspace(value):
    """Accept a retained validation workspace with only ordinary files and directories."""
    supplied = Path(value).absolute()
    workspace = supplied.resolve(strict=True)
    excluded = (REPO, Path(r"C:\ROOT")) if os.name == "nt" else (REPO,)
    if (workspace != supplied or not workspace.name.startswith("laew-run-")
            or any(workspace.is_relative_to(root) for root in excluded)
            or any((parent / ".obsidian").is_dir() for parent in (workspace, *workspace.parents))):
        raise ValueError("Expected a retained M17 workspace outside operational storage.")

    def check_tree(path):
        info = path.lstat()
        if getattr(info, "st_file_attributes", 0) & REPARSE_POINT:
            raise ValueError("The retained workspace contains a reparse point.")
        if stat.S_ISDIR(info.st_mode):
            for child in path.iterdir():
                check_tree(child)
        elif not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("The retained workspace contains a linked or special file.")

    check_tree(workspace)
    if not (workspace / ".m17-validation").is_file():
        raise ValueError("The workspace must come from validate_m17.py.")
    return workspace
