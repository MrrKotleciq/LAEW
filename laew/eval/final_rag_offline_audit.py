"""Rebuild cache-only controls and audit the frozen preflight using rubric v2.1."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from laew.eval.complementary_context_study import load_inputs, offline, read, seal, sha, verify_manifest, write
from laew.eval.final_rag_preflight import digest, distribution, intersects, restriction_map
from laew.eval.real_world_retrieval import coverage_of, payload_segments
from laew.eval.retrieval_budget_diagnostics import FrozenVectors, oracle_diagnostic, subtract_regions
from laew.eval.scoring_calibration import score_evidence
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.vector_store import ChromaVectorStore


def collect(config, preflight, inventory, output):
    import chromadb
    from chromadb.config import Settings

    data = load_inputs(config)
    run = Path(config['run'])
    meta = read(run / 'run-metadata.json')
    if chromadb.__version__ != meta['chroma_version']:
        raise ValueError('Historical Chroma version differs')
    traces = {(t['arm'], t['question_id']): t for t in data['traces']}
    if sha(run / 'vector-cache.sqlite3') != preflight['cache_sha256']:
        raise ValueError('Cache differs from preflight')
    cache = FrozenVectors(run / 'vector-cache.sqlite3', meta)
    output.mkdir(parents=True, exist_ok=False)
    results, measurements = [], {}
    try:
        queries = {qid: cache.get(q['text']).tolist() for qid, q in data['questions'].items()}
        for arm, strategy in [('B', 'legacy'), ('C', 'structure-v2')]:
            allowed = {row['id']: row for row in inventory['arms'][arm]}
            chunks = [replace(data['chunks'][strategy, cid], embedding=cache.get(row['text']).tolist())
                      for cid, row in allowed.items()]
            directory = output / f'{arm}-index'
            client = chromadb.PersistentClient(path=str(directory), settings=Settings(anonymized_telemetry=False))
            with patch('laew.rag.vector_store._build_chroma_client', return_value=client):
                tick = perf_counter()
                store = ChromaVectorStore(host='127.0.0.1', port=1,
                                          collection_name=f'final-rag-{strategy}',
                                          source='global', embedding_model_id=cache.identity)
                for i in range(0, len(chunks), 128):
                    store.add_chunks(chunks[i:i + 128])
                build_seconds = perf_counter() - tick
            if store.count() != len(allowed):
                raise ValueError('Unexpected safe index record count')
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

                def encode(chunk, cosine):
                    sid, mapping, text = data['sources'][strategy][chunk.chunk_id]
                    row = allowed[chunk.chunk_id]
                    if row['source_id'] != sid or not row['text'].startswith(chunk.text):
                        raise ValueError('Index returned unresolved attribution or text')
                    return dict(id=chunk.chunk_id, source_id=sid, cosine=cosine,
                                source_ranges=payload_segments(chunk, mapping, text))

                ids = [c.chunk_id for c, _ in raw]
                original = [c['id'] for c in traces[arm, qid]['raw']]
                results.append(dict(arm=arm, question_id=qid, raw=[encode(c, s) for c, s in raw],
                                    eligible=[encode(c, s) for c, s in raw if s >= .3],
                                    selected=[encode(c, s) for c, s in selected.chunks],
                                    context_sha256=digest(enclosing),
                                    rendered_tokens=selected.estimated_tokens,
                                    changed_order=ids != original, changed_membership=set(ids) != set(original)))
            measurements[arm] = dict(index_bytes=sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()),
                                     build_seconds=build_seconds, search_ms=distribution(searches),
                                     render_ms=distribution(renders), searches=len(searches))
    finally:
        cache.close()
    write(output / 'safe-control-traces.json', results)
    write(output / 'measurements.json', measurements)
    seal(output, ['safe-control-traces.json', 'measurements.json'], code_sha256=sha(__file__))


def audit(config, inventory, collected, output):
    data = load_inputs(config, scoring=True)
    banned, _ = restriction_map(config, data)
    regions = read(Path(config['corpus']) / 'review/r3d/restricted-regions.json')['regions']
    rubrics, atoms, texts = (data[key] for key in ('rubric', 'atoms', 'texts'))
    safe = {(t['arm'], t['question_id']): t for t in collected}
    ledger, totals, opportunities = [], Counter(), {}

    def exposure(candidates):
        return sorted({c['source_id'] for c in candidates if intersects(c['source_ranges'], banned[c['source_id']])})

    def score(family, candidates):
        return score_evidence(family, atoms, subtract_regions(coverage_of(candidates), regions), texts)

    for t in data['traces']:
        arm, qid = t['arm'], t['question_id']
        family = rubrics[t['family_id']]
        row = {k: t[k] for k in ('arm', 'question_id', 'family_id', 'language')}
        row['historical'], row['safe_control'] = {}, {}
        row['historical_restricted_sources'] = {}
        for stage in ('raw', 'eligible', 'selected'):
            base = score_evidence(family, atoms, coverage_of(t[stage]), texts)
            if base != data['historical'][qid, arm][stage]['calibrated']:
                raise ValueError('Historical rubric replay differs')
            row['historical'][stage] = base
            row['historical_restricted_sources'][stage] = exposure(t[stage])
            totals[f'{arm}/{stage}/historical_complete'] += base['complete'] is True
            totals[f'{arm}/{stage}/historical_restricted_rows'] += bool(exposure(t[stage]))
            if arm in ('B', 'C'):
                candidates = safe[arm, qid][stage]
                if exposure(candidates):
                    raise ValueError('Restricted range escaped safe control')
                new = score(family, candidates)
                row['safe_control'][stage] = new
                row['safe_control'][f'{stage}_changed_complete'] = (new['complete'] != base['complete'])
                totals[f'{arm}/{stage}/safe_complete'] += new['complete'] is True
        if arm in ('B', 'C'):
            for key in ('changed_order', 'changed_membership', 'rendered_tokens'):
                row['safe_control'][key] = safe[arm, qid][key]
            sids = list(dict.fromkeys(c['source_id'] for c in t['eligible']))[:2]
            ceiling = score(family, [dict(source_id=sid, source_ranges=[[0, len(texts[sid])]]) for sid in sids])
            row['top_two_historical_documents_complete'] = ceiling['complete']
            totals[f'{arm}/top_two_accessible_complete'] += ceiling['complete'] is True
        ledger.append(row)

    for arm in ('B', 'C', 'adaptive'):
        by_source = {}
        for chunk in inventory['arms'][arm]:
            sid = chunk['source_id']
            by_source.setdefault(sid, []).append(dict(chunk, source_ranges=chunk['ranges']))
        for fid, family in rubrics.items():
            if not family['positive_recall_applicable']:
                continue
            refs = {}
            for req in family['requirements']:
                for alternative in req['proofs']:
                    for aid in alternative:
                        atom = atoms[aid]
                        refs.setdefault(atom['source_id'], []).append((atom['start'], atom['end']))
            carriers = [chunk for sid, rr in refs.items() for chunk in by_source.get(sid, [])
                        if intersects(chunk['ranges'], rr)]
            entire = score(family, carriers)
            if len(carriers) <= 20:
                bound = oracle_diagnostic(family, atoms, carriers, texts,
                                          [c['rendered_chars'] for c in carriers], regions=regions)
                minimum = bound['min_complete_tokens']
                witness = [carriers[i]['id'] for i in bound['min_complete_indices']]
            else:
                minimum, witness = None, []
            opportunities.setdefault(fid, {})[arm] = dict(full_inventory=entire, proof_carriers=len(carriers),
                                                         budget_oracle_measured=len(carriers) <= 20,
                                                         minimum_complete_tokens=minimum, witness_ids=witness)
    write(output / 'historical-and-safe-per-question.json', ledger)
    write(output / 'full-inventory-per-family.json', opportunities)
    write(output / 'audit-summary.json', dict(replayed_scores=len(ledger) * 3, totals=dict(totals),
                                               input_receipts=data['receipts']))
    seal(output, ['historical-and-safe-per-question.json', 'full-inventory-per-family.json', 'audit-summary.json'],
         code_sha256=sha(__file__))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['collect', 'audit'])
    parser.add_argument('config', type=Path)
    parser.add_argument('preflight', type=Path)
    parser.add_argument('preflight_seal', help='SHA-256 of the preflight integrity manifest')
    parser.add_argument('controls', type=Path)
    parser.add_argument('--control-seal', help='Required for audit')
    parser.add_argument('--audit-output', type=Path)
    args = parser.parse_args()
    with offline():
        verify_manifest(args.preflight, 'integrity.json', args.preflight_seal)
        config = read(args.config)
        inventory = read(args.preflight / 'inventory.json')
        if args.mode == 'collect':
            collect(config, read(args.preflight / 'preflight.json'), inventory, args.controls)
        else:
            verify_manifest(args.controls, 'integrity.json', args.control_seal)
            args.audit_output.mkdir(parents=True, exist_ok=False)
            audit(config, inventory, read(args.controls / 'safe-control-traces.json'), args.audit_output)


if __name__ == '__main__':
    main()
