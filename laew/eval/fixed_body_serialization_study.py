"""Offline fixed-selected-body preparation, collection and separate scoring."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

from laew.eval import fixed_body_citations as fmt
from laew.eval.complementary_context_study import offline, read, write, sha, seal, verify_manifest
from laew.eval.real_world_retrieval import payload_segments, coverage_of
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.pipeline import RAGPipeline
from laew.rag.evidence_selection import scope_section

REPO = Path(__file__).resolve().parents[2]
PARENT = Path(os.environ.get('LAEW_FINE_EVIDENCE_ROOT', 'laew-fine-evidence-v1'))
BOUNDARY = PARENT.parent / 'laew-source-boundaries-v1'
PARENT_SHA = 'dfd32baa3e9de0aa67ecaa47a0b6be7b0dcba0b3fb6f05a25abbb8377d6218db'
BOUNDARY_SHA = '35225effb768c1a4256926428ac78995eef7876fe1431423919bdcf1c62b290f'
OWN_FILES = {'laew/eval/fixed_body_citations.py', 'laew/eval/fixed_body_serialization_study.py',
             'tests/evaluation/test_fixed_body_citations.py',
             'docs/reports/STAGE_2B2_FIXED_BODY_CITATION_SERIALIZATION_20261116.md'}


def exposure(sid, ranges, regions):
    return tuple(r['id'] for r in regions if r['source_id'] == sid and any(
        max(a, cell['start']) < min(z, cell['end']) for a,z in ranges
        for cell in r['component_ranges'] + r['related_context_ranges']))


def prepare(package, output):
    if output.exists():
        raise ValueError('Fresh input directory required')
    paths = subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=REPO).decode().split('\0')
    initial = dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        protected_files=[dict(path=p,sha256=sha(REPO/p)) for p in paths if p and p not in OWN_FILES],
        observation='Preexisting changes recorded before collection; current experiment paths excluded')
    receipts = [verify_manifest(PARENT,'artifact-integrity.json',PARENT_SHA),
                verify_manifest(BOUNDARY,'artifact-integrity.json',BOUNDARY_SHA)]
    config = read(PARENT/'study-config.json')
    corpus, run = Path(config['corpus']), Path(config['run'])
    sys.path.insert(0,str(REPO/'tools/corpus'))
    from prepare_real_world_pilot import verify_corpus
    receipts.append(verify_corpus(corpus))
    receipts.append(verify_manifest(run.parent,'artifact-integrity.json',config['retrieval_sha']))
    receipts.append(verify_manifest(run,'trace-integrity.json',config['trace_sha']))
    receipts.append(verify_manifest(Path(config['questions']),'input-integrity.json',config['questions_sha']))
    # Rubric is not read by preparation/collection. Only its historical manifest
    # bytes are pinned for the separate post-collection scorer.
    units = {u['id']:u for u in read(corpus/'corpus/source-manifest.json')['source_units']}
    texts = {sid:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    chunks, mappings = {}, {}
    for strategy in ('legacy','structure-v2'):
        loader = object.__new__(KnowledgeBase)
        loader.chunk_size, loader.chunk_overlap, loader.chunking_strategy = 1000, 200, strategy
        for sid,u in units.items():
            path=corpus/'corpus'/u['normalized_path']
            generated=loader._load_file(path,'global',path.parent,content=texts[sid],embed=False)
            records=read(corpus/f'corpus/chunk-maps/{sid}-{strategy}.json')['records']
            if len(generated)!=len(records):raise ValueError('Frozen chunk count drift')
            for chunk,record in zip(generated,records):
                if fmt.digest(chunk.text)!=record['text_sha256']:raise ValueError('Frozen chunk payload drift')
                chunks[strategy,chunk.chunk_id]=chunk
                mappings[strategy,chunk.chunk_id]=(sid,record)
    regions=read(corpus/'review/r3d/restricted-regions.json')['regions']
    sources={};contracts=[]
    def make(trace, selected, historical, kind):
        strategy=trace['strategy'];passages=[];local=[];raw=[]
        for c in trace['raw']:
            chunk=chunks[strategy,c['id']];sid,mapping=mappings[strategy,c['id']]
            if (chunk.text!=c['text'] or sid!=c['source_id'] or c['source_sha256']!=units[sid]['normalized_sha256']
                    or c['source_ranges']!=[list(r) for r in payload_segments(chunk,mapping,texts[sid],len(chunk.text))]):
                raise ValueError('Frozen candidate identity/source/ranking payload differs')
            raw.append(dict(id=c['id'],cosine=c['cosine'],source_id=sid,source_sha256=c['source_sha256'],
                            body_sha256=fmt.digest(c['text']),ranges=c['source_ranges']))
        for c in selected:
            chunk=chunks[strategy,c['id']];sid,mapping=mappings[strategy,c['id']];unit=units[sid]
            ranges=tuple(tuple(r) for r in c['source_ranges'])
            if (sid!=c['source_id'] or c['source_sha256']!=unit['normalized_sha256']
                    or not chunk.text.startswith(c['text'])
                    or ranges!=tuple(payload_segments(chunk,mapping,texts[sid],len(c['text'])))):
                # payload_segments can return list pairs; compare JSON below.
                if (sid!=c['source_id'] or c['source_sha256']!=unit['normalized_sha256']
                        or not chunk.text.startswith(c['text'])
                        or fmt.canonical(ranges)!=fmt.canonical(payload_segments(chunk,mapping,texts[sid],len(c['text'])))):
                    raise ValueError('Selected body/source/visible ranges differ')
            source=fmt.Source(sid,unit['revision'],unit['normalized_sha256'],texts[sid],chunk.file_path,unit['applicable_versions'])
            sources[source.key]=source
            if source.key not in local:local.append(source.key)
            passage=fmt.Passage(c['id'],source.key,c['text'],fmt.digest(c['text']),ranges,
                fmt.canonical(chunk.metadata),fmt.digest(fmt.canonical(mapping)),
                annotations=bool(mapping['synthetic_chars'] or len(c['text'])!=sum(z-a for a,z in ranges)),
                clipped=c['text']!=chunk.text,restricted=exposure(sid,ranges,regions))
            passages.append(dict(**asdict(passage),original_mapping=mapping,
                                 original_candidate_rank=next(i+1 for i,r in enumerate(trace['raw']) if r['id']==c['id'])))
        contract=dict(question_id=trace['question_id'],family_id=trace['family_id'],language=trace['language'],split=trace['split'],
            arm=trace['arm'],strategy=strategy,kind=kind,k=trace['k'],policy=trace['policy'],scope='global',
            scope_budget=1000,overall_budget=8000,raw_candidates=raw,eligible_ids=[c['id'] for c in trace['eligible']],
            selected_ids=[c['id'] for c in selected],source_keys=local,passages=passages,historical_context=historical,
            original_selection_decisions='Immutable selected IDs/order and skipped eligible IDs are frozen; no selector is called',
            skipped_ids=[c['id'] for c in trace['eligible'] if c['id'] not in {p['chunk_id'] for p in passages}])
        contract['contract_sha256']=fmt.digest(fmt.canonical(contract))
        return contract
    traces=[t for t in read(run/'retrieval-traces.json') if t['arm'] in ('B','C')]
    if len(traces)!=120 or len({t['question_id'] for t in traces})!=60:raise ValueError('Expected 60 B/C K10 contexts')
    for trace in traces:
        if (trace['k'],trace['budget'],trace['policy'])!=(10,1000,'ranked_fill'):raise ValueError('Unexpected native settings')
        contracts.append(make(trace,trace['selected'],trace['context'],'primary-selected'))
    # A fixed, already-saved oversized whole-chunk witness, not re-selection.
    old=next(r for r in read(PARENT/'analysis-v3/per-question.json') if r['question_id']=='P03-en' and r['configuration']=='B/K10')
    trace=next(t for t in traces if t['question_id']=='P03-en' and t['arm']=='B')
    selected=[trace['eligible'][i] for i in old['whole_chunk_oracle']['min_complete_indices']]
    diagnostic=RAGPipeline(None,None,max_context_tokens=1_000_000)._build_context(
        [(chunks['legacy',c['id']],c['cosine']) for c in selected])[0]
    if (len(diagnostic)+3)//4!=3699:raise ValueError('Historical diagnostic minimum differs')
    contracts.append(make(trace,selected,diagnostic,'diagnostic-whole-oracle'))
    output.mkdir(parents=True)
    write(output/'contracts.json',contracts)
    write(output/'sources.json',{key:asdict(s) for key,s in sources.items()})
    write(output/'initial-state.json',initial)
    write(output/'input-integrity.json',receipts)
    write(output/'study-config.json',config)
    write(output/'provenance.json',dict(questions=60,primary_rows=120,diagnostic_rows=1,labels_read=False,rubric_read=False,
        saved_answers_read=False,source_loader_embed=False,selection_calls=0,retrieval_calls=0,embedding_calls=0,network_calls=0,
        corpus_chunks_reconstructed=len(chunks),no_source_body_deduplication=True,no_budget_repacking=True))
    seal(output,[p.name for p in output.iterdir() if p.is_file()])
    print(dict(output=str(output),primary=120,diagnostic=1,protected_files=len(initial['protected_files'])),flush=True)


def load_frames(inputs):
    verify_manifest(inputs,'integrity.json',sha(inputs/'integrity.json'))
    sources={key:fmt.Source(**value) for key,value in read(inputs/'sources.json').items()}
    frames=[]
    for record in read(inputs/'contracts.json'):
        approved=dict(record);contract_hash=approved.pop('contract_sha256')
        if fmt.digest(fmt.canonical(approved))!=contract_hash:raise ValueError('Fixed-body contract changed')
        passages=[]
        for p in record['passages']:
            fields={k:v for k,v in p.items() if k not in ('original_mapping','original_candidate_rank')}
            fields['ranges']=tuple(tuple(r) for r in fields['ranges'])
            fields['restricted']=tuple(fields['restricted'])
            passages.append(fmt.Passage(**fields))
        frame=fmt.FixedContext(tuple(sources[k] for k in record['source_keys']),tuple(passages),
            tuple(p.binding for p in passages),contract_hash,record['historical_context'])
        fmt.serialize(frame,'S0')
        frames.append((record,frame))
    return frames


def collect(inputs, freeze_path, output):
    if output.exists():raise ValueError('Fresh collection output required')
    frozen=read(freeze_path)
    if (frozen['serializer_sha256']!=sha(fmt.__file__) or frozen['version']!=fmt.VERSION
            or frozen['input_manifest_sha256']!=sha(inputs/'integrity.json')):
        raise ValueError('Pre-evaluation format/input freeze changed')
    frames=load_frames(inputs)
    rows=[];timings=[]
    for record,frame in frames:
        encoded={variant:fmt.serialize(frame,variant) for variant in fmt.VARIANTS}
        for variant,item in encoded.items():
            if variant in ('S2','S3'):fmt.decode_grouped(frame,item)
            body_chars=sum(len(p.body) for p in frame.passages)
            rows.append(dict(question_id=record['question_id'],family_id=record['family_id'],language=record['language'],arm=record['arm'],kind=record['kind'],
                variant=variant,contract_sha256=frame.contract_sha256,context=item.context,body_positions=item.body_positions,
                source_aliases=item.source_aliases,tokens=item.tokens,chars=len(item.context),body_chars=body_chars,
                overhead_chars=len(item.context)-body_chars,
                enclosing_tokens=(len(scope_section(record['scope'],item.context))+3)//4,
                sources=len(frame.sources),fragments=len(frame.passages),
                original_tokens=(len(frame.historical_context)+3)//4,
                fixed_token_savings=(len(frame.historical_context)+3)//4-item.tokens,
                unused_headroom_tokens=max(0,1000-item.tokens),over_scope_budget=item.tokens>1000,
                over_overall_budget=(len(scope_section(record['scope'],item.context))+3)//4>8000,
                body_sha256s=[p.body_sha256 for p in frame.passages],source_ranges=[p.ranges for p in frame.passages],
                selected_ids=[p.chunk_id for p in frame.passages],
                restricted_exposure=sorted({rid for p in frame.passages for rid in p.restricted}),
                repeated_registry_control_chars=item.repeated_source_header_chars,
                repeated_source_identity_fields=max(0,len(frame.passages)-len(frame.sources))*(0 if variant in ('S2','S3') else 1),
                body_identity=True,range_identity=True,revision_identity=True,ownership_failures=0,
                continuity='Explicit independent/length-framed passages' if variant in ('S2','S3') else 'Historical boundaries; source offsets/version pins require sidecar',
                completeness_change_claimed=False))
        samples={v:[] for v in fmt.VARIANTS}
        for repeat in range(20):
            order=list(fmt.VARIANTS[repeat%4:]+fmt.VARIANTS[:repeat%4])
            if repeat%2:order.reverse()
            for variant in order:
                tick=time.perf_counter_ns();fmt.serialize(frame,variant)
                samples[variant].append((time.perf_counter_ns()-tick)/1_000_000)
        timings.append(dict(question_id=record['question_id'],arm=record['arm'],kind=record['kind'],samples_ms=samples))
    output.mkdir(parents=True)
    write(output/'serialized-contexts.json',rows)
    write(output/'latency.json',timings)
    write(output/'provenance.json',dict(version=fmt.VERSION,serializer_sha256=sha(fmt.__file__),runner_sha256=sha(__file__),
        freeze_sha256=sha(freeze_path),input_manifest_sha256=sha(inputs/'integrity.json'),
        labels_read=False,rubric_read=False,answers_read=False,selection_calls=0,retrieval_calls=0,embedding_calls=0,network_calls=0,
        primary_rows=480,diagnostic_rows=4,repetitions=20,no_body_deduplication=True,no_source_extraction=True,no_repacking=True,
        timing='Warm validation+serialization only, excluding immutable source construction/file/hash loading; cyclic/reversed order'))
    seal(output,[p.name for p in output.iterdir() if p.is_file()])
    print(dict(output=str(output),rows=len(rows),body_identity=True,range_identity=True),flush=True)


def score(inputs, delivery, output):
    if output.exists():raise ValueError('Fresh scoring output required')
    from laew.eval.scoring_calibration import validate_atoms,score_evidence
    from laew.eval.retrieval_budget_diagnostics import subtract_regions
    verify_manifest(delivery,'integrity.json',sha(delivery/'integrity.json'))
    config=read(inputs/'study-config.json')
    rubric_root=Path(config['rubric'])
    verify_manifest(rubric_root,'rubric-manifest-v2.1.json',config['rubric_sha'])
    verify_manifest(rubric_root,'artifact-integrity.json',config['calibration_sha'])
    rubric=read(rubric_root/'rubric-v2.1.json')['families'];atoms=read(rubric_root/'source-atoms-v2.1.json')
    frames={(r['question_id'],r['arm'],r['kind']):(r,f) for r,f in load_frames(inputs)}
    units={u['id']:u for u in read(Path(config['corpus'])/'corpus/source-manifest.json')['source_units']}
    texts={sid:(Path(config['corpus'])/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for sid,u in units.items()}
    validate_atoms(atoms,texts,units)
    regions=read(Path(config['corpus'])/'review/r3d/restricted-regions.json')['regions']
    # Only ordinary frozen family category is used for strata, after collection.
    categories={}
    for dataset in config['datasets']:
        root=Path(dataset['path']);verify_manifest(root,'dataset-integrity.json',dataset['sha256'])
        categories.update({f['id']:f['category'] for f in read(root/'families.json')})
    rows=[]
    for row in read(delivery/'serialized-contexts.json'):
        record,frame=frames[row['question_id'],row['arm'],row['kind']]
        encoded=fmt.serialize(frame,row['variant'])
        if encoded.context!=row['context']:raise ValueError('Delivered serializer output drift')
        # Verify the actual serialized range/source ownership, not just a copy
        # of expected metadata, before feeding the unchanged frozen scorer.
        if row['variant'] in ('S2','S3'):
            decoded=fmt.decode_grouped(frame,encoded)
            actual=[dict(source_id=r[3]['id'],source_ranges=r[2]) for r in decoded]
        else:
            actual=[dict(source_id=next(s.source_id for s in frame.sources if s.key==p.source_key),source_ranges=p.ranges) for p in frame.passages]
        cov=subtract_regions(coverage_of(actual),regions)
        family=rubric[record['family_id']]
        evidence=score_evidence(family,atoms,cov,texts)
        original_cov=subtract_regions(coverage_of([dict(source_id=next(s.source_id for s in frame.sources if s.key==p.source_key),source_ranges=p.ranges) for p in frame.passages]),regions)
        if evidence!=score_evidence(family,atoms,original_cov,texts):raise ValueError('Evidence changed under fixed-body serialization')
        rows.append(dict(**row,answerable=family['positive_recall_applicable'],category=categories[record['family_id']],
            source_groups=sorted({units[s.source_id]['family'] for s in frame.sources}),
            calibrated_evidence=evidence,requirement_gains=[],requirement_losses=[],critical_support_changed=False,
            semantic_limits='No generated answer or independent domain validation; P03/S12 boundaries remain as selected'))
    output.mkdir(parents=True)
    write(output/'per-question.json',rows)
    write(output/'provenance.json',dict(delivery_manifest_sha256=sha(delivery/'integrity.json'),
        scorer_sha256=sha(sys.modules['laew.eval.scoring_calibration'].__file__),runner_sha256=sha(__file__),
        selection_calls=0,retrieval_calls=0,embedding_calls=0,network_calls=0,generation_calls=0,
        all_evidence_scores_unchanged=True,all_requirement_gains_losses_empty=True,independent_domain_validation=False))
    seal(output,[p.name for p in output.iterdir() if p.is_file()])
    print(dict(output=str(output),scores=len(rows),all_unchanged=True),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','collect','score'))
    parser.add_argument('--package',type=Path)
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--delivery',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with offline():
        if args.mode=='prepare':prepare(args.package,args.output)
        elif args.mode=='collect':collect(args.inputs,args.freeze,args.output)
        else:score(args.inputs,args.delivery,args.output)


if __name__=='__main__':main()
