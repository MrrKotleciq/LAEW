"""Offline-only candidate planning for two independent RAG experiments."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import time

from laew.eval.complementary_context_study import load_inputs, offline, read, seal, sha, write
from laew.eval.real_world_retrieval import payload_segments, union
from laew.eval.retrieval_budget_diagnostics import FrozenVectors
from laew.rag.markdown_chunker import structure_chunks
from laew.rag.obsidian import extract_links, extract_tags
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import DocumentChunk

TARGET = 1000
CAP = 1600
HEADING = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*(?:\r?\n)?$')
LIST = re.compile(r'^\s*(?:[-+*]|\d+[.)])\s+')
PARAGRAPH_BREAK = re.compile(r'\n[^\S\n]*\n')
WEIGHT_SHA = '06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'


def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def intersects(ranges, banned):
    return any(a < z and x < b for a, b in ranges for x, z in banned)


def segments(text, base):
    pos = base
    for line in text.splitlines(keepends=True):
        yield pos, pos + len(line), line
        pos += len(line)


def narrative_atoms(text, start, stop):
    """Keep lists spanning adjacent paragraphs together when they fit."""
    ends = [start + m.end() for m in PARAGRAPH_BREAK.finditer(text[start:stop])] + [stop]
    atoms = []
    for end in ends:
        if start == end:
            continue
        kind = 'list' if LIST.match(text[start:end]) else 'paragraph'
        if atoms and kind == atoms[-1][2] == 'list' and end - atoms[-1][0] <= CAP:
            atoms[-1] = (atoms[-1][0], end, kind)
        else:
            atoms.append((start, end, kind))
        start = end
    return atoms


def adaptive_chunks(text: str, body_offset: int, banned: list[tuple[int, int]]) -> tuple[list[dict], list[dict]]:
    """Slice a full normalized document after its frontmatter."""
    body = text[body_offset:]
    blocks = structure_chunks(body, max(32, len(body) + 1))
    path, rows, withheld, pending = [], [], [], []

    def flush():
        if pending:
            a, z = pending[0][0], pending[-1][1]
            if text[a:z].strip():
                rows.append(dict(start=a, end=z, text=text[a:z], path=tuple(label for _, label in path if label),
                                 atoms=[list(atom) for atom in pending]))
            pending.clear()

    def enqueue(a, z, kind):
        if pending and (a != pending[-1][1] or z - pending[0][0] > CAP
                        or (z - pending[0][0] > TARGET and pending[-1][1] - pending[0][0] >= TARGET // 2
                            and any(atom[2] != 'heading' for atom in pending))):
            flush()
        pending.append((a, z, kind))

    for block in blocks:
        start, stop = body_offset + block.start_offset, body_offset + block.end_offset
        if block.kind in ('table', 'code'):
            if stop - start > CAP or intersects([(start, stop)], banned):
                flush()
                withheld.append(dict(start=start, end=stop, kind=block.kind,
                                     reason='restricted' if intersects([(start, stop)], banned) else 'oversize'))
            else:
                enqueue(start, stop, block.kind)
            continue
        run_start = start

        def narrative(stop_at):
            for a, z, kind in narrative_atoms(text, run_start, stop_at):
                while z - a > CAP:
                    boundary = max(text.rfind(ch, a + TARGET // 2, a + TARGET) for ch in ('\n', ' ', '\t'))
                    end = boundary + 1 if boundary >= 0 else a + TARGET
                    enqueue(a, end, kind + '-part')
                    flush()
                    a = end
                    kind = kind.removesuffix('-continuation') + '-continuation'
                if z > a:
                    enqueue(a, z, kind)

        for a, z, line in segments(text[start:stop], start):
            heading = HEADING.fullmatch(line)
            restricted = intersects([(a, z)], banned)
            if not heading and not restricted:
                continue
            narrative(a)
            flush()
            if heading:
                level = len(heading[1])
                path = [(old, label) for old, label in path if old < level]
                path.append((level, heading[2].strip() if not restricted and z - a <= CAP else ''))
            if restricted or z - a > CAP:
                withheld.append(dict(start=a, end=z, kind='line', reason='restricted' if restricted else 'oversize'))
            else:
                enqueue(a, z, 'heading')
            run_start = z
        narrative(stop)
    flush()
    return rows, withheld


def restriction_map(config, data):
    path = Path(config['corpus']) / 'review/r3d/restricted-regions.json'
    regions = read(path)['regions']
    if len(regions) != 10:
        raise ValueError('Expected ten restrictions')
    banned = defaultdict(list)
    for region in regions:
        sid = region['source_id']
        if region['normalized_sha256'] != data['units'][sid]['normalized_sha256']:
            raise ValueError('Restriction source version changed')
        for span in region['component_ranges'] + region['related_context_ranges']:
            a, z = span['start'], span['end']
            if not 0 <= a < z <= len(data['texts'][sid]) or digest(data['texts'][sid][a:z]) != span['sha256_utf8']:
                raise ValueError('Restriction offsets or content changed')
            banned[sid].append((a, z))
    return banned, sha(path)


def restricted_attribution(chunk, unsafe_headings, forbidden_texts):
    metadata = chunk.metadata
    headings = [metadata.get('section_header', ''), *metadata.get('section_path', [])]
    return (any(label in unsafe_headings for label in headings)
            or bool(set(metadata.get('tags', [])) & forbidden_texts['tags'])
            or bool(set(metadata.get('backlinks', [])) & forbidden_texts['backlinks']))


def contextual_text(chunk, unit):
    metadata = chunk.metadata
    path = metadata.get('section_path') or []
    scope = unit.get('applicable_versions')
    lines = [f"Document: {unit['id']}", f"Source revision: {unit['revision']}"]
    if scope:
        lines.append(f"Applicability: {scope}")
    if path:
        lines.append("Section: " + " > ".join(path))
    return '\n'.join(lines) + '\n\n' + chunk.text


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {}
    return dict(min=ordered[0], median=statistics.median(ordered),
                p95=ordered[math.ceil(.95 * len(ordered)) - 1], max=ordered[-1], total=sum(ordered))


def rendered_size(chunk, renderer):
    rendered, used, _ = renderer._build_context([(chunk, 1.0)])
    if len(used) != 1 or used[0][0].text != chunk.text:
        raise ValueError('Single fragment clipped at measurement ceiling')
    return len(rendered)


def build(config, data, out, weight_receipt):
    tick = time.perf_counter()
    banned, restrictions_sha = restriction_map(config, data)
    run = Path(config['run'])
    metadata = read(run / 'run-metadata.json')
    catalog = metadata['model_catalog']
    if (catalog['id'], catalog['meta']['ftype'], catalog['meta']['n_embd']) != ('laew-qwen3-embedding', 'Q8_0', 1024):
        raise ValueError('Unexpected historical catalog')
    receipt = read(weight_receipt)
    weight = Path(receipt['model_path'])
    with weight.open('rb') as file:
        weight_sha = hashlib.file_digest(file, 'sha256').hexdigest()
    if weight_sha != receipt['weight_sha256'] or weight_sha != WEIGHT_SHA or not receipt['server']['pooling'].startswith('last;'):
        raise ValueError('Historical weight or pooling provenance mismatch')

    arms, excluded, withheld = defaultdict(list), [], []
    renderer = RAGPipeline(None, None, max_context_tokens=100_000)
    for sid, unit in data['units'].items():
        text = data['texts'][sid]
        if digest(text) != unit['normalized_sha256']:
            raise ValueError('Unit offsets must refer to exact normalized text')
        blocked = banned[sid]
        forbidden_lines, safe_lines = [], []
        for a, z, line in segments(text, 0):
            (forbidden_lines if intersects([(a, z)], blocked) else safe_lines).append(line)
        unsafe_headings = {m[2].strip() for line in forbidden_lines if (m := HEADING.fullmatch(line))}
        forbidden_metadata = {}
        for key, extract in [('tags', extract_tags), ('backlinks', extract_links)]:
            forbidden_metadata[key] = set(extract(''.join(forbidden_lines))) - set(extract('\n'.join(safe_lines)))
        if intersects([(0, unit['body_offset'])], blocked):
            raise ValueError('Restriction affects frontmatter')
        base_metadata = {'tags': [], 'backlinks': [], 'frontmatter': {}}
        for strategy, arm in [('legacy', 'B'), ('structure-v2', 'C')]:
            for chunk_id, (chunk_sid, mapping, _) in data['sources'][strategy].items():
                if chunk_sid != sid:
                    continue
                chunk = data['chunks'][strategy, chunk_id]
                base_metadata = {key: chunk.metadata[key] for key in base_metadata}
                visible = payload_segments(chunk, mapping, text)
                historical = [(mapping['start'], mapping['end']), *mapping['context_spans'], *visible]
                reason = None
                if intersects(historical, blocked):
                    reason = 'body-or-copied-context'
                elif restricted_attribution(chunk, unsafe_headings, forbidden_metadata):
                    reason = 'attribution'
                elif blocked and '[Table columns]\n' in chunk.text[:mapping['synthetic_chars']]:
                    reason = 'table-prefix-on-restricted-unit'
                if reason:
                    excluded.append(dict(arm=arm, id=chunk_id, source_id=sid, reason=reason))
                    continue
                row = dict(id=chunk_id, source_id=sid, text=chunk.text, metadata=chunk.metadata,
                           file_path=chunk.file_path, ranges=visible, rendered_chars=rendered_size(chunk, renderer),
                           embedding_text_sha256=digest(chunk.text))
                arms[arm].append(row)
                if arm == 'C':
                    enriched = contextual_text(chunk, unit)
                    arms['contextual'].append(dict(row, embedding_text_sha256=digest(enriched), embedding_text=enriched))

        rows, gaps = adaptive_chunks(text, unit['body_offset'], blocked)
        withheld.extend(dict(gap, source_id=sid) for gap in gaps)
        for index, row in enumerate(rows):
            a, z = row['start'], row['end']
            chunk_id = f"global:{sid}:adaptive:{index}"
            chunk = DocumentChunk(chunk_id=chunk_id, text=row['text'], source='global',
                                  file_path=Path(unit['normalized_path']).name, embedding=None,
                                  metadata=dict(base_metadata, section_path=list(row['path']),
                                                section_header=row['path'][-1] if row['path'] else ''))
            if (text[a:z] != chunk.text or len(chunk.text) > CAP or not chunk.text.strip()
                    or intersects([(a, z)], blocked) or restricted_attribution(chunk, unsafe_headings, forbidden_metadata)):
                raise ValueError(f'Adaptive provenance violation: {chunk_id}')
            arms['adaptive'].append(dict(id=chunk_id, source_id=sid, text=chunk.text,
                                        metadata=chunk.metadata, file_path=chunk.file_path,
                                        ranges=[[a, z]], atoms=row['atoms'], rendered_chars=rendered_size(chunk, renderer),
                                        embedding_text_sha256=digest(chunk.text)))
    cache = FrozenVectors(run / 'vector-cache.sqlite3', metadata)
    unique, workload, questions = {}, {}, {}

    def cached(text, key):
        if key not in unique:
            try:
                cache.get(text)
            except RuntimeError as error:
                if not str(error).startswith('EMBEDDING STOP GATE:'):
                    raise
                unique[key] = False
            else:
                unique[key] = True
        return unique[key]

    try:
        questions = {qid: digest(q['text']) for qid, q in data['questions'].items()}
        if not all(cached(data['questions'][qid]['text'], key) for qid, key in questions.items()):
            raise ValueError('Historical query cache has a miss')
        for arm, rows in arms.items():
            for row in rows:
                value = row.pop('embedding_text', row['text'])
                key = row['embedding_text_sha256']
                row['cache_hit'] = cached(value, key)
                if not row['cache_hit']:
                    if arm in ('B', 'C'):
                        raise ValueError('Frozen control text missed cache')
                    workload.setdefault(key, dict(sha256=key, text=value, arms=[]))
                    if arm not in workload[key]['arms']:
                        workload[key]['arms'].append(arm)
    finally:
        cache.close()

    out.mkdir(parents=True, exist_ok=False)
    units = {sid: {key: unit[key] for key in ('normalized_sha256', 'revision', 'family', 'language',
                                                'applicable_versions', 'normalized_path', 'source_map')}
             for sid, unit in data['units'].items()}
    def workload_stats(items):
        sizes = [len(item['text']) for item in items]
        return dict(inputs=len(sizes), estimated_tokens_chars_per_4=sum(math.ceil(n / 4) for n in sizes),
                    characters=distribution(sizes), max_utf8_bytes=max((len(item['text'].encode()) for item in items), default=0),
                    raw_float32_bytes=len(sizes) * 4096)

    summaries = {}
    for arm, rows in arms.items():
        keys = {row['embedding_text_sha256'] for row in rows}
        summaries[arm] = dict(chunks=len(rows), unique_inputs=len(keys),
                              unique_cached=sum(unique[key] for key in keys),
                              chunk_chars=distribution([len(row['text']) for row in rows]),
                              rendered_chars=distribution([row['rendered_chars'] for row in rows]),
                              individually_over_scope=sum(row['rendered_chars'] > 4000 for row in rows),
                              new=workload_stats([value for value in workload.values() if arm in value['arms']]))
    write(out / 'inventory.json', dict(arms=arms, units=units, excluded=excluded, withheld=withheld))
    write(out / 'pending-embedding-inputs.json', list(workload.values()))
    write(out / 'preflight.json', dict(input_receipts=data['receipts'], restrictions_sha256=restrictions_sha,
                                      cache_sha256=sha(run / 'vector-cache.sqlite3'),
                                      model_catalog=catalog, model_identity_sha256=metadata['model_identity_sha256'],
                                      weight_sha256=weight_sha, weight_bytes=weight.stat().st_size,
                                      historical_server=receipt['server'], historical_server_receipt_sha256=sha(weight_receipt),
                                      active_server_verified=False, caches_verified=len(cache.keys), queries=questions,
                                      source_units=len(units), arms=summaries, all_new=workload_stats(list(workload.values())),
                                      excluded=dict(Counter(row['arm'] for row in excluded)),
                                      withheld=dict(Counter(f"{row['reason']}/{row['kind']}" for row in withheld)),
                                      planning_seconds=time.perf_counter() - tick,
                                      embedding_calls=0, generation_calls=0))
    seal(out, ['inventory.json', 'pending-embedding-inputs.json', 'preflight.json'],
         code_sha256=sha(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('weight_receipt', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    with offline():
        config = read(args.config)
        data = load_inputs(config)
        build(config, data, args.output, args.weight_receipt)


if __name__ == '__main__':
    main()
