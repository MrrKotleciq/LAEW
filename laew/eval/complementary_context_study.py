"""Offline development diagnostics for frozen context selection (never runtime).

Selection and rubric scoring are separate CLI invocations. Large source-bearing
outputs belong in a fresh external directory. No index or model is constructed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import socket
import statistics
import sys
import time
from unittest.mock import patch

from laew.eval.compact_delivery_replay import context_metrics
from laew.eval.real_world_retrieval import coverage_of, payload_segments, union
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.knowledge_base import KnowledgeBase


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_manifest(root, name, expected):
    root = Path(root).resolve()
    if sha(root / name) != expected:
        raise ValueError(f'Manifest changed: {root / name}')
    entries = read(root / name)['files']
    for entry in entries:
        path = (root / entry['path']).resolve()
        if not path.is_relative_to(root) or sha(path) != entry['sha256']:
            raise ValueError(f'Manifest member changed: {path}')
        if 'bytes' in entry and path.stat().st_size != entry['bytes']:
            raise ValueError(f'Manifest member size changed: {path}')
    return dict(root=str(root), manifest=name, sha256=expected, members=len(entries))


@contextmanager
def offline():
    def denied(*args, **kwargs):
        raise RuntimeError('Network forbidden in frozen context study')
    with patch.object(socket.socket, 'connect', denied), patch.object(socket, 'create_connection', denied):
        yield


def load_inputs(config, *, scoring=False):
    """Verify and reconstruct all native candidates; no embeddings/index access."""
    corpus, run = Path(config['corpus']), Path(config['run'])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/corpus'))
    from prepare_real_world_pilot import verify_corpus
    receipts = [verify_corpus(corpus)]
    receipts.append(verify_manifest(run.parent, 'artifact-integrity.json', config['retrieval_sha']))
    receipts.append(verify_manifest(run, 'trace-integrity.json', config['trace_sha']))
    questions_dir = Path(config['questions'])
    receipts.append(verify_manifest(questions_dir, 'input-integrity.json', config['questions_sha']))
    questions = read(questions_dir / 'questions-only.json')
    if len(questions) != 60 or any(set(q) != {'id', 'family_id', 'language', 'text', 'split'} for q in questions):
        raise ValueError('Expected exactly 60 sanitized development questions')
    traces = read(run / 'retrieval-traces.json')
    if len(traces) != 180:
        raise ValueError('Expected 180 historical rows')
    units = {u['id']: u for u in read(corpus / 'corpus/source-manifest.json')['source_units']}
    texts = {sid: (corpus / 'corpus' / u['normalized_path']).read_text(encoding='utf-8')
             for sid, u in units.items()}
    chunks, sources = {}, {'legacy': {}, 'structure-v2': {}}
    for strategy in sources:
        loader = object.__new__(KnowledgeBase)
        loader.chunk_size, loader.chunk_overlap, loader.chunking_strategy = 1000, 200, strategy
        for sid, unit in units.items():
            path = corpus / 'corpus' / unit['normalized_path']
            generated = loader._load_file(path, 'global', path.parent, content=texts[sid], embed=False)
            records = read(corpus / f'corpus/chunk-maps/{sid}-{strategy}.json')['records']
            if len(generated) != len(records):
                raise ValueError('Frozen chunk count differs')
            for chunk, record in zip(generated, records):
                if hashlib.sha256(chunk.text.encode()).hexdigest() != record['text_sha256']:
                    raise ValueError('Frozen chunk serialization differs')
                chunks[strategy, chunk.chunk_id] = chunk
                sources[strategy][chunk.chunk_id] = (sid, record, texts[sid])
    pools, metrics = {}, []
    for trace in traces:
        strategy = trace['strategy']
        candidates = []
        for raw in trace['raw']:
            chunk = chunks[strategy, raw['id']]
            sid, mapping, text = sources[strategy][raw['id']]
            ranges = payload_segments(chunk, mapping, text, len(chunk.text))
            if (raw['text'] != chunk.text or raw['source_id'] != sid or raw['source_ranges'] != [list(r) for r in ranges]
                    or raw['source_sha256'] != units[sid]['normalized_sha256']):
                raise ValueError('Native candidate text/identity/ranges differ')
            candidates.append(Candidate(chunk, raw['cosine']))
        config_select = SelectionConfig(policy=trace['policy'], budget=trace['budget'])
        result, enclosing = select_scopes({'global': candidates}, config_select, 8000)
        result = result['global']
        if (result.context != trace['context'] or enclosing != trace['enclosing_context']
                or [(c.chunk_id, c.text) for c, _ in result.chunks] != [(c['id'], c['text']) for c in trace['selected']]):
            raise ValueError('Historical context replay differs')
        key = trace['question_id'], trace['arm']
        pools[key] = candidates
        metrics.append(dict(question_id=key[0], arm=key[1], **context_metrics(result, enclosing, sources[strategy])))
    result = dict(traces=traces, questions={q['id']: q for q in questions}, units=units, texts=texts,
                  chunks=chunks, sources=sources, pools=pools, metrics=metrics, receipts=receipts)
    if scoring:
        # This branch is never used by the selection invocation.
        from laew.eval.scoring_calibration import validate_atoms
        rubric_dir = Path(config['rubric'])
        receipts.append(verify_manifest(rubric_dir, 'rubric-manifest-v2.1.json', config['rubric_sha']))
        receipts.append(verify_manifest(rubric_dir, 'artifact-integrity.json', config['calibration_sha']))
        result['rubric'] = read(rubric_dir / 'rubric-v2.1.json')['families']
        result['atoms'] = read(rubric_dir / 'source-atoms-v2.1.json')
        validate_atoms(result['atoms'], texts, units)
        result['historical'] = {(r['question_id'], r['arm']): r for r in read(rubric_dir / 'calibrated-per-question-v2.1.json')}
        result['families'] = {}
        for entry in config['datasets']:
            folder = Path(entry['path'])
            receipts.append(verify_manifest(folder, 'dataset-integrity.json', entry['sha256']))
            result['families'].update({f['id']: f for f in read(folder / 'families.json')})
    return result


def support(family, atoms, coverage, texts):
    from laew.eval.scoring_calibration import proof_present
    return {r['id']: proof_present(r, atoms, coverage, texts) for r in family['requirements']}


def diagnose(config, output):
    data = load_inputs(config, scoring=True)
    from laew.eval.scoring_calibration import score_evidence
    rows = []
    counts = Counter()
    for trace, metrics in zip(data['traces'], data['metrics']):
        family = data['rubric'][trace['family_id']]
        stages = {stage: score_evidence(family, data['atoms'], coverage_of(trace[stage]), data['texts'])
                  for stage in ('raw', 'eligible', 'selected')}
        old = data['historical'][trace['question_id'], trace['arm']]
        if any(stages[s] != old[s]['calibrated'] for s in stages):
            raise ValueError('Repaired evidence scorer differs from historical v2.1')
        proofs = {stage: support(family, data['atoms'], coverage_of(trace[stage]), data['texts']) for stage in stages}
        lost = [rid for rid in proofs['raw'] if proofs['raw'][rid] and not proofs['selected'][rid]]
        absent = [rid for rid in proofs['raw'] if not proofs['raw'][rid]]
        if family['positive_recall_applicable']:
            counts[trace['arm'] + '/lost'] += len(lost)
            counts[trace['arm'] + '/absent'] += len(absent)
        rows.append(dict(question_id=trace['question_id'], arm=trace['arm'], family_id=trace['family_id'],
                         stages=stages, support=proofs, present_in_k10_lost=lost,
                         registered_support_absent=absent, metrics=metrics))
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'root-cause-rows.json', rows)
    write(output / 'input-integrity.json', data['receipts'])
    write(output / 'summary.json', dict(counts=counts, historical_stage_scores_reproduced=540,
          historical_contexts_reproduced=180, network_calls=0,
          caveat='Absent registered proof is not a semantic irrelevance judgment; all requirements include optional/conditional branches.'))
    print(json.dumps(dict(output=str(output), counts=counts), indent=2))


def seal(output, names, **provenance):
    write(output / 'integrity.json', dict(files=[dict(path=name, sha256=sha(output / name)) for name in names],
                                        **provenance))


def collect(config, output, split, version):
    from laew.eval import complementary_context_selection as selector
    if output.exists():
        raise ValueError('Fresh output required')
    data = load_inputs(config)  # Does not read rubric, dataset labels or answers.
    rows, measurements, timings = [], [], []
    for trace in data['traces']:
        if trace['arm'] not in ('B', 'C') or (split != 'all' and trace['split'] != split):
            continue
        pool = data['pools'][trace['question_id'], trace['arm']]
        query = data['questions'][trace['question_id']]['text']
        cfg = SelectionConfig(policy='ranked_fill', budget=1000)
        if (trace['k'], trace['budget'], trace['policy']) != (10, 1000, 'ranked_fill'):
            raise ValueError('Baseline settings differ')
        started = time.perf_counter()
        results, enclosing = selector.select_complementary_scopes({'global': pool}, cfg, query, version=version)
        elapsed = (time.perf_counter() - started) * 1000
        result = results['global']
        sources = data['sources'][trace['strategy']]
        selected = []
        for chunk, score in result.chunks:
            sid, mapping, text = sources[chunk.chunk_id]
            ranges = payload_segments(chunk, mapping, text, len(chunk.text))
            selected.append(dict(id=chunk.chunk_id, source_id=sid,
                source_sha256=data['units'][sid]['normalized_sha256'], cosine=score, text=chunk.text,
                source_ranges=ranges))
        variant = trace['arm'] + '-' + version
        row = {k: trace[k] for k in ('question_id', 'family_id', 'language', 'split', 'strategy', 'k', 'budget')}
        row.update(arm=variant, baseline_arm=trace['arm'], raw=trace['raw'], eligible=trace['eligible'],
                   selected=selected, context=result.context, enclosing_context=enclosing,
                   estimated_tokens=result.estimated_tokens, selection_ms=elapsed, decisions=result.decisions)
        if result.estimated_tokens > 1000 or (len(enclosing) + 3) // 4 > 8000:
            raise ValueError('Budget exceeded')
        rows.append(row)
        measurements.append(dict(question_id=trace['question_id'], arm=variant,
                                  **context_metrics(result, enclosing, sources)))
        samples = {'baseline': [], 'experimental': []}
        for repeat in range(10):
            for name in (('baseline', 'experimental') if repeat % 2 == 0 else ('experimental', 'baseline')):
                started = time.perf_counter()
                if name == 'baseline':
                    select_scopes({'global': pool}, cfg)
                else:
                    selector.select_complementary_scopes({'global': pool}, cfg, query, version=version)
                samples[name].append((time.perf_counter() - started) * 1000)
        timings.append(dict(question_id=trace['question_id'], arm=variant, samples_ms=samples))
    output.mkdir(parents=True)
    write(output / 'selection-traces.json', rows)
    write(output / 'metrics.json', measurements)
    write(output / 'timing.json', timings)
    write(output / 'input-integrity.json', data['receipts'])
    write(output / 'provenance.json', dict(version=version, settings=selector.SETTINGS,
        selector_sha256=sha(selector.__file__), replay_sha256=sha(__file__),
        split=split, rows=len(rows), labels_read=False, rubric_read=False, saved_answers_read=False,
        source_loader_embed=False, historical_contexts_reproduced=180,
        retrieval_calls=0, embedding_calls=0, generation_calls=0, index_writes=0,
        scope='All 60 questions are development data; no independent validation',
        latency='Selection+render only; 10 alternating-order warm repeats per question and arm; no loading/retrieval'))
    seal(output, ['selection-traces.json', 'metrics.json', 'timing.json', 'input-integrity.json', 'provenance.json'])
    print(json.dumps(dict(output=str(output), rows=len(rows), version=version)))


def evaluate(config, delivery, output):
    from laew.eval.complementary_context_selection import shingles
    from laew.eval.scoring_calibration import score_evidence
    from laew.eval.real_world_analysis import distribution
    if output.exists():
        raise ValueError('Fresh output required')
    verify_manifest(delivery, 'integrity.json', sha(delivery / 'integrity.json'))
    data = load_inputs(config, scoring=True)
    experiment = read(delivery / 'selection-traces.json')
    metrics = {(m['question_id'], m['arm']): m for m in data['metrics'] + read(delivery / 'metrics.json')}
    risks = read(Path(config['corpus']) / 'review/r3d/inherited-unresolved-risk-register.json')
    restricted = read(Path(config['corpus']) / 'review/r3d/restricted-regions.json')['regions']
    historical = {(r['question_id'], r['arm']): r for r in data['traces']}
    rows = []
    for trace in data['traces'] + experiment:
        qid, fid, arm = trace['question_id'], trace['family_id'], trace['arm']
        family = data['rubric'][fid]
        selected_cov = coverage_of(trace['selected'])
        stages = {stage: score_evidence(family, data['atoms'], coverage_of(trace[stage]), data['texts'])
                  for stage in ('raw', 'selected')}
        if arm in ('A', 'B', 'C') and any(stages[s] != data['historical'][qid, arm][s]['calibrated'] for s in stages):
            raise ValueError('Historical calibrated score differs')
        proofs = {stage: support(family, data['atoms'], coverage_of(trace[stage]), data['texts']) for stage in stages}
        # A fixed all-branch ledger prevents choosing an easier evidence method
        # from hiding a lost conditional safeguard. It does not infer actual advice.
        critical = [r['id'] for r in family['requirements'] if r['safety_critical'] and not r.get('contextual')]
        conditions = [r['id'] for r in family['requirements']
                      if (r.get('when') or r['safety_critical']) and not r.get('contextual')]
        relevant_sources = {data['atoms'][aid]['source_id'] for r in family['requirements']
                            for alt in r['proofs'] for aid in alt}
        source_groups = sorted({data['units'][sid]['family'] for sid in relevant_sources}) or ['unavailable']
        shingle_sets = [shingles(c['text']) for c in trace['selected']]
        shingle_count = sum(len(s) for s in shingle_sets)
        duplicate_shingles = shingle_count - len(set().union(*shingle_sets)) if shingle_sets else 0
        restricted_exposure = [dict(source_id=r['source_id'], page=r['pdf_page']) for r in restricted
            if any(max(a, s['start']) < min(z, s['end']) for a, z in selected_cov.get(r['source_id'], [])
                   for s in r['component_ranges'] + r['related_context_ranges'])]
        open_exposure = [dict(source_id=r['source_id'], page=r['page'], severity=r['original_severity']) for r in risks
            if any(max(a, r['start']) < min(z, r['end']) for a, z in selected_cov.get(r['source_id'], []))]
        baseline = historical[qid, trace.get('baseline_arm', arm)]
        # Experimental text/ranges must be an unchanged whole native candidate
        # or a verbatim historical clipped fallback, never source-enriched text.
        native = {c['id']: c for c in baseline['raw']}
        clipped = {c['id']: c for c in baseline['selected']}
        for c in trace['selected']:
            if c != native.get(c['id']) and c != clipped.get(c['id']):
                raise ValueError('Selected text or attribution escaped frozen native candidates')
        row = dict(question_id=qid, family_id=fid, arm=arm, split=trace['split'], language=trace['language'],
                   category=data['families'][fid]['category'], source_groups=source_groups,
                   stages=stages, support=proofs, critical_ids=critical, condition_ids=conditions,
                   critical_hit=[rid for rid in critical if proofs['selected'][rid]],
                   condition_hit=[rid for rid in conditions if proofs['selected'][rid]],
                   present_in_k10_lost=[rid for rid in proofs['raw'] if proofs['raw'][rid] and not proofs['selected'][rid]],
                   metrics=metrics[qid, arm], redundant_shingles=duplicate_shingles,
                   shingle_instances=shingle_count, restricted_exposure=restricted_exposure,
                   open_page_risk_exposure=open_exposure)
        rows.append(row)
    by = {(r['question_id'], r['arm']): r for r in rows}
    paired = []
    for trace in experiment:
        before, after = by[trace['question_id'], trace['baseline_arm']], by[trace['question_id'], trace['arm']]
        bs, es = before['support']['selected'], after['support']['selected']
        gains = [rid for rid in bs if not bs[rid] and es[rid]]
        losses = [rid for rid in bs if bs[rid] and not es[rid]]
        paired.append(dict(question_id=trace['question_id'], family_id=trace['family_id'],
            baseline=trace['baseline_arm'], experimental=trace['arm'],
            coverage_before=before['stages']['selected']['positive_recall'],
            coverage_after=after['stages']['selected']['positive_recall'],
            complete_before=before['stages']['selected']['complete'], complete_after=after['stages']['selected']['complete'],
            requirement_gains=gains, requirement_losses=losses,
            critical_gains=[rid for rid in gains if rid in after['critical_ids']],
            critical_losses=[rid for rid in losses if rid in after['critical_ids']],
            condition_gains=[rid for rid in gains if rid in after['condition_ids']],
            condition_losses=[rid for rid in losses if rid in after['condition_ids']],
            token_delta=after['metrics']['estimated_tokens']-before['metrics']['estimated_tokens']))

    def aggregate(items):
        answerable = [r for r in items if r['stages']['selected']['positive_recall'] is not None]
        return dict(questions=len(items), answerable=len(answerable),
            minimum_coverage=statistics.mean(r['stages']['selected']['positive_recall'] for r in answerable) if answerable else None,
            complete=sum(r['stages']['selected']['complete'] for r in answerable),
            raw_complete=sum(r['stages']['raw']['complete'] for r in answerable),
            critical_hit=sum(len(r['critical_hit']) for r in items), critical_total=sum(len(r['critical_ids']) for r in items),
            conditions_hit=sum(len(r['condition_hit']) for r in items), conditions_total=sum(len(r['condition_ids']) for r in items),
            lost_k10_support=sum(len(r['present_in_k10_lost']) for r in items),
            tokens=distribution([r['metrics']['estimated_tokens'] for r in items]),
            sources_mean=statistics.mean(r['metrics']['sources'] for r in items),
            sections_mean=statistics.mean(r['metrics']['sections'] for r in items),
            attribution_chars_mean=statistics.mean(r['metrics']['attribution_chars'] for r in items),
            repeated_source_chars_mean=statistics.mean(r['metrics']['repeated_source_chars'] for r in items),
            redundant_shingle_fraction=sum(r['redundant_shingles'] for r in items)/max(1,sum(r['shingle_instances'] for r in items)),
            restricted_exposure_questions=sum(bool(r['restricted_exposure']) for r in items),
            open_risk_questions=sum(bool(r['open_page_risk_exposure']) for r in items))
    grouped = {}
    for arm in sorted({r['arm'] for r in rows}):
        rr = [r for r in rows if r['arm'] == arm]
        grouped[arm + '/all'] = aggregate(rr)
        strata = [('split', s) for s in ('pilot', 'sealed')] + [('language', s) for s in ('en', 'pl', 'de')]
        strata += [('category', s) for s in sorted({r['category'] for r in rr})]
        strata += [('source_group', s) for s in ('prusa', 'progit', 'postgresql', 'unavailable')]
        for dimension, value in strata:
            subset = [r for r in rr if (value in r['source_groups'] if dimension == 'source_group' else r[dimension] == value)]
            if subset:
                grouped[f'{arm}/{dimension}/{value}'] = aggregate(subset)
    timing = read(delivery / 'timing.json')
    latency = {arm: {kind: distribution([v for r in timing if r['arm'] == arm for v in r['samples_ms'][kind]])
                     for kind in ('baseline', 'experimental')} for arm in sorted({r['arm'] for r in timing})}
    output.mkdir(parents=True)
    write(output / 'per-question.json', rows)
    write(output / 'paired.json', paired)
    write(output / 'summary.json', dict(grouped=grouped, latency=latency,
        status='development-diagnostics-not-independent-validation',
        caveat='Mechanical source-proof coverage under provisional agent-authored v2.1; lexical redundancy is not semantic equivalence. All conditional branches reported, not inferred advice applicability.'))
    write(output / 'provenance.json', dict(delivery_integrity_sha256=sha(delivery/'integrity.json'),
          scorer_sha256=sha(sys.modules[score_evidence.__module__].__file__), rubric_sha256=config['rubric_sha'],
          labels_modified=False, answers_read=False, network_calls=0))
    seal(output, ['per-question.json', 'paired.json', 'summary.json', 'provenance.json'])
    print(json.dumps(dict(output=str(output), summary={k: v for k, v in grouped.items() if k.endswith('/all')},
         losses=[p for p in paired if p['requirement_losses']]), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['diagnose', 'collect', 'score'])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--delivery', type=Path)
    parser.add_argument('--split', choices=['pilot', 'sealed', 'all'], default='pilot')
    parser.add_argument('--version', default='complementary-pack-v2')
    args = parser.parse_args()
    with offline():
        config = read(args.config)
        if args.mode == 'diagnose':
            diagnose(config, args.output)
        elif args.mode == 'collect':
            collect(config, args.output, args.split, args.version)
        else:
            if args.delivery is None:
                parser.error('--delivery is required for score')
            evaluate(config, args.delivery, args.output)


if __name__ == '__main__':
    main()
