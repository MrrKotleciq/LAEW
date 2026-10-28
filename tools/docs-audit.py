"""Audit Markdown frontmatter for the LAEW knowledge-management migration.

Read-only analysis helper.
Does not modify project files.

Usage:
    python -u tools/docs-audit.py
    python -u tools/docs-audit.py docs
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


CORE_FIELDS = [
    "name",
    "description",
    "scope",
    "status",
    "tags",
]

EXCLUDED_DIRS = {
    "history",
}


def is_excluded(path: Path) -> bool:
    """Return True for files intentionally excluded from migration."""
    parts = path.parts

    # Entire docs/history/** tree.
    if "history" in parts:
        return True

    # Only source chapters are excluded.
    if "source" in parts and path.name.startswith("Chapter-") and path.suffix == ".md":
        return True

    return False


def parse_frontmatter(path: Path) -> tuple[str, dict[str, Any] | None]:
    """Parse YAML frontmatter.

    Returns:
        (status, metadata)

    Status values:
        NO_FRONTMATTER
        INVALID_YAML
        INVALID_STRUCTURE
        VALID
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "INVALID_FILE", None

    lines = text.splitlines()

    if not lines or lines[0].strip() != "---":
        return "NO_FRONTMATTER", None

    end = None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break

    if end is None:
        return "INVALID_YAML", None

    raw_yaml = "\n".join(lines[1:end])

    try:
        data = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return "INVALID_YAML", None

    if data is None:
        return "VALID", {}

    if not isinstance(data, dict):
        return "INVALID_STRUCTURE", None

    return "VALID", data


def audit(root: Path) -> list[dict[str, Any]]:
    """Audit all Markdown files below root."""
    rows: list[dict[str, Any]] = []

    for dirpath, dirs, files in os.walk(root):
        current_dir = Path(dirpath)

        # Do not descend into intentionally excluded directories.
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in EXCLUDED_DIRS
        ]

        for filename in sorted(files):
            if not filename.endswith(".md"):
                continue

            path = current_dir / filename
            relative = path.relative_to(root)

            if is_excluded(relative):
                continue

            fm_status, metadata = parse_frontmatter(path)

            if fm_status != "VALID":
                rows.append(
                    {
                        "path": str(relative),
                        "type": fm_status,
                        "missing": "",
                    }
                )
                continue

            metadata = metadata or {}

            document_type = metadata.get("type", "MISSING_TYPE")

            missing = [
                field
                for field in CORE_FIELDS
                if field not in metadata
            ]

            rows.append(
                {
                    "path": str(relative),
                    "type": str(document_type),
                    "missing": ",".join(missing) if missing else "OK",
                }
            )

    return rows


def print_report(rows: list[dict[str, Any]]) -> None:
    """Print a deterministic human-readable report."""
    print(
        f"{'TYPE':<20} {'MISSING':<45} PATH",
        flush=True,
    )
    print("-" * 100, flush=True)

    for row in rows:
        print(
            f"{row['type']:<20} "
            f"{row['missing']:<45} "
            f"{row['path']}",
            flush=True,
        )

    print(flush=True)

    total = len(rows)
    no_frontmatter = sum(
        row["type"] == "NO_FRONTMATTER"
        for row in rows
    )
    invalid_yaml = sum(
        row["type"] == "INVALID_YAML"
        for row in rows
    )
    invalid_structure = sum(
        row["type"] == "INVALID_STRUCTURE"
        for row in rows
    )
    missing_type = sum(
        row["type"] == "MISSING_TYPE"
        for row in rows
    )

    print("Summary", flush=True)
    print(f"  Markdown files audited: {total}", flush=True)
    print(f"  No frontmatter:         {no_frontmatter}", flush=True)
    print(f"  Invalid YAML:           {invalid_yaml}", flush=True)
    print(f"  Invalid structure:      {invalid_structure}", flush=True)
    print(f"  Missing type:           {missing_type}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit LAEW Markdown frontmatter."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default="docs",
        help="Directory to audit (default: docs)",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()

    if not root.exists():
        raise SystemExit(f"Directory does not exist: {root}")

    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    print(f"Auditing: {root}", flush=True)
    print(flush=True)

    rows = audit(root)
    print_report(rows)


if __name__ == "__main__":
    main()