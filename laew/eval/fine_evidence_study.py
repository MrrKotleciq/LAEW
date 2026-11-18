"""Offline feasibility study. Reference extraction is never a runtime mechanism.

prepare is question-only and stops before any missing embedding is computed.
inspect/analyze are separate curator processes. No embedding client is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from laew.eval.complementary_context_study import load_inputs, offline, read, seal, sha, verify_manifest, write

PARENT = Path(os.environ.get('LAEW_RETRIEVAL_BUDGET_ROOT', 'laew-retrieval-budget-v1'))
PARENT_SHA = 'c5a96d10822d5d6f7559b8e0985d7758eb9864d0038c734dca8dcb73d76c1917'


def prepare(config, output):
    from laew.eval import question_decomposition as mechanism
    from laew.eval.retrieval_budget_diagnostics import FrozenVectors
    if output.exists():
        raise ValueError('Fresh output required')
    data = load_inputs(config, scoring=False)
    metadata = read(Path(config['run']) / 'run-metadata.json')
    cache = FrozenVectors(Path(config['run']) / 'vector-cache.sqlite3', metadata)
    plans, pending, hits = [], {}, set()
    try:
        for qid, q in data['questions'].items():
            plan = mechanism.decompose(q['text'])
            plan.update(question_id=qid, language=q['language'],
                        allocations={str(n): mechanism.search_allocations(len(plan['queries']), n) for n in (10, 20)})
            for query in plan['queries']:
                try:
                    cache.get(query)
                    hits.add(query)
                except RuntimeError as error:
                    if 'EMBEDDING STOP GATE' not in str(error):
                        raise
                    pending.setdefault(query, []).append(qid)
            plans.append(plan)
    finally:
        cache.close()
    workload = [dict(text=q, question_ids=ids, characters=len(q),
                     estimated_tokens_chars4=(len(q) + 3) // 4,
                     sha256=hashlib.sha256(q.encode()).hexdigest()) for q, ids in pending.items()]
    output.mkdir(parents=True)
    write(output / 'question-only-plans.json', plans)
    write(output / 'pending-embedding-inputs.json', workload)
    write(output / 'input-integrity.json', data['receipts'])
    write(output / 'freeze.json', dict(version=mechanism.VERSION, mechanism_sha256=sha(mechanism.__file__),
        plans_sha256=sha(output / 'question-only-plans.json'), labels_read=False, rubric_read=False,
        saved_answers_read=False, embedding_calls=0, network_calls=0,
        design='Full original scope plus explicit question-clause focus; max four contiguous foci; original search retained',
        merge='Round robin original first; exact chunk-ID dedup; no source/version substitution; no backfill',
        budgets='10 or 20 total raw slots divided across all searches; separate optional 20 slots per search',
        threshold=.3, similarity='unchanged cosine', original_index_modified=False,
        new_unique_inputs=len(workload), verified_unique_cache_hits=len(hits),
        estimated_tokens_chars4=sum(w['estimated_tokens_chars4'] for w in workload),
        utf8_bytes=sum(len(w['text'].encode()) for w in workload),
        dimensions=metadata['dimensions'], model_catalog=metadata['model_catalog'],
        model_identity_sha256=metadata['model_identity_sha256'],
        queries=sum(len(p['queries']) for p in plans), split_questions=sum(p['status']=='split' for p in plans),
        languages={lang: dict(questions=sum(p['language']==lang for p in plans),
                              split=sum(p['language']==lang and p['status']=='split' for p in plans),
                              searches=sum(len(p['queries']) for p in plans if p['language']==lang))
                   for lang in ('en','pl','de')},
        gate='STOP: missing embeddings require explicit user authorization; no provider/service accessed'))
    seal(output, ['question-only-plans.json','pending-embedding-inputs.json','input-integrity.json','freeze.json'])
    print(json.dumps(read(output / 'freeze.json'), indent=2))


def inspect(config, output):
    if output.exists():
        raise ValueError('Fresh output required')
    receipt = verify_manifest(PARENT, 'artifact-integrity.json', PARENT_SHA)
    data = load_inputs(config, scoring=True)
    from laew.eval.real_world_retrieval import coverage_of
    from laew.eval.scoring_calibration import score_evidence
    for trace in data['traces']:
        for stage in ('raw','eligible','selected'):
            if score_evidence(data['rubric'][trace['family_id']], data['atoms'],
                              coverage_of(trace[stage]), data['texts']) != data['historical'][trace['question_id'],trace['arm']][stage]['calibrated']:
                raise ValueError('Historical scoring drift')
    review = []
    for aid, atom in data['atoms'].items():
        text = data['texts'][atom['source_id']]
        a, z = atom['start'], atom['end']
        review.append(dict(atom_id=aid, atom=atom, source_unit=data['units'][atom['source_id']],
                           exact=text[a:z], before=text[max(0,a-650):a], after=text[z:z+650]))
    output.mkdir(parents=True)
    write(output / 'atom-local-review.json', review)
    write(output / 'integrity-receipts.json', [receipt] + data['receipts'])
    write(output / 'rubric-review.json', data['rubric'])
    write(output / 'replay.json', dict(historical_contexts_reproduced=180, historical_stage_scores_reproduced=540,
        atoms=len(review), production_changed=False, embedding_calls=0, generation_calls=0))
    seal(output, ['atom-local-review.json','integrity-receipts.json','rubric-review.json','replay.json'])
    print(json.dumps(read(output / 'replay.json')))


def scopes(config, output):
    from laew.eval import source_evidence_oracle as oracle
    if output.exists():
        raise ValueError('Fresh output required')
    data=load_inputs(config,scoring=True)
    rules=oracle.make_scope_rules(data['atoms'],data['texts'])
    output.mkdir(parents=True)
    write(output/'scope-rules.json',rules)
    write(output/'freeze.json',dict(oracle_sha256=sha(oracle.__file__),rules_sha256=sha(output/'scope-rules.json'),
        granularity_libraries=list(oracle.GRANULARITIES),
        labels_used=True,origin='agent-authored diagnostic envelope review',independent_review=False,
        candidate_rule='Every non-whitespace source character of each mandatory envelope must already be in the eligible unrestricted candidate union',
        boundary_policy='Full applicable parameter definitions, warnings and local procedures; exact source order; explicit gaps; unchanged source/version',
        bounds='Necessary registered-body-only floor <= semantic minimum <= admitted coherent witness cost when available',
        attribution='Per source: exact identity, full revision, full normalized SHA256; per fragment: exact Unicode offsets; visible gap separators',
        warning='Exact finite-library optimization is not proof of globally minimal coherent extraction'))
    write(output/'methodology-note.json',dict(
        revision='source-identity-scope-v2',
        change='Section headings are no longer mandatory candidate BODY when exact source identity/revision already establish scope; parameter definitions and all substantive safety/sequence closures are unchanged',
        reason='Strict-v1 conflated available source/section metadata with missing technical evidence; its outputs remain preserved separately',
        exposure='All 60 questions exposed; this is a disclosed methodological revision after strict-v1, not independent validation'))
    write(output/'oracle-correction.json',dict(
        issue='A packet could incidentally supply another registered atom without that requirement local scope closure',
        correction='Reject every union in which any credited registered proof lacks at least one complete declared proof envelope',
        rule_changes=False,decomposition_changes=False,
        previous_outputs='analysis-v1 and analysis-v2 are preserved pre-correction diagnostics, not authoritative coherent witnesses'))
    seal(output,['scope-rules.json','freeze.json','methodology-note.json','oracle-correction.json'])
    print(dict(scope_rules=len(rules),output=str(output)))


def analyze(config, output, scope_dir, decomposition):
    from laew.eval import source_evidence_oracle as oracle
    from laew.eval.real_world_retrieval import coverage_of
    from laew.eval.scoring_calibration import score_evidence
    if output.exists():
        raise ValueError('Fresh output required')
    verify_manifest(PARENT,'artifact-integrity.json',PARENT_SHA)
    verify_manifest(scope_dir,'integrity.json',sha(scope_dir/'integrity.json'))
    verify_manifest(decomposition,'integrity.json',sha(decomposition/'integrity.json'))
    freeze=read(scope_dir/'freeze.json')
    if freeze['oracle_sha256']!=sha(oracle.__file__) or freeze['rules_sha256']!=sha(scope_dir/'scope-rules.json'):
        raise ValueError('Extraction library differs from pre-analysis freeze')
    data=load_inputs(config,scoring=True)
    regions=read(Path(config['corpus'])/'review/r3d/restricted-regions.json')['regions']
    traces=read(PARENT/'retrieval/retrieval-traces.json')
    prior={(r['question_id'],r['configuration']):r for r in read(PARENT/'analysis-v3/per-question.json')}
    plans={p['question_id']:p for p in read(decomposition/'question-only-plans.json')}
    rules=read(scope_dir/'scope-rules.json')
    rows=[]
    for trace in traces:
        qid,cfg=trace['question_id'],trace['configuration']
        family=data['rubric'][trace['family_id']]
        before=prior[qid,cfg]
        candidate_cov=oracle.subtract_regions(coverage_of(trace['eligible']),regions)
        candidate_score=score_evidence(family,data['atoms'],candidate_cov,data['texts'])
        if candidate_score!=before['scores']['eligible']:
            raise ValueError('Frozen candidate score differs')
        floor=oracle.solve(family,data['atoms'],data['texts'],data['units'],trace['eligible'],regions,rules,'minimal-span',floor=True)
        results={g:oracle.solve(family,data['atoms'],data['texts'],data['units'],trace['eligible'],regions,rules,g)
                 for g in oracle.GRANULARITIES}
        # Serialization control: union/deduplicate the source ranges of the
        # SAME original minimum-complete whole-chunk witness and group citation.
        # This changes duplicate/synthetic representation as well as attribution;
        # it is neither an attribution-only control nor a new selector.
        old_indices=before['oracle']['min_complete_indices']
        same_whole=[trace['eligible'][i] for i in old_indices]
        control=oracle.render(coverage_of(same_whole),data['texts'],data['units']) if same_whole else None
        for granularity,result in results.items():
            positive=family['positive_recall_applicable']
            witness=result['witness']
            selected_support=before['support']['selected']
            retained=result['witness']['support']
            result['critical_retained']=[rid for rid in before['critical_ids'] if retained[rid]]
            result['critical_missing']=[rid for rid in before['critical_ids'] if not retained[rid]]
            result['conditions_retained']=[rid for rid in before['condition_ids'] if retained[rid]]
            result['conditions_missing']=[rid for rid in before['condition_ids'] if not retained[rid]]
            result['prerequisites_retained']=[rid for rid in before['prerequisite_ids'] if retained[rid]]
            result['gained_vs_actual']=[rid for rid in retained if retained[rid] and not selected_support[rid]]
            result['lost_vs_actual']=[rid for rid in retained if selected_support[rid] and not retained[rid]]
            restricted=oracle.subtract_regions(witness['coverage'],regions)
            if oracle.ranges_key(restricted)!=oracle.ranges_key(witness['coverage']):
                raise ValueError('Restricted component in extraction witness')
            result['restricted_exposure']=[]
            result['ambiguities']=['Curator envelope minimality and unregistered/cross-language equivalence lack independent validation']
            if result['rejected']:
                result['ambiguities'].append('Required neighboring scope not present in candidate pool; no source expansion performed')
            # Source applicability is exact identity/revision matching, not a
            # certification that every unrelated sentence is technically true.
            result['source_applicability']='Frozen exact source/version proof; no cross-version substitution'
        rows.append(dict(question_id=qid,family_id=trace['family_id'],language=trace['language'],
            configuration=cfg,answerable=family['positive_recall_applicable'],
            candidate_score=candidate_score,actual_score=before['scores']['selected'],
            whole_chunk_oracle=before['oracle'],same_whole_witness_grouped_citation_control=control,
            proof_body_cost_floor=floor,extractions=results,
            decomposition=dict(status='pending_embedding_authorization' if plans[qid]['status']=='split' else 'identical_original_query',
                               queries=len(plans[qid]['queries']),foci=plans[qid]['foci']),
            missing_candidate_requirements=before['missing_active_requirements'],
            partial_evidence_ambiguities=before['partial_missing_requirements'],
            wrong_product_version_candidate_diagnostics=before['neighbor_candidates'],
            candidate_restricted_exposure=before['restricted_candidate_exposure'],
            cross_language_note='Shared family rubric; translations are dependent and source-equivalence review remains provisional'))
    output.mkdir(parents=True)
    write(output/'per-question.json',rows)
    import csv
    with (output/'per-question.csv').open('w',encoding='utf-8',newline='') as handle:
        keys=['question_id','configuration','answerable','candidate_complete','actual_complete','whole_complete','whole_min_tokens','proof_body_floor_tokens']
        for g in oracle.GRANULARITIES:
            keys.extend([g+'_complete',g+'_coverage',g+'_min_tokens',g+'_fragments',g+'_citation_chars',g+'_rejected_packets'])
        writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader()
        for r in rows:
            flat=dict(question_id=r['question_id'],configuration=r['configuration'],answerable=r['answerable'],
                candidate_complete=r['candidate_score']['complete'] if r['answerable'] else None,
                actual_complete=r['actual_score']['complete'] if r['answerable'] else None,
                whole_complete=r['whole_chunk_oracle']['complete'] if r['answerable'] else None,
                whole_min_tokens=r['whole_chunk_oracle']['min_complete_tokens'],
                proof_body_floor_tokens=r['proof_body_cost_floor']['min_complete_tokens'])
            for g,e in r['extractions'].items():
                flat.update({g+'_complete':e['complete'] if r['answerable'] else None,g+'_coverage':e['coverage'] if r['answerable'] else None,
                             g+'_min_tokens':e['min_complete_tokens'],g+'_fragments':e['witness']['rendering']['fragments'],
                             g+'_citation_chars':e['witness']['rendering']['attribution_and_separator_chars'],g+'_rejected_packets':len(e['rejected'])})
            writer.writerow(flat)
    summary={}
    for cfg in ('B/K10','B/K20','C/K10','C/K20'):
        group=[r for r in rows if r['configuration']==cfg and r['answerable']]
        summary[cfg]=dict(answerable=len(group),candidate_complete=sum(r['candidate_score']['complete'] for r in group),
            actual_complete=sum(r['actual_score']['complete'] for r in group),whole_complete=sum(r['whole_chunk_oracle']['complete'] for r in group),
            necessary_body_floor_complete_upper=sum(r['proof_body_cost_floor']['complete'] for r in group),
            extraction={g:dict(complete=sum(r['extractions'][g]['complete'] for r in group),
                coverage=sum(r['extractions'][g]['coverage'] for r in group)/len(group),
                cannot_fit_admitted_complete=sum(r['extractions'][g]['min_complete_tokens'] is not None and r['extractions'][g]['min_complete_tokens']>1000 for r in group),
                scope_gap_prevents_complete=sum(r['candidate_score']['complete'] and r['extractions'][g]['min_complete_tokens'] is None for r in group),
                gains_vs_whole=[r['question_id'] for r in group if r['extractions'][g]['complete'] and not r['whole_chunk_oracle']['complete']],
                losses_vs_whole=[r['question_id'] for r in group if r['whole_chunk_oracle']['complete'] and not r['extractions'][g]['complete']],
                critical_retained=sum(len(r['extractions'][g]['critical_retained']) for r in group),
                critical_lost_vs_actual=[dict(question_id=r['question_id'],requirements=[rid for rid in r['extractions'][g]['lost_vs_actual'] if rid in r['extractions'][g]['critical_missing']])
                                        for r in group if any(rid in r['extractions'][g]['critical_missing'] for rid in r['extractions'][g]['lost_vs_actual'])],
                max_states=max(r['extractions'][g]['states'] for r in group)) for g in oracle.GRANULARITIES})
    write(output/'summary.json',summary)
    write(output/'input-integrity.json',data['receipts'])
    write(output/'provenance.json',dict(parent_sha256=PARENT_SHA,scope_manifest_sha256=sha(scope_dir/'integrity.json'),
        decomposition_manifest_sha256=sha(decomposition/'integrity.json'),oracle_sha256=sha(oracle.__file__),
        runner_sha256=sha(__file__),questions=60,rows=len(rows),embedding_calls=0,generation_calls=0,
        network_calls=0,reference_labels_used_only_for_extraction_and_scoring=True,
        no_combined_decomposition_bound='No new subquery retrieval data: do not sum extraction and hypothetical retrieval gains',
        original_results_modified=False,independent_validation=False))
    seal(output,['per-question.json','per-question.csv','summary.json','input-integrity.json','provenance.json'])
    print(json.dumps(summary,indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare','inspect','scopes','analyze'])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scopes', type=Path)
    parser.add_argument('--decomposition', type=Path)
    args = parser.parse_args()
    with offline():
        if args.mode=='analyze':
            if not args.scopes or not args.decomposition:
                parser.error('--scopes and --decomposition required')
            analyze(read(args.config),args.output,args.scopes,args.decomposition)
        else:
            globals()[args.mode](read(args.config), args.output)


if __name__ == '__main__':
    main()
