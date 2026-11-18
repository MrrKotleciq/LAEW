"""Offline retrieval and separate scoring for the two frozen RAG experiments."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import math
from pathlib import Path
import sqlite3
from time import perf_counter
from unittest.mock import patch

import numpy as np

from laew.eval.complementary_context_study import load_inputs, offline, read, seal, sha, verify_manifest, write
from laew.eval.final_rag_embedding_job import COUNTS, REQUESTS, WORKLOAD_SHA
from laew.eval.final_rag_preflight import digest, distribution, intersects, restriction_map
from laew.eval.real_world_retrieval import coverage_of, payload_segments
from laew.eval.retrieval_budget_diagnostics import FrozenVectors
from laew.eval.scoring_calibration import score_evidence
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk

ARMS = ('adaptive', 'contextual')
STAGES = ('raw', 'eligible', 'selected')
# Post-collection diagnostic for explicit, unambiguous target mismatches only.
# Other-hardware technical advice may be shared, and cross-printer accessories
# and PostgreSQL transition notes need passage-level review.
HARDWARE_TARGET = {
    'P02': 'prusa-mini-pl', 'S08': 'prusa-mini-pl', 'S14': 'prusa-mini-pl',
    'S05': 'prusa-mk4s-en', 'S06': 'prusa-mk4-de', 'S07': 'prusa-xl-de',
    'S16': 'prusa-xl-de', 'S09': 'prusa-mk3s-pl',
}
PRIMARY_HARDWARE_MANUALS = set(HARDWARE_TARGET.values())


def target_conflicts(family_id, source_ids):
    if family_id in HARDWARE_TARGET:
        return sorted((set(source_ids) & PRIMARY_HARDWARE_MANUALS) - {HARDWARE_TARGET[family_id]})
    if family_id in ('P03', 'S04'):
        return sorted(set(source_ids) & {'postgresql-11-continuous-archiving'})
    return []


def collect(config, package, output):
    import chromadb
    from chromadb.config import Settings

    data = load_inputs(config)
    run = Path(config['run'])
    historical = read(run / 'run-metadata.json')
    preflight = read(package / 'preflight/preflight.json')
    inventory = read(package / 'preflight/inventory.json')
    execution = read(package / 'embeddings/execution.json')
    if (execution['workload_sha256'] != WORKLOAD_SHA
            or sha(run / 'vector-cache.sqlite3') != preflight['cache_sha256']
            or chromadb.__version__ != historical['chroma_version']):
        raise ValueError('Frozen workload, cache, or Chroma version changed')
    pending = read(package / 'preflight/pending-embedding-inputs.json')
    banned, rechecked_sha = restriction_map(config, data)
    if rechecked_sha != preflight['restrictions_sha256']:
        raise ValueError('Restriction map changed')
    vector_uri = (package / 'embeddings/vectors.sqlite3').resolve().as_uri() + '?mode=ro&immutable=1'
    with closing(sqlite3.connect(vector_uri, uri=True)) as saved:
        values = {key: np.frombuffer(blob, dtype=np.float32) for key, blob in
                  saved.execute('select hash,vector from vectors')}
        batches = dict(saved.execute("select arm,count(*) from batches where status='completed' group by arm"))
        if (batches != REQUESTS or saved.execute('select count(*) from batches').fetchone()[0] != sum(REQUESTS.values())
                or set(values) != {row['sha256'] for row in pending}):
            raise ValueError('Embedding requests or hash set differ from approval')
    if any(v.shape != (1024,) or not np.isfinite(v).all() or abs(np.linalg.norm(v) - 1) > 1e-4
           for v in values.values()):
        raise ValueError('Invalid embedding cache record')

    output.mkdir(parents=True, exist_ok=False)
    cache = FrozenVectors(run / 'vector-cache.sqlite3', historical)
    results, measurements = [], {}
    try:
        queries = {qid: cache.get(q['text']).tolist() for qid, q in data['questions'].items()}
        for arm in ARMS:
            rows = {row['id']: row for row in inventory['arms'][arm]}
            expected_keys = {row['sha256'] for row in pending if row['arms'] == [arm]}
            if {r['embedding_text_sha256'] for r in rows.values() if not r['cache_hit']} != expected_keys:
                raise ValueError('Variant input set changed')
            chunks = []
            for cid, row in rows.items():
                if intersects(row['ranges'], banned[row['source_id']]):
                    raise ValueError('Restricted range reached experimental index')
                vector = cache.get(row['text']) if row['cache_hit'] else values[row['embedding_text_sha256']]
                chunks.append(DocumentChunk(chunk_id=cid, text=row['text'], source='global',
                                            file_path=row['file_path'], metadata=row['metadata'],
                                            embedding=vector.tolist()))
            directory = output / f'{arm}-index'
            client = chromadb.PersistentClient(path=str(directory), settings=Settings(anonymized_telemetry=False))
            with patch('laew.rag.vector_store._build_chroma_client', return_value=client):
                tick = perf_counter()
                store = ChromaVectorStore(host='127.0.0.1', port=1, collection_name=f'final-rag-{arm}',
                                          source='global', embedding_model_id=execution['server']['compatibility'][
                                              'current_catalog_identity'])
                for start in range(0, len(chunks), 128):
                    store.add_chunks(chunks[start:start + 128])
                build_seconds = perf_counter() - tick
            if store.count() != len(rows):
                raise ValueError('Experimental index count differs')
            matrix = np.array([c.embedding for c in chunks], dtype=np.float64)
            matrix /= np.linalg.norm(matrix, axis=1)[:, None]
            chunk_position = {c.chunk_id: i for i, c in enumerate(chunks)}
            store.search(next(iter(queries.values())), top_k=10, source_filter='global')
            searches, renders = [], []
            for qid, query in queries.items():
                tick = perf_counter()
                raw = store.search(query, top_k=10, source_filter='global')
                searches.append((perf_counter() - tick) * 1000)
                tick = perf_counter()
                selections, enclosing = select_scopes({'global': [Candidate(c, s) for c, s in raw]},
                                                       SelectionConfig(policy='ranked_fill', budget=1000), 8000)
                selected = selections['global']
                renders.append((perf_counter() - tick) * 1000)
                if len(raw) != 10 or selected.estimated_tokens > 1000 or math.ceil(len(enclosing) / 4) > 8000:
                    raise ValueError('K10 or context budget differs')
                query_vector = np.asarray(query, dtype=np.float64)
                exact = matrix @ (query_vector / np.linalg.norm(query_vector))
                native = np.array([chunk_position[c.chunk_id] for c, _ in raw])
                exact_order = np.argsort(-exact, kind='stable')[:10]
                max_error = max(abs(exact[i] - cosine) for i, (_, cosine) in zip(native, raw))
                if max_error > 2e-6:
                    raise ValueError('Native cosine calculation differs')

                def encode(chunk, cosine):
                    row = rows[chunk.chunk_id]
                    sid = row['source_id']
                    if (not row['text'].startswith(chunk.text) or chunk.metadata != row['metadata']
                            or chunk.file_path != row['file_path']):
                        raise ValueError('Index returned unresolved attribution or text')
                    if arm == 'contextual':
                        original_sid, mapping, text = data['sources']['structure-v2'][chunk.chunk_id]
                        if original_sid != sid:
                            raise ValueError('Contextual source changed')
                        ranges = payload_segments(chunk, mapping, text)
                    else:
                        [(start, end)] = row['ranges']
                        if data['texts'][sid][start:end] != row['text']:
                            raise ValueError('Adaptive offsets changed')
                        ranges = [[start, start + len(chunk.text)]]
                    if intersects(ranges, banned[sid]):
                        raise ValueError('Restricted range escaped index')
                    return dict(id=chunk.chunk_id, source_id=sid, cosine=cosine, source_ranges=ranges,
                                source_sha256=data['units'][sid]['normalized_sha256'],
                                revision=data['units'][sid]['revision'])

                results.append(dict(arm=arm, question_id=qid, raw=[encode(c, s) for c, s in raw],
                                    eligible=[encode(c, s) for c, s in raw if s >= .3],
                                    selected=[encode(c, s) for c, s in selected.chunks],
                                    context_sha256=digest(enclosing), rendered_tokens=selected.estimated_tokens,
                                    clipped=sum(len(c.text) != len(rows[c.chunk_id]['text']) for c, _ in selected.chunks),
                                    exact_top10_agrees=set(native) == set(exact_order),
                                    non_tie_rank_gap=max(0., float(exact[exact_order[-1]] - min(exact[native]))),
                                    max_cosine_error=float(max_error)))
            measurements[arm] = dict(index_bytes=sum(f.stat().st_size for f in directory.rglob('*') if f.is_file()),
                                     build_seconds=build_seconds, search_ms=distribution(searches),
                                     render_ms=distribution(renders), searches=len(searches))
    finally:
        cache.close()
    write(output / 'traces.json', results)
    write(output / 'measurements.json', measurements)
    seal(output, ['traces.json', 'measurements.json'], code_sha256=sha(__file__))


def audit(config, package, collection, output):
    data = load_inputs(config, scoring=True)
    banned, _ = restriction_map(config, data)
    controls = read(package / 'controls/safe-control-traces.json')
    historical = read(package / 'audit/historical-and-safe-per-question.json')
    traces = read(collection / 'traces.json')
    all_traces = {(row['arm'], row['question_id']): row for row in controls + traces}
    if len(all_traces) != 240:
        raise ValueError('Expected 60 questions per arm')
    baseline_scores = {(row['arm'], row['question_id']): row for row in historical}
    summaries = defaultdict(Counter)
    pairs, family_outcomes = [], defaultdict(Counter)
    for arm in ('B', 'C', *ARMS):
        summary = summaries[arm]
        for qid, question in data['questions'].items():
            trace = all_traces[arm, qid]
            family_id = question['family_id']
            family = data['rubric'][family_id]
            reqs = {r['id']: r for r in family['requirements']}
            outcomes = {}
            conflicts = {}
            for stage in STAGES:
                coverage = coverage_of(trace[stage])
                if any(intersects(ranges, banned[sid]) for sid, ranges in coverage.items()):
                    raise ValueError('Restricted source coverage in evaluation')
                scored = score_evidence(family, data['atoms'], coverage, data['texts'])
                outcomes[stage] = scored
                conflicts[stage] = target_conflicts(family_id, coverage)
                summary[f'{stage}_complete'] += scored['complete'] is True
                summary[f'{stage}_target_conflict_questions'] += bool(conflicts[stage])
                if arm in ('B', 'C') and scored != baseline_scores[arm, qid]['safe_control'][stage]:
                    raise ValueError('Matched control scores changed')
            family_outcomes[family_id][arm] += outcomes['selected']['complete'] is True
            selected = outcomes['selected']
            if selected['complete'] is not None:
                best = next(m for m in selected['methods'] if m['method'] == selected['chosen_method'])
                for key, relevant in [('critical', lambda r: r['safety_critical']),
                                      ('conditional', lambda r: r['category'] == 'conditional')]:
                    active = {rid: best['status'][rid] for rid in best['status'] if relevant(reqs[rid])}
                    summary[f'{key}_active_on_chosen_method'] += len(active)
                    summary[f'{key}_covered_on_chosen_method'] += sum(s == 'minimum-sufficient' for s in active.values())
            pairs.append(dict(arm=arm, question_id=qid, family_id=family_id,
                              language=question['language'], outcomes=outcomes,
                              selected_source_ids=list(dict.fromkeys(c['source_id'] for c in trace['selected'])),
                              selected_tokens=trace['rendered_tokens'], target_conflicts=conflicts))
    by_key = {(row['arm'], row['question_id']): row for row in pairs}
    deltas = {}
    for arm in ARMS:
        for control in ('B', 'C'):
            changes = {}
            for stage in STAGES:
                changes[stage] = dict(gains=[], losses=[])
                for qid in data['questions']:
                    base = by_key[control, qid]['outcomes'][stage]['complete']
                    new = by_key[arm, qid]['outcomes'][stage]['complete']
                    if base is not None and new is not None and base != new:
                        changes[stage]['gains' if new else 'losses'].append(qid)
            deltas[f'{arm}/{control}'] = dict(**changes, majority_gains=[], majority_losses=[],
                                             selected_requirement_changes=[], selected_target_conflict_changes=[])
            delta = deltas[f'{arm}/{control}']
            for qid, question in data['questions'].items():
                before, after = (by_key[key, qid] for key in (control, arm))
                old_conflicts = set(before['target_conflicts']['selected'])
                new_conflicts = set(after['target_conflicts']['selected'])
                if old_conflicts != new_conflicts:
                    delta['selected_target_conflict_changes'].append(dict(
                        question_id=qid, added=sorted(new_conflicts - old_conflicts),
                        removed=sorted(old_conflicts - new_conflicts)))
                family = data['rubric'][question['family_id']]
                requirements = {r['id']: r for r in family['requirements']}
                prior_methods = before['outcomes']['selected']['methods']
                new_methods = after['outcomes']['selected']['methods']
                for prior, new in zip(prior_methods, new_methods, strict=True):
                    if prior['method'] != new['method'] or prior['status'].keys() != new['status'].keys():
                        raise ValueError('Same rubric produced different method or applicability')
                    for rid, status in prior['status'].items():
                        changed = new['status'][rid]
                        if status != changed:
                            req = requirements[rid]
                            delta['selected_requirement_changes'].append(dict(
                                question_id=qid, method=prior['method'], id=rid, category=req['category'],
                                safety_critical=req['safety_critical'], before=status, after=changed))
            for fid, counts in family_outcomes.items():
                if (counts[arm] >= 2) != (counts[control] >= 2):
                    delta['majority_gains' if counts[arm] >= 2 else 'majority_losses'].append(fid)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'per-question.json', pairs)
    write(output / 'summary.json', dict(arms=summaries, deltas=deltas, family_complete_variants=family_outcomes,
                                       restrictions_exposed=0, question_variants=60, answerable_variants=48,
                                       dependent_families=20, answerable_families=16))
    seal(output, ['per-question.json', 'summary.json'], code_sha256=sha(__file__))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['collect', 'audit'])
    parser.add_argument('config', type=Path)
    parser.add_argument('package', type=Path)
    parser.add_argument('collection', type=Path)
    parser.add_argument('--collection-sha')
    parser.add_argument('--audit-output', type=Path)
    args = parser.parse_args()
    with offline():
        receipt = read(args.package / 'verification.json')
        for folder, receipt_entry in zip(('preflight', 'controls', 'audit'), receipt['phase_manifests']):
            verify_manifest(args.package / folder, 'integrity.json', receipt_entry['sha256'])
        if args.mode == 'collect':
            manifest = args.package / 'embeddings/integrity.json'
            verify_manifest(manifest.parent, manifest.name, sha(manifest))
            collect(read(args.config), args.package, args.collection)
        else:
            verify_manifest(args.collection, 'integrity.json', args.collection_sha)
            audit(read(args.config), args.package, args.collection, args.audit_output)
