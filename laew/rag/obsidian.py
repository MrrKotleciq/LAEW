"""
Obsidian note parsing for RAG ingestion (Milestone 17).

Parses the Obsidian "Second Brain" vault (ADR-002) so its notes — title,
frontmatter, ``#tags`` and ``[[backlinks]]`` — survive chunking and are
surfaced in retrieved context (ADR-011).

The parser is intentionally dependency-free: it handles the subset Obsidian
notes use (``title``, ``tags``, ``backlinks`` and simple inline/block lists)
so the RAG core needs no PyYAML dependency.
"""

import re
from typing import Any, Dict, List

#: Matches a YAML frontmatter block delimited by ``---`` lines.
FRONTMATTER_RE = re.compile(
    r"^---[ \t]*\n(.*?)\n?^---[ \t]*\n?",
    re.DOTALL | re.MULTILINE,
)

#: Matches a single Obsidian backlink: ``[[link text]]``.
LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")

#: Matches an Obsidian tag: ``#tag``, ``#tag-name``, ``#tag with spaces``.
TAG_RE = re.compile(r"#\w[\w\s\-]*")


def _parse_frontmatter_block(block: str) -> Dict[str, Any]:
    """Parse a frontmatter body into a dict.

    Handles scalar values, inline flow lists (``key: [a, b]``) and block
    lists (``key:`` followed by indented ``- item`` lines).
    """
    result: Dict[str, Any] = {}
    lines = block.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" not in stripped:
            i += 1
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()

        if value.startswith("[") and value.endswith("]"):
            items = [
                s.strip().strip('"').strip("'")
                for s in value[1:-1].split(",")
                if s.strip()
            ]
            result[key] = items
            i += 1
        elif value == "":
            indent = len(line) - len(line.lstrip())
            # Block list: collect following more-indented list items.
            items: List[str] = []
            j = i + 1
            while j < len(lines):
                nline = lines[j]
                nstripped = nline.strip()
                if not nstripped or nstripped.startswith("#"):
                    j += 1
                    continue
                nindent = len(nline) - len(nline.lstrip())
                if indent < nindent and (
                    nstripped.startswith("- ") or nstripped.startswith("-")
                ):
                    item = (
                        nstripped[2:].strip()
                        if nstripped.startswith("- ")
                        else nstripped.strip()
                    )
                    items.append(item)
                    j += 1
                else:
                    break
            result[key] = items
            i = j
        else:
            result[key] = value
            i += 1

    return result


def _strip_frontmatter(content: str) -> str:
    """Return *content* with any leading YAML frontmatter block removed."""
    match = FRONTMATTER_RE.search(content)
    return content[match.end():] if match else content


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """
    Parse YAML frontmatter from an Obsidian note.

    Args:
        content: Full note text (frontmatter + body).

    Returns:
        Dict of frontmatter fields. Empty dict when no frontmatter is present.
    """
    match = FRONTMATTER_RE.search(content)
    if not match:
        return {}
    return _parse_frontmatter_block(match.group(1))


def extract_links(text: str) -> List[str]:
    """Extract Obsidian ``[[backlinks]]`` targets from *text*."""
    return [m.group(1).strip() for m in LINK_RE.finditer(text)]


def extract_tags(text: str) -> List[str]:
    """
    Extract Obsidian ``#tags`` from *text*.

    Deduplicates while preserving order and strips the leading ``#``.
    """
    seen: List[str] = []
    for m in TAG_RE.finditer(text):
        tag = m.group(0)[1:].strip()
        if tag and tag not in seen:
            seen.append(tag)
    return seen


def parse_note(content: str) -> Dict[str, Any]:
    """
    Parse an Obsidian note into structured metadata.

    Args:
        content: Full note text (frontmatter + body).

    Returns:
        Dict with ``title``, ``tags``, ``backlinks`` and ``body`` keys.
        ``tags`` and ``backlinks`` fall back to inline extraction when the
        frontmatter omits them.
    """
    frontmatter = parse_frontmatter(content)
    body = _strip_frontmatter(content).strip()

    title = frontmatter.get("title")
    if not title:
        first = body.splitlines()
        if first:
            line = first[0].strip()
            if line.startswith("#"):
                title = line.lstrip("#").strip()
            elif line:
                title = line

    tags = list(frontmatter.get("tags", []) or [])
    backlinks = list(frontmatter.get("backlinks", []) or [])
    if not backlinks:
        backlinks = extract_links(content)
    if not tags:
        tags = extract_tags(content)

    return {
        "title": title,
        "tags": tags,
        "backlinks": backlinks,
        "body": body,
    }
