"""Versioned contextual Markdown grouping with bounded synthetic context.

Source spans partition the body; synthetic prefixes have separate provenance.
No source files, retrieval scoring or routing decisions are changed here.
"""
from bisect import bisect_right
from dataclasses import dataclass
import re
from laew.rag.markdown_chunker import structure_chunks


@dataclass(frozen=True)
class ContextChunk:
    text: str
    path: tuple[str, ...]
    start_line: int
    end_line: int
    kind: str
    language: str
    start_offset: int
    end_offset: int
    context_spans: tuple[tuple[int, int], ...]
    synthetic_chars: int
    limited_context: bool
    block_id: str


def contextual_chunks(body: str, size: int) -> list[ContextChunk]:
    """Group related blocks, then split with a bounded descriptive envelope."""
    if size < 128:
        raise ValueError('structure-v2 requires at least 128 characters')
    blocks = structure_chunks(body, max(32, len(body) + 1))
    if not blocks:
        return []
    # Heading-only parents belong to their first descendant, not to the index
    # as an independent semantically empty retrieval unit.
    groups = []
    for b in blocks:
        if groups and (groups[-1][-1].path == b.path or
                       all(not re.sub(r'(?m)^\s*#{1,6}\s+.*$', '', x.text).strip() for x in groups[-1])):
            groups[-1].append(b)
        else:
            groups.append([b])
    line_starts = [0] + [m.end() for m in re.finditer('\n', body)]
    result = []
    intros = {}
    for group in groups:
        path = group[-1].path
        start, stop = group[0].start_offset, group[-1].end_offset
        language = next((b.language for b in group if b.language), '')
        kinds = sorted({b.kind for b in group})
        kind = kinds[0] if len(kinds) == 1 else 'mixed'
        # Narrative before/after code or tables carries interpretation and
        # restrictions; ancestor introductions carry procedure prerequisites.
        narrative = []
        for b in group:
            if b.kind == 'text':
                raw = body[b.start_offset:b.end_offset]
                match = re.search(r'(?m)^(?!\s*#)(?=\S).+', raw)
                if match:
                    narrative.append((b.start_offset + match.start(), b.end_offset))
        if narrative:
            intros[path] = narrative[0]
        candidates = [intros[p] for n in range(1, len(path)) if (p := path[:n]) in intros]
        if any(b.kind in ('code','table') for b in group):
            candidates += narrative
        elif stop - start > size:
            candidates += narrative[:1]
        # Split the fixed context allowance across candidates so a final
        # restriction is not displaced by an arbitrarily long introduction.
        candidates = list(dict.fromkeys(candidates))
        context_budget = size // 4
        spans = []
        if candidates:
            allowance = max(1, (context_budget - 24) // len(candidates))
            spans = [(a, min(z, a + allowance)) for a, z in candidates]
        desc = '\n'.join(body[a:z].strip() for a,z in spans)
        context = ('[Related context]\n' + desc + '\n') if desc else ''
        context = context[:context_budget]
        limited = any(z-a > (spans[i][1]-spans[i][0]) for i,(a,z) in enumerate(candidates))
        pos = start
        while pos < stop:
            table = next((b for b in group if b.kind == 'table' and b.start_offset < pos < b.end_offset), None)
            extra = ''
            if table:
                header = ''.join(body[table.start_offset:table.end_offset].splitlines(keepends=True)[:2])
                extra = '[Table columns]\n' + header[:size // 5] + '\n'
                limited = limited or len(header) > size // 5
            elif language and pos > start:
                extra = f'[Code continuation: {language[:40]}]\n'
            # Context is unnecessary when the entire logical group fits.
            prefix = context + extra if stop-start > size else ''
            available = size - len(prefix)
            end = min(stop, pos + available)
            if end < stop:
                # Prefer blank lines (paragraph/function boundaries), then
                # complete lines. A single huge line uses a character fallback.
                for delimiter in ('\n\n', '\n'):
                    boundary = body.rfind(delimiter, pos, end)
                    if boundary > pos + available // 2:
                        end = boundary + len(delimiter)
                        break
            result.append(ContextChunk(prefix + body[pos:end], path,
                bisect_right(line_starts,pos), bisect_right(line_starts,max(pos,end-1)),
                kind,language,pos,end,tuple(spans) if prefix else (),len(prefix),limited,
                f'{start}:{stop}'))
            pos = end
    return result
