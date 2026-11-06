"""Bounded, lossless Markdown block chunking without a full Markdown parser.

Offsets refer to the body after frontmatter removal. Oversized lines are split
by character; repeated table headers are explicitly separate from source spans.
"""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MarkdownChunk:
    text: str
    path: tuple[str, ...]
    start_line: int
    end_line: int
    kind: str
    language: str = ""
    start_offset: int = 0
    end_offset: int = 0
    repeated_prefix: str = ""


def structure_chunks(body: str, size: int) -> list[MarkdownChunk]:
    if size < 32:
        raise ValueError("structure-v1 requires a chunk size of at least 32 characters")
    if not body.strip():
        return []
    lines = body.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    heading = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*(?:\r?\n)?$')
    fence = re.compile(r'^ {0,3}(`{3,}|~{3,})([^\r\n]*)')
    separator = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$')
    result = []
    path = []
    i = 0
    pending = None

    def emit(start, end, kind, language='', prefix=''):
        # Slice on line boundaries where possible, then on characters for a
        # single oversized line. Source spans partition the original body.
        nonlocal pending
        pos = offsets[start] if pending is None else pending
        stop = offsets[end]
        if not body[pos:stop].strip():
            pending = pos
            return
        pending = None
        while pos < stop:
            repeated = prefix if pos > offsets[start] and len(prefix) < size // 2 else ''
            limit = min(stop, pos + size - len(repeated))
            cut = body.rfind('\n', pos, limit)
            if limit < stop and cut >= pos:
                limit = cut + 1
            if limit <= pos:
                limit = min(stop, pos + size - len(repeated))
            import bisect
            first = bisect.bisect_right(offsets, pos)
            last = bisect.bisect_left(offsets, limit)
            result.append(MarkdownChunk(repeated + body[pos:limit], tuple(x[1] for x in path),
                                        first, max(first, last), kind, language, pos, limit, repeated))
            pos = limit

    while i < len(lines):
        m = heading.match(lines[i])
        if m:
            level = len(m.group(1))
            path = [entry for entry in path if entry[0] < level]
            path.append((level, m.group(2).strip()))
        start = i
        f = fence.match(lines[i])
        if f:
            marker, info = f.group(1), f.group(2).strip()
            language = info.split()[0] if info else ''
            i += 1
            close = re.compile(r'^ {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}\s*$')
            while i < len(lines):
                i += 1
                if close.match(lines[i - 1]):
                    break
            emit(start, i, 'code', language)
        elif i + 1 < len(lines) and '|' in lines[i] and separator.match(lines[i + 1]):
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                i += 1
            emit(start, i, 'table', prefix=lines[start] + lines[start + 1])
        else:
            i += 1
            while i < len(lines):
                if heading.match(lines[i]) or fence.match(lines[i]):
                    break
                if i + 1 < len(lines) and '|' in lines[i] and separator.match(lines[i + 1]):
                    break
                i += 1
            emit(start, i, 'text')
    return result
