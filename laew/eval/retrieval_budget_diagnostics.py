"""Offline, reference-informed bottleneck diagnosis; NEVER a runtime selector.

retrieve reuses verified vectors and a disposable copy of the frozen index.
analyze uses curator labels for exact whole-chunk upper bounds. Neither mode
embeds, generates, judges, edits sources, or changes a production component.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import re
import shutil
import sqlite3
import statistics

import numpy as np

from laew.eval.complementary_context_study import (
    load_inputs, offline, read, seal, sha, support, verify_manifest, write,
)
from laew.eval.compact_delivery_replay import context_metrics
from laew.eval.real_world_retrieval import coverage_of, payload_segments, span_present, union
from laew.eval.scoring_calibration import active_requirements, score_evidence
from laew.rag.evidence_selection import Candidate, SEPARATOR, SelectionConfig, select_scopes
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import ChromaVectorStore


def encode(candidate, strategy, data):
    chunk = candidate.chunk
    sid, mapping, text = data['sources'][strategy][chunk.chunk_id]
    return dict(id=chunk.chunk_id, source_id=sid,
                source_sha256=data['units'][sid]['normalized_sha256'],
                cosine=candidate.cosine, text=chunk.text,
                source_ranges=payload_segments(chunk, mapping, text, len(chunk.text)))


class FrozenVectors:
    """Read-only, exact historical cache keys. A miss is a stop, never inference."""
    def __init__(self, path, metadata):
        self.connection = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
        self.identity = metadata['model_identity_sha256']
        identity = hashlib.sha256(json.dumps(metadata['model_catalog'], sort_keys=True).encode()).hexdigest()
        if identity != self.identity or metadata['dimensions'] != 1024:
            raise ValueError('Historical embedding identity/dimensions differ')
        self.keys = set()

    def get(self, text):
        key = hashlib.sha256((self.identity + '\0' + text).encode()).hexdigest()
        row = self.connection.execute('select vector from vectors where key=?', (key,)).fetchone()
        if row is None:
            raise RuntimeError('EMBEDDING STOP GATE: required verified vector is absent; no inference performed')
        vector = np.frombuffer(row[0], dtype=np.float32)
        if vector.shape != (1024,) or not np.isfinite(vector).all() or np.linalg.norm(vector) <= 0:
            raise ValueError('Invalid saved embedding')
        self.keys.add(key)
        return vector.copy()

    def close(self):
        self.connection.close()


def retrieve(config, output):
    """Replay native K10/K20 using the original cosine HNSW index, copied first."""
    if output.exists():
        raise ValueError('Fresh output required')
    data = load_inputs(config, scoring=False)
    run = Path(config['run'])
    metadata = read(run / 'run-metadata.json')
    cache = FrozenVectors(run / 'vector-cache.sqlite3', metadata)
    # Resolve ALL vectors before importing/opening a vector client. No fallback.
    vectors = {key: cache.get(chunk.text) for key, chunk in data['chunks'].items()}
    queries = {qid: cache.get(q['text']) for qid, q in data['questions'].items()}
    unique_vectors = len(cache.keys)
    cache.close()
    output.mkdir(parents=True)
    copied = output / 'copied-index'
    shutil.copytree(run / 'chroma', copied)
    # Check copy bytes before opening: Chroma may mutate its disposable clone.
    original_files = [p for p in (run / 'chroma').rglob('*') if p.is_file()]
    if any(sha(p) != sha(copied / p.relative_to(run / 'chroma')) for p in original_files):
        raise ValueError('Index copy differs before use')
    import chromadb
    from chromadb.config import Settings
    if chromadb.__version__ != metadata['chroma_version']:
        raise ValueError('Historical Chroma version differs')
    client = chromadb.PersistentClient(path=str(copied), settings=Settings(anonymized_telemetry=False))
    pools, checks, vector_checks = {}, [], []
    for strategy, arm in [('legacy', 'B'), ('structure-v2', 'C')]:
        collection = client.get_collection('real-world-' + strategy, embedding_function=None)
        if collection.metadata.get('hnsw:space') != 'cosine':
            raise ValueError('Historical similarity metric differs')
        stored = collection.get(include=['embeddings', 'metadatas'])
        expected = {cid for strat, cid in vectors if strat == strategy}
        if set(stored['ids']) != expected:
            raise ValueError('Index source universe differs')
        largest_delta = 0.0
        for cid, vector, meta in zip(stored['ids'], stored['embeddings'], stored['metadatas']):
            original = vectors[strategy, cid]
            normalized = np.array(ChromaVectorStore._normalize(original.tolist()), dtype=np.float32)
            # Original add_chunks normalizes cached float32 vectors before insert.
            delta = float(np.max(np.abs(vector - normalized)))
            largest_delta = max(largest_delta, delta)
            chunk = data['chunks'][strategy, cid]
            if delta > 2e-6 or meta['source'] != 'global' or meta['text'] != chunk.text or meta['file_path'] != chunk.file_path:
                raise ValueError('Index vector/text/source does not match verified cache/loader')
        vector_checks.append(dict(strategy=strategy, chunks=len(expected), max_component_delta=largest_delta))
        store = object.__new__(ChromaVectorStore)
        store._collection, store.source = collection, 'global'
        ids = sorted(expected)
        matrix = np.stack([vectors[strategy, cid] for cid in ids]).astype(np.float64)
        matrix /= np.linalg.norm(matrix, axis=1)[:, None]
        for qid, vector in queries.items():
            runs = {k: [store.search(vector.tolist(), top_k=k, source_filter='global') for _ in range(2)]
                    for k in (10, 20)}
            old = next(t for t in data['traces'] if t['question_id'] == qid and t['arm'] == arm)
            native10, native20 = runs[10][0], runs[20][0]
            oldids = [c['id'] for c in old['raw']]
            tenids = [c.chunk_id for c, _ in native10]
            twentyids = [c.chunk_id for c, _ in native20]
            exact = matrix @ (vector.astype(np.float64) / np.linalg.norm(vector.astype(np.float64)))
            exactids = [ids[i] for i in np.argsort(-exact, kind='stable')[:20]]
            exact_by_id = dict(zip(ids, exact))
            check = dict(question_id=qid, arm=arm,
                historical_k10_order_equal=tenids == oldids,
                historical_k20_prefix_equal=twentyids[:10] == oldids,
                k10_k20_prefix_equal=twentyids[:10] == tenids,
                ranking_repeat_equal=all(runs[k][0] == runs[k][1] for k in runs),
                max_historical_score_delta=max((abs(score - c['cosine']) for (chunk, score), c in zip(native10, old['raw'])
                                                if chunk.chunk_id == c['id']), default=0),
                max_exact_cosine_delta=max(abs(s - exact_by_id[c.chunk_id]) for c, s in native20),
                exact_top20_membership_equal=set(exactids) == set(twentyids),
                historical_ids=oldids, native_k10_ids=tenids, native_k20_ids=twentyids,
                exact_top20_ids=exactids)
            checks.append(check)
            # Use reconstructed, hash-verified chunks with original native scores.
            for k in (10, 20):
                pools[qid, arm, k] = [Candidate(data['chunks'][strategy, c.chunk_id], s) for c, s in runs[k][0]]
    failures = [c for c in checks if not all(c[x] for x in (
        'historical_k10_order_equal', 'historical_k20_prefix_equal', 'k10_k20_prefix_equal', 'ranking_repeat_equal'))
        or c['max_historical_score_delta'] > 2e-6]
    write(output / 'ranking-checks.json', checks)
    write(output / 'vector-checks.json', vector_checks)
    write(output / 'input-integrity.json', data['receipts'])
    # Always save discrepancies BEFORE any reference-label interpretation.
    write(output / 'retrieval-verification.json', dict(questions=60, configurations=4,
        checks=len(checks), discrepancies=len(failures), unique_cached_vectors=unique_vectors,
        embedding_calls=0, generation_calls=0, network_calls=0,
        score_tolerance=2e-6, cache_sha256=sha(run / 'vector-cache.sqlite3'),
        exact_top20_membership_disagreements=sum(not c['exact_top20_membership_equal'] for c in checks),
        native_searches=480, historical_index_modified=False))
    rows = []
    for (qid, arm, k), pool in pools.items():
        q = data['questions'][qid]
        strategy = 'legacy' if arm == 'B' else 'structure-v2'
        result, enclosing = select_scopes({'global': pool}, SelectionConfig(policy='ranked_fill', budget=1000), 8000)
        result = result['global']
        selected = [encode(Candidate(c, score), strategy, data) for c, score in result.chunks]
        rows.append(dict(question_id=qid, family_id=q['family_id'], split=q['split'], language=q['language'],
            arm=arm, k=k, configuration=f'{arm}/K{k}', strategy=strategy,
            raw=[encode(c, strategy, data) for c in pool],
            eligible=[encode(c, strategy, data) for c in pool if c.cosine >= .3], selected=selected,
            context=result.context, enclosing_context=enclosing,
            metrics=context_metrics(result, enclosing, data['sources'][strategy])))
    write(output / 'retrieval-traces.json', rows)
    seal(output, ['ranking-checks.json', 'vector-checks.json', 'input-integrity.json',
                  'retrieval-verification.json', 'retrieval-traces.json'])
    print(json.dumps(dict(output=str(output), discrepancies=len(failures),
        exact_top20_membership_disagreements=sum(not c['exact_top20_membership_equal'] for c in checks),
        max_score_delta=max(c['max_historical_score_delta'] for c in checks),
        status='REVIEW DISCREPANCIES BEFORE ANALYSIS' if failures else 'VERIFIED'), indent=2), flush=True)


def subtract_regions(coverage, regions):
    """Restricted graphical/source components never contribute positive proof."""
    result = {}
    for sid, ranges in coverage.items():
        current = list(ranges)
        for region in regions:
            if region['source_id'] != sid:
                continue
            for banned in region['component_ranges'] + region['related_context_ranges']:
                current = [(x, y) for a, z in current
                           for x, y in ((a, min(z, banned['start'])), (max(a, banned['end']), z)) if x < y]
        result[sid] = union(current)
    return result


def proof_cells(family, atoms, candidates, texts, regions=()):
    """Finite exact partition of all registered non-whitespace proof text.

    Atom fragments carried by several chunks can jointly satisfy an atom. A
    whole-atom-per-chunk shortcut would incorrectly understate the upper bound.
    """
    atom_ids = sorted({aid for r in family['requirements'] for p in r['proofs'] for aid in p})
    coverages = [subtract_regions(coverage_of([c]), regions) for c in candidates]
    masks = [0] * len(candidates)
    atom_masks, cells = {}, []
    for aid in atom_ids:
        atom = atoms[aid]
        sid, start, end = atom['source_id'], atom['start'], atom['end']
        boundaries = {start, end}
        for cov in coverages:
            for a, z in cov.get(sid, []):
                boundaries.update((max(start, min(end, a)), max(start, min(end, z))))
        points = sorted(boundaries)
        atom_mask = 0
        for a, z in zip(points, points[1:]):
            if not texts[sid][a:z].strip():
                continue
            bit = 1 << len(cells)
            cells.append((aid, sid, a, z))
            atom_mask |= bit
            for i, cov in enumerate(coverages):
                if any(x <= a and y >= z for x, y in cov.get(sid, [])):
                    masks[i] |= bit
        if not atom_mask:
            raise ValueError('Empty source atom')
        atom_masks[aid] = atom_mask
    requirements = {r['id']: [sum_masks(atom_masks[aid] for aid in alt) for alt in r['proofs']]
                    for r in family['requirements']}
    return masks, requirements, atom_masks, cells


def sum_masks(masks):
    result = 0
    for mask in masks:
        result |= mask
    return result


def support_mask(mask, family, proofs):
    return {r['id']: bool(r.get('contextual')) or any(mask & p == p for p in proofs[r['id']])
            for r in family['requirements']}


def method_specs(family):
    specs = []
    for method in family['methods']:
        active, unresolved = active_requirements(family, method, dict(family['conditions'], **method.get('conditions', {})))
        specs.append((method['id'], [r['id'] for r in active], unresolved))
    return specs


def score_support(supported, specs):
    # Same complete/coverage/hit lexicographic objective as frozen v2.1.
    rows = [(bool(ids) and all(supported[r] for r in ids) and not unresolved,
             Fraction(sum(supported[r] for r in ids), len(ids)) if ids else Fraction(0),
             sum(supported[r] for r in ids), mid) for mid, ids, unresolved in specs]
    return max(enumerate(rows), key=lambda pair: (pair[1][:3], -pair[0]))[1]


def exact_states(masks, costs):
    """Exact dynamic program: least additive character cost per proof union.

    Induction: two subsets with the same covered cells have identical future
    evidence utility. Retain the cheaper subset; every future item has positive,
    order-independent renderer cost. No heuristic/state cap is applied. Costs
    include one separator per item; subtract one separator for nonempty sets.
    The unbounded DP also proves minimum complete cost above the test budget.
    """
    if len(masks) != len(costs) or any(c <= 0 for c in costs):
        raise ValueError('Invalid exact-DP costs')
    states = {0: (0, 0)}
    for i, (mask, cost) in enumerate(zip(masks, costs)):
        if not mask:
            continue
        for before, (oldcost, subset) in list(states.items()):
            after = before | mask
            candidate = oldcost + cost, subset | (1 << i)
            if after not in states or candidate < states[after]:
                states[after] = candidate
    return states


def oracle_diagnostic(family, atoms, candidates, texts, rendered_chars, budget=1000, regions=()):
    """Reference-label-only upper bound. Returns a proof witness, never a policy."""
    if len(candidates) != len(rendered_chars) or len(candidates) > 20:
        raise ValueError('Diagnostic candidate bound or costs differ')
    masks, proofs, atom_masks, cells = proof_cells(family, atoms, candidates, texts, regions)
    specs = method_specs(family)
    states = exact_states(masks, [c + len(SEPARATOR) for c in rendered_chars])
    best = None
    minimum_complete = None
    best_subset = best_mask = 0
    best_cost = 0
    for mask, (additive, subset) in states.items():
        cost = additive - len(SEPARATOR) if subset else 0
        supported = support_mask(mask, family, proofs)
        score = score_support(supported, specs)
        if score[0] and (minimum_complete is None or (cost, subset) < minimum_complete):
            minimum_complete = cost, subset
        objective = (*score[:3], -cost, -subset)
        if cost <= budget * 4 and (best is None or objective > best):
            best, best_subset, best_mask, best_cost = objective, subset, mask, cost
    available = sum_masks(masks)
    available_support = support_mask(available, family, proofs)
    # Count distinct coherent registered proof bundles, not arbitrary redundant
    # supersets of carrier chunks. Multiple methods can share the same bundle.
    bundles = set()
    methods_available = []
    for mid, ids, unresolved in specs:
        if unresolved or not ids or not all(available_support[rid] for rid in ids):
            continue
        methods_available.append(mid)
        choices = [[p for p in proofs[rid] if available & p == p] for rid in ids]
        bundles.update(sum_masks(combo) for combo in product(*choices))
    return dict(optimality='exact', method='minimum-cost DP over exact source-proof cells; no state cap',
        states=len(states), proof_cells=len(cells),
        coverage=float(best[1]), complete=bool(best[0]),
        witness_indices=[i for i in range(len(candidates)) if best_subset & (1 << i)],
        witness_chars=best_cost, witness_tokens=(best_cost + 3) // 4,
        support=support_mask(best_mask, family, proofs),
        min_complete_chars=minimum_complete[0] if minimum_complete else None,
        min_complete_tokens=(minimum_complete[0] + 3) // 4 if minimum_complete else None,
        min_complete_indices=[i for i in range(len(candidates)) if minimum_complete and minimum_complete[1] & (1 << i)],
        complete_methods_available=methods_available, complete_registered_proof_bundles=len(bundles),
        unavailable_atom_ids=[aid for aid, mask in atom_masks.items() if available & mask != mask])


def classify(candidate_complete, actual_complete, oracle_complete, available_recall, oracle_recall,
             semantic_ambiguity=False, actual_recall=None):
    if actual_complete:
        return 'complete'
    if semantic_ambiguity:
        return 'unresolved'
    retrieval = not candidate_complete
    budget = available_recall > oracle_recall + 1e-12
    selection = oracle_complete or (actual_recall is not None and oracle_recall > actual_recall + 1e-12)
    if sum((retrieval,budget,selection))>1:
        return 'mixed'
    if selection:
        return 'selection_lost'
    if budget:
        return 'budget_infeasible'
    return 'retrieval_missing' if retrieval else 'unresolved'


def review_ranking_ties(retrieval, data, config):
    """Accept only demonstrably identical-body/exact-vector ties, never drift."""
    checks=read(retrieval/'ranking-checks.json')
    cache=FrozenVectors(Path(config['run'])/'vector-cache.sqlite3',read(Path(config['run'])/'run-metadata.json'))
    reviewed=[]
    try:
        for check in checks:
            if not check['historical_k10_order_equal'] or not check['ranking_repeat_equal'] or check['max_historical_score_delta']>2e-6:
                raise ValueError('Non-tie historical ranking/score drift')
            pairs=[]
            for left,right in zip(check['historical_ids'],check['native_k20_ids']):
                if left!=right:
                    pairs.append((left,right,'K10 prefix'))
            left=set(check['exact_top20_ids'])-set(check['native_k20_ids'])
            right=set(check['native_k20_ids'])-set(check['exact_top20_ids'])
            if len(left)!=len(right):
                raise ValueError('Inconsistent exact/native membership audit')
            pairs.extend((a,b,'Exact/native K20 boundary') for a,b in zip(sorted(left),sorted(right)))
            strategy='legacy' if check['arm']=='B' else 'structure-v2'
            for left,right,kind in pairs:
                a,b=data['chunks'][strategy,left],data['chunks'][strategy,right]
                if a.text!=b.text or not np.array_equal(cache.get(a.text),cache.get(b.text)):
                    raise ValueError('Non-identical body/vector ranking discrepancy')
                reviewed.append(dict(question_id=check['question_id'],arm=check['arm'],kind=kind,
                    left=left,right=right,text_sha256=hashlib.sha256(a.text.encode()).hexdigest(),
                    text=a.text,reason='Identical text and exact cached vector; tied cosine; source identities remain distinct'))
    finally:
        cache.close()
    return reviewed


def analyze(config, retrieval, output):
    if output.exists():
        raise ValueError('Fresh output required')
    verify_manifest(retrieval, 'integrity.json', sha(retrieval / 'integrity.json'))
    verification = read(retrieval / 'retrieval-verification.json')
    data = load_inputs(config, scoring=True)
    reviewed_ties=review_ranking_ties(retrieval,data,config)
    # Reproduce all 540 historical stage scores, including original A.
    for trace in data['traces']:
        family = data['rubric'][trace['family_id']]
        for stage in ('raw', 'eligible', 'selected'):
            if score_evidence(family, data['atoms'], coverage_of(trace[stage]), data['texts']) != data['historical'][trace['question_id'], trace['arm']][stage]['calibrated']:
                raise ValueError('Historical v2.1 stage score differs')
    regions = read(Path(config['corpus']) / 'review/r3d/restricted-regions.json')['regions']
    # Registered atoms must not assert restricted-region content.
    for aid, atom in data['atoms'].items():
        if not span_present(atom, subtract_regions({atom['source_id']: [(atom['start'], atom['end'])]}, regions), data['texts']):
            raise ValueError('Frozen proof intersects a restricted region: ' + aid)
    indexed = read(Path(config['run']) / 'indexed-source-coverage.json')
    traces = read(retrieval / 'retrieval-traces.json')
    rows = []
    full_renderer = RAGPipeline(None, None, max_context_tokens=1_000_000)
    for trace in traces:
        fid, strategy = trace['family_id'], trace['strategy']
        family, atoms, texts = data['rubric'][fid], data['atoms'], data['texts']
        eligible = trace['eligible']
        covs = {stage: subtract_regions(coverage_of(trace[stage]), regions) for stage in ('raw', 'eligible', 'selected')}
        scores = {stage: score_evidence(family, atoms, cov, texts) for stage, cov in covs.items()}
        supports = {stage: support(family, atoms, cov, texts) for stage, cov in covs.items()}
        positive = family['positive_recall_applicable']
        costs = []
        for c in eligible:
            chunk = data['chunks'][strategy, c['id']]
            rendered, used, _ = full_renderer._build_context([(chunk, c['cosine'])])
            if len(used) != 1 or used[0][0].text != c['text']:
                raise ValueError('Whole-chunk costing clipped a fragment')
            costs.append(len(rendered))
        oracle = oracle_diagnostic(family, atoms, eligible, texts, costs, regions=regions)
        witness = [eligible[i] for i in oracle['witness_indices']]
        witness_pairs = [(data['chunks'][strategy, c['id']], c['cosine']) for c in witness]
        rendered, used, tokens = RAGPipeline(None, None, max_context_tokens=1000)._build_context(witness_pairs)
        witness_cov = subtract_regions(coverage_of(witness), regions)
        witness_score = score_evidence(family, atoms, witness_cov, texts)
        scored_witness = witness_score if positive else witness_score['clarification_support']
        recall = scored_witness['positive_recall'] if positive else scored_witness['recall']
        complete = scored_witness['complete']
        if len(rendered) != oracle['witness_chars'] or tokens != oracle['witness_tokens'] or len(used) != len(witness) or recall != oracle['coverage'] or complete != oracle['complete']:
            raise ValueError('Exact DP witness does not reproduce the real renderer/scorer')
        minimum = [eligible[i] for i in oracle['min_complete_indices']]
        if minimum:
            mc, mu, mt = full_renderer._build_context([(data['chunks'][strategy, c['id']], c['cosine']) for c in minimum])
            if len(mc) != oracle['min_complete_chars'] or mt != oracle['min_complete_tokens'] or len(mu) != len(minimum):
                raise ValueError('Minimum complete-cost witness differs')
            minimum_score=score_evidence(family,atoms,subtract_regions(coverage_of(minimum),regions),texts)
            if not (minimum_score['complete'] if positive else minimum_score['clarification_support']['complete']):
                raise ValueError('Minimum complete-cost witness does not contain a complete proof')
        oracle['minimum_complete_body_chars']=sum(len(c['text']) for c in minimum) if minimum else None
        oracle['minimum_complete_attribution_and_separator_chars']=(oracle['min_complete_chars']-oracle['minimum_complete_body_chars']) if minimum else None
        specs = method_specs(family)
        chosen = scores['eligible'].get('chosen_method', specs[0][0])
        active = next(ids for mid, ids, _ in specs if mid == chosen)
        requirements = {r['id']: r for r in family['requirements']}
        missing = [rid for rid in active if not supports['eligible'][rid]]
        partial = [rid for rid in missing if next(m for m in scores['eligible']['methods'] if m['method'] == chosen)['status'][rid] == 'partial']
        # Partial registered proof can be semantically sufficient prose. Without
        # independent entailment adjudication, retain reference class separately.
        ambiguity = bool(partial) and not scores['eligible']['complete'] if positive else False
        reference_class = classify(bool(scores['eligible']['complete']), bool(scores['selected']['complete']),
                                   oracle['complete'], scores['eligible']['positive_recall'] or 0, oracle['coverage'],
                                   actual_recall=scores['selected']['positive_recall']) if positive else 'unresolved'
        classification = classify(bool(scores['eligible']['complete']), bool(scores['selected']['complete']),
                                  oracle['complete'], scores['eligible']['positive_recall'] or 0, oracle['coverage'], ambiguity,
                                  actual_recall=scores['selected']['positive_recall']) if positive else 'unresolved'
        relevant_sources = {atoms[aid]['source_id'] for r in family['requirements'] for alt in r['proofs'] for aid in alt}
        index_support = support(family, atoms, subtract_regions(indexed[strategy], regions), texts)
        target_sources = {atoms[aid]['source_id'] for rid in active for alt in requirements[rid]['proofs'] for aid in alt}
        def neighbor(c):
            sid = c['source_id']
            if sid in target_sources:
                return None
            if sid.startswith('prusa-') and any(s.startswith('prusa-') for s in target_sources):
                return 'wrong_product_source_for_registered_scope'
            if sid.startswith('postgresql-') and any(s.startswith('postgresql-') for s in target_sources):
                version=sid.split('-')[1]
                versions={s.split('-')[1] for s in target_sources if s.startswith('postgresql-')}
                return 'wrong_version_document' if version not in versions else 'same_version_other_section_not_registered_proof'
            return 'other_source_not_registered_proof'
        critical = [rid for rid, r in requirements.items() if r['safety_critical'] and not r.get('contextual')]
        conditions = [rid for rid, r in requirements.items() if (r['safety_critical'] or r.get('when')) and not r.get('contextual')]
        prerequisite_ids=[rid for rid,r in requirements.items() if any(word in r['statement'].casefold()
            for word in ('prerequisite','before','same server','same-server','session','model','version','dependency','ancestr','heat'))]
        candidate_ranges = coverage_of(eligible)
        total_chars = sum(z-a for c in eligible for a,z in c['source_ranges'])
        unique_chars = sum(z-a for ranges in candidate_ranges.values() for a,z in ranges)
        new_support = support(family, atoms, subtract_regions(coverage_of(eligible[:10]), regions), texts)
        exposure = lambda cov: [r['id'] for r in regions if any(max(a, x['start']) < min(z, x['end'])
            for a,z in cov.get(r['source_id'], []) for x in r['component_ranges'] + r['related_context_ranges'])]
        row = dict(question_id=trace['question_id'], family_id=fid, arm=trace['arm'], k=trace['k'],
            configuration=trace['configuration'], split=trace['split'], language=trace['language'],
            category=data['families'][fid]['category'],
            source_groups=sorted({data['units'][sid]['family'] for sid in relevant_sources}) or ['unavailable'],
            answerable=positive, classification=classification, reference_bottleneck=reference_class,
            reference_factors=dict(retrieval_missing=positive and not bool(scores['eligible']['complete']),
                selection_recoverable=positive and oracle['coverage']>(scores['selected']['positive_recall'] or 0)+1e-12,
                budget_reduces_available_coverage=positive and (scores['eligible']['positive_recall'] or 0)>oracle['coverage']+1e-12),
            ambiguity_reasons=['Partial registered proof; unregistered semantic sufficiency not adjudicated'] if ambiguity else [],
            scope_note=None if positive else 'Positive recall N/A: clarification/unavailable facts are not retrieval failures',
            scores=scores, support=supports, oracle=oracle,
            missing_active_requirements=missing, missing_essential=[rid for rid in missing if requirements[rid]['category']=='essential'],
            partial_missing_requirements=partial,
            missing_conditions=[rid for rid in conditions if not supports['eligible'][rid]],
            missing_critical=[rid for rid in critical if not supports['eligible'][rid]],
            index_representation_missing=[rid for rid in active if not index_support[rid]],
            available_but_ranked_fill_lost=[rid for rid in requirements if supports['eligible'][rid] and not supports['selected'][rid]],
            ranks_11_20_requirement_gains=[rid for rid in requirements if supports['eligible'][rid] and not new_support[rid]] if trace['k']==20 else [],
            ranks_11_20=[dict(rank=i+1, id=c['id'], source_id=c['source_id'], cosine=c['cosine']) for i,c in enumerate(trace['raw']) if i>=10],
            neighbor_candidates=[dict(rank=i+1, id=c['id'], source_id=c['source_id'], reason=neighbor(c)) for i,c in enumerate(trace['raw']) if neighbor(c)],
            anchor_only_candidates=[dict(rank=i+1,id=c['id'],source_id=c['source_id']) for i,c in enumerate(trace['raw'])
                if re.fullmatch(r'\s*(?:<a\s+id="[^"]+"\s*></a>\s*)+',c['text'])],
            anchor_only_selected=[c['id'] for c in trace['selected'] if re.fullmatch(r'\s*(?:<a\s+id="[^"]+"\s*></a>\s*)+',c['text'])],
            candidate_sources=len(candidate_ranges), candidate_repeated_source_chars=total_chars-unique_chars,
            threshold_filtered_candidates=len(trace['raw'])-len(eligible),
            threshold_lost_requirements=[rid for rid in requirements if supports['raw'][rid] and not supports['eligible'][rid]],
            candidate_sections=len({(c['source_id'], tuple(data['chunks'][strategy,c['id']].metadata.get('section_path') or [])) for c in eligible}),
            critical_ids=critical, condition_ids=conditions, prerequisite_ids=prerequisite_ids,
            requirement_categories={rid:r['category'] for rid,r in requirements.items()}, metrics=trace['metrics'],
            restricted_candidate_exposure=exposure(coverage_of(trace['eligible'])),
            restricted_selected_exposure=exposure(coverage_of(trace['selected'])),
            oracle_witness_ids=[c['id'] for c in witness],
            minimum_complete_ids=[c['id'] for c in minimum])
        rows.append(row)
    output.mkdir(parents=True)
    write(output / 'per-question.json', rows)
    write(output / 'input-integrity.json', data['receipts'])
    write(output / 'ranking-tie-review.json',reviewed_ties)
    summarize(rows, output)
    write(output / 'provenance.json', dict(retrieval_manifest_sha256=sha(retrieval / 'integrity.json'),
        historical_contexts_reproduced=180, historical_stage_scores_reproduced=540,
        optimality='exact finite DP; witnesses rechecked with frozen scorer and unchanged renderer',
        diagnostic_only=True, embedding_calls=0, generation_calls=0, judge_calls=0, network_calls=0,
        labels_modified=False, answers_read=False, module_sha256=sha(__file__),
        caveat='Agent-draft v2.1; exposed development data; no independent domain/semantic validation'))
    seal(output, ['per-question.json', 'input-integrity.json', 'ranking-tie-review.json', 'summary.json', 'paired-k.json',
                  'all-questions.csv', 'strata.json', 'evidence-types.json', 'oracle-paired.json', 'provenance.json'])
    print(json.dumps(dict(output=str(output), summary=read(output/'summary.json')), indent=2), flush=True)


def aggregate(rows):
    answerable = [r for r in rows if r['answerable']]
    result = dict(questions=len(rows), answerable=len(answerable))
    for stage, name in [('eligible','candidate'), ('selected','actual')]:
        result[name+'_coverage'] = statistics.mean(r['scores'][stage]['positive_recall'] for r in answerable) if answerable else None
        result[name+'_complete'] = sum(bool(r['scores'][stage]['complete']) for r in answerable)
    result.update(oracle_coverage=statistics.mean(r['oracle']['coverage'] for r in answerable) if answerable else None,
        oracle_complete=sum(r['oracle']['complete'] for r in answerable),
        budget_infeasible=sum(r['oracle']['min_complete_tokens'] is not None and r['oracle']['min_complete_tokens']>1000 for r in answerable),
        classifications=dict(Counter(r['classification'] for r in answerable)),
        reference_bottlenecks=dict(Counter(r['reference_bottleneck'] for r in answerable)),
        mean_tokens=statistics.mean(r['metrics']['estimated_tokens'] for r in rows),
        mean_attribution_chars=statistics.mean(r['metrics']['attribution_chars'] for r in rows),
        mean_candidate_sources=statistics.mean(r['candidate_sources'] for r in rows),
        mean_candidate_repeated_source_chars=statistics.mean(r['candidate_repeated_source_chars'] for r in rows),
        mean_selected_repeated_source_chars=statistics.mean(r['metrics']['repeated_source_chars'] for r in rows),
        restricted_candidate_questions=sum(bool(r['restricted_candidate_exposure']) for r in rows),
        restricted_selected_questions=sum(bool(r['restricted_selected_exposure']) for r in rows),
        max_dp_states=max(r['oracle']['states'] for r in rows))
    result.update(anchor_only_candidate_instances=sum(len(r['anchor_only_candidates']) for r in rows),
        anchor_only_candidate_questions=sum(bool(r['anchor_only_candidates']) for r in rows),
        anchor_only_selected_instances=sum(len(r['anchor_only_selected']) for r in rows),
        index_representation_missing_questions=sum(bool(r['index_representation_missing']) for r in answerable))
    for ids, name in [('critical_ids', 'critical'), ('condition_ids', 'conditions')]:
        result[name+'_total'] = sum(len(r[ids]) for r in rows)
        for stage, label in [('eligible','candidate'), ('selected','actual')]:
            result[name+'_'+label] = sum(r['support'][stage][rid] for r in rows for rid in r[ids])
        result[name+'_oracle_witness'] = sum(r['oracle']['support'][rid] for r in rows for rid in r[ids])
    return result


def summarize(rows, output):
    configs = ['B/K10', 'B/K20', 'C/K10', 'C/K20']
    write(output / 'summary.json', {cfg: aggregate([r for r in rows if r['configuration']==cfg]) for cfg in configs})
    strata = {}
    for cfg in configs:
        rr = [r for r in rows if r['configuration']==cfg]
        for dimension in ('split','language','category','source_groups'):
            values = sorted({v for r in rr for v in (r[dimension] if dimension=='source_groups' else [r[dimension]])})
            for value in values:
                strata[f'{cfg}/{dimension}/{value}'] = aggregate([r for r in rr if value in r[dimension]] if dimension=='source_groups' else [r for r in rr if value==r[dimension]])
    write(output/'strata.json', strata)
    by = {(r['question_id'],r['arm'],r['k']):r for r in rows}
    paired = []
    for (qid, arm, k), before in by.items():
        if k!=10:
            continue
        after = by[qid,arm,20]
        support_changes = {}
        for stage in ('eligible','selected'):
            bs, es = before['support'][stage], after['support'][stage]
            gains = [rid for rid in bs if es[rid] and not bs[rid]]
            losses = [rid for rid in bs if bs[rid] and not es[rid]]
            support_changes[stage] = dict(gains=gains, losses=losses,
                critical_gains=[rid for rid in gains if rid in before['critical_ids']],
                critical_losses=[rid for rid in losses if rid in before['critical_ids']],
                condition_gains=[rid for rid in gains if rid in before['condition_ids']],
                condition_losses=[rid for rid in losses if rid in before['condition_ids']])
        paired.append(dict(question_id=qid, arm=arm, answerable=before['answerable'], support_changes=support_changes,
            actual_complete_before=before['scores']['selected']['complete'], actual_complete_after=after['scores']['selected']['complete'],
            oracle_complete_before=before['oracle']['complete'], oracle_complete_after=after['oracle']['complete'],
            oracle_coverage_delta=after['oracle']['coverage']-before['oracle']['coverage']))
    write(output/'paired-k.json', paired)
    oracle_paired=[]
    for r in rows:
        bs,es=r['support']['selected'],r['oracle']['support']
        gains=[rid for rid in bs if es[rid] and not bs[rid]]
        losses=[rid for rid in bs if bs[rid] and not es[rid]]
        oracle_paired.append(dict(question_id=r['question_id'],configuration=r['configuration'],answerable=r['answerable'],
            gains=gains,losses=losses,
            critical_gains=[rid for rid in gains if rid in r['critical_ids']],
            critical_losses=[rid for rid in losses if rid in r['critical_ids']],
            condition_gains=[rid for rid in gains if rid in r['condition_ids']],
            condition_losses=[rid for rid in losses if rid in r['condition_ids']]))
    write(output/'oracle-paired.json',oracle_paired)
    evidence = {}
    # Fixed all-branch ledger, not claims about advice activation or safe answers.
    for cfg in configs:
        rr = [r for r in rows if r['configuration']==cfg]
        cells = {}
        for kind, ids in [('critical','critical_ids'),('conditions_and_prerequisites','condition_ids'),
                          ('prerequisites_statement_tag_diagnostic','prerequisite_ids')]:
            cells[kind] = dict(total=sum(len(r[ids]) for r in rr),
                candidate=sum(r['support']['eligible'][rid] for r in rr for rid in r[ids]),
                actual=sum(r['support']['selected'][rid] for r in rr for rid in r[ids]),
                oracle_witness=sum(r['oracle']['support'][rid] for r in rr for rid in r[ids]))
        for category in ('essential','conditional','optional','alternative'):
            tagged=[(r,rid) for r in rr for rid,c in r['requirement_categories'].items() if c==category]
            cells[category]=dict(total=len(tagged),
                candidate=sum(r['support']['eligible'][rid] for r,rid in tagged),
                actual=sum(r['support']['selected'][rid] for r,rid in tagged),
                oracle_witness=sum(r['oracle']['support'][rid] for r,rid in tagged))
        evidence[cfg] = cells
    write(output/'evidence-types.json', evidence)
    with (output/'all-questions.csv').open('w',encoding='utf-8',newline='') as handle:
        fields=['question_id','configuration','answerable','classification','reference_bottleneck','candidate_coverage',
                'actual_coverage','oracle_coverage','candidate_complete','actual_complete','oracle_complete','min_complete_tokens',
                'complete_registered_proof_bundles','missing_essential','available_but_lost','ambiguity']
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(question_id=r['question_id'],configuration=r['configuration'],answerable=r['answerable'],
                classification=r['classification'],reference_bottleneck=r['reference_bottleneck'],
                candidate_coverage=r['scores']['eligible']['positive_recall'],actual_coverage=r['scores']['selected']['positive_recall'],
                oracle_coverage=r['oracle']['coverage'] if r['answerable'] else '',
                candidate_complete=r['scores']['eligible']['complete'],actual_complete=r['scores']['selected']['complete'],
                oracle_complete=r['oracle']['complete'] if r['answerable'] else '',min_complete_tokens=r['oracle']['min_complete_tokens'],
                complete_registered_proof_bundles=r['oracle']['complete_registered_proof_bundles'],
                missing_essential=';'.join(r['missing_essential']),available_but_lost=';'.join(r['available_but_ranked_fill_lost']),
                ambiguity=';'.join(r['ambiguity_reasons'])))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['retrieve','analyze'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--retrieval',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with offline():
        if args.mode=='retrieve':
            retrieve(read(args.config),args.output)
        else:
            if not args.retrieval:
                parser.error('--retrieval is required for analyze')
            analyze(read(args.config),args.retrieval,args.output)


if __name__=='__main__':
    main()
