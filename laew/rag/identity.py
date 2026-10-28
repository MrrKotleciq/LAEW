"""Stable collection identities for explicitly selected project roots."""

import hashlib
import ntpath
import os
from pathlib import Path


def canonical_project_path(path: str | Path) -> str:
    """Canonicalize an absolute project path, including Windows case semantics."""
    raw = os.fspath(path)
    if os.name == "nt":
        return ntpath.normcase(ntpath.normpath(str(Path(raw).expanduser().resolve())))
    # Support comparisons of Windows paths in platform-independent tooling.
    if ntpath.isabs(raw) and ntpath.splitdrive(raw)[0]:
        return ntpath.normcase(ntpath.normpath(raw))
    return str(Path(raw).expanduser().resolve())


def project_collection_name(path: str | Path) -> str:
    """Return a short, Chroma-compatible name derived from the full path."""
    digest = hashlib.sha256(canonical_project_path(path).encode("utf-8")).hexdigest()
    return "laew_project_" + digest[:32]
