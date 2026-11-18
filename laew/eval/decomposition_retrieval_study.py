"""Frozen multi-query retrieval collection and separate reference evaluation."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import statistics
import time

from laew.eval.complementary_context_study import load_inputs, offline, read, seal, sha, support, verify_manifest, write
from laew.eval.fine_evidence_study import PARENT,PARENT_SHA
from laew.eval.question_decomposition import merge_ranked,search_allocations
from laew.eval.retrieval_budget_diagnostics import FrozenVectors,encode,subtract_regions


def collect(package, output):
    if output.exists():raise ValueError('Fresh output required')
    config=read(package/'study-config.json')
    verify_manifest(PARENT,'artifact-integrity.json',PARENT_SHA)
    for folder in ('decomposition','embeddings-authorized'):
        verify_manifest(package/folder,'integrity.json',sha(package/folder/'integrity.json'))
    from laew.eval import question_decomposition as mechanism
    if sha(mechanism.__file__)!=read(package/'decomposition/freeze.json')['mechanism_sha256']:
        raise ValueError('Question-only mechanism changed since freeze')
    data=load_inputs(config,scoring=False)
    plans=read(package/'decomposition/question-only-plans.json')
    old=FrozenVectors(Path(config['run'])/'vector-cache.sqlite3',read(Path(config['run'])/'run-metadata.json'))
    newmeta=read(package/'embeddings-authorized/metadata.json')
    new=FrozenVectors(package/'embeddings-authorized/query-vectors.sqlite3',newmeta)
    vectors={}
    try:
        for plan in plans:
            for i,query in enumerate(plan['queries']):
                vectors[query]=(old if i==0 else new).get(query)
    finally:old.close();new.close()
    output.mkdir(parents=True)
    copied=output/'disposable-index'
    original=Path(config['run'])/'chroma'
    shutil.copytree(original,copied)
    if any(sha(p)!=sha(copied/p.relative_to(original)) for p in original.rglob('*') if p.is_file()):
        raise ValueError('Disposable index differs before opening')
    import chromadb
    from chromadb.config import Settings
    from laew.rag.vector_store import ChromaVectorStore
    client=chromadb.PersistentClient(path=str(copied),settings=Settings(anonymized_telemetry=False))
    memo={};search_receipts=[];rows=[];controls=[];logical=0
    for strategy,arm in [('legacy','B'),('structure-v2','C')]:
        collection=client.get_collection('real-world-'+strategy,embedding_function=None)
        if collection.metadata.get('hnsw:space')!='cosine':raise ValueError('Metric changed')
        store=object.__new__(ChromaVectorStore);store._collection=collection;store.source='global'
        def search(query,k):
            nonlocal logical
            logical+=1;key=(arm,query,k)
            if key not in memo:
                tick=time.perf_counter()
                first=store.search(vectors[query].tolist(),top_k=k,source_filter='global')
                seconds=time.perf_counter()-tick
                second=store.search(vectors[query].tolist(),top_k=k,source_filter='global')
                if first!=second:raise ValueError('Repeated native ranking is unstable')
                from laew.rag.evidence_selection import Candidate
                memo[key]=[encode(Candidate(data['chunks'][strategy,c.chunk_id],score),strategy,data) for c,score in first]
                search_receipts.append(dict(arm=arm,query=query,k=k,seconds=seconds,repeated_equal=True))
            return memo[key]
        for plan in plans:
            qid=plan['question_id'];queries=plan['queries']
            for k in (10,20):
                found=search(queries[0],k)
                baseline=next(t for t in read(PARENT/'retrieval/retrieval-traces.json') if t['question_id']==qid and t['arm']==arm and t['k']==k)
                if json.loads(json.dumps(found))!=baseline['raw']:raise ValueError('Original native ranking/source/score drift')
                controls.append(dict(question_id=qid,arm=arm,k=k,native_equal=True))
            for condition,total,counts in [('equal10',10,search_allocations(len(queries),10)),
                                           ('equal20',20,search_allocations(len(queries),20)),
                                           ('expanded20perquery',20*len(queries),[20]*len(queries))]:
                results=[search(q,k) for q,k in zip(queries,counts)]
                merged=merge_ranked(results,total)
                raw=merge_ranked(results,total,threshold=-1)
                rows.append(dict(question_id=qid,family_id=data['questions'][qid]['family_id'],language=plan['language'],
                    arm=arm,strategy=strategy,condition=condition,total_raw_budget=total,
                    original_queries=len(queries),allocations=counts,
                    raw=raw['candidates'],eligible=merged['candidates'],
                    duplicate_slots=merged['duplicates'],filtered_slots=merged['filtered'],
                    search_results=[dict(query_index=i,query=q,raw=r) for i,(q,r) in enumerate(zip(queries,results))]))
    write(output/'retrieval-traces.json',rows)
    write(output/'controls.json',controls)
    write(output/'search-receipts.json',search_receipts)
    write(output/'input-integrity.json',data['receipts'])
    write(output/'provenance.json',dict(labels_read=False,rubric_read=False,answers_read=False,
        query_mechanism_sha256=sha(mechanism.__file__),embedding_calls=0,network_calls=0,
        corpus_embeddings_changed=False,index_original_changed=False,
        new_vectors=41,existing_vectors=60,logical_searches=logical,
        physical_searches=2*len(search_receipts),memo_hits=logical-len(search_receipts),
        native_search_first_seconds=sum(s['seconds'] for s in search_receipts),
        original_control_rows=len(controls),all_original_rankings_equal=True,
        note='Each distinct native search repeated once; timing records first native call only; no inference in collection'))
    seal(output,['retrieval-traces.json','controls.json','search-receipts.json','input-integrity.json','provenance.json'])
    print(read(output/'provenance.json'),flush=True)


def score(package, retrieval, output):
    from laew.eval.scoring_calibration import score_evidence
    from laew.eval.real_world_retrieval import coverage_of
    from laew.eval import source_evidence_oracle as oracle
    from laew.eval.retrieval_budget_diagnostics import oracle_diagnostic
    from laew.rag.pipeline import RAGPipeline
    if output.exists():raise ValueError('Fresh output required')
    verify_manifest(retrieval,'integrity.json',sha(retrieval/'integrity.json'))
    config=read(package/'study-config.json');data=load_inputs(config,scoring=True)
    rules=read(package/'scopes-v3/scope-rules.json')
    if sha(oracle.__file__)!=read(package/'scopes-v3/freeze.json')['oracle_sha256']:
        raise ValueError('Frozen extraction oracle changed')
    baselines={(r['question_id'],r['configuration']):r for r in read(package/'analysis-v3/per-question.json')}
    regions=read(Path(config['corpus'])/'review/r3d/restricted-regions.json')['regions']
    renderer=RAGPipeline(None,None,max_context_tokens=1_000_000)
    old_traces={(t['question_id'],t['configuration']):t for t in read(PARENT/'retrieval/retrieval-traces.json')}
    rows=[]
    for trace in read(retrieval/'retrieval-traces.json'):
        family=data['rubric'][trace['family_id']];atoms=data['atoms'];texts=data['texts']
        cov=subtract_regions(coverage_of(trace['eligible']),regions)
        score=score_evidence(family,atoms,cov,texts)
        supported=support(family,atoms,cov,texts)
        baseline=baselines[trace['question_id'],trace['arm']+'/K'+('10' if trace['condition']=='equal10' else '20')]
        before_cov=None
        # Original candidate support can be recovered from its immutable trace.
        old=old_traces[trace['question_id'],baseline['configuration']]
        old_support=support(family,atoms,subtract_regions(coverage_of(old['eligible']),regions),texts)
        gains=[rid for rid in supported if supported[rid] and not old_support[rid]]
        losses=[rid for rid in supported if old_support[rid] and not supported[rid]]
        extracts={g:oracle.solve(family,atoms,texts,data['units'],trace['eligible'],regions,rules,g) for g in oracle.GRANULARITIES}
        whole=None
        if len(trace['eligible'])<=20:
            costs=[len(renderer._build_context([(data['chunks'][trace['strategy'],c['id']],c['cosine'])])[0]) for c in trace['eligible']]
            whole=oracle_diagnostic(family,atoms,trace['eligible'],texts,costs,regions=regions)
        def exposure(coverage):
            return [r['id'] for r in regions if any(max(a,p['start'])<min(z,p['end'])
                for a,z in coverage.get(r['source_id'],[]) for p in r['component_ranges']+r['related_context_ranges'])]
        scope_sources={atoms[a]['source_id'] for r in family['requirements'] for proof in r['proofs'] for a in proof}
        neighbors=[dict(id=c['id'],source_id=c['source_id']) for c in trace['eligible'] if c['source_id'] not in scope_sources]
        critical=[r['id'] for r in family['requirements'] if r['safety_critical'] and not r.get('contextual')]
        conditions=[r['id'] for r in family['requirements'] if (r['safety_critical'] or r.get('when')) and not r.get('contextual')]
        rows.append(dict(question_id=trace['question_id'],family_id=trace['family_id'],language=trace['language'],arm=trace['arm'],condition=trace['condition'],
            answerable=family['positive_recall_applicable'],baseline_configuration=baseline['configuration'],
            candidate_score=score,candidate_support=supported,baseline_candidate_score=baseline['candidate_score'],
            baseline_whole_chunk_oracle=baseline['whole_chunk_oracle'],baseline_extraction=baseline['extractions'],
            gained_requirements=gains,lost_requirements=losses,
            critical_gained=[rid for rid in gains if rid in critical],critical_lost=[rid for rid in losses if rid in critical],
            condition_gained=[rid for rid in gains if rid in conditions],condition_lost=[rid for rid in losses if rid in conditions],
            missing_critical=[rid for rid in critical if not supported[rid]],missing_conditions=[rid for rid in conditions if not supported[rid]],
            extractions=extracts,whole_chunk_oracle=whole,
            raw_budget=trace['total_raw_budget'],unique_eligible=len(trace['eligible']),
            duplicate_slots=len(trace['duplicate_slots']),threshold_slots=len(trace['filtered_slots']),searches=len(trace['allocations']),
            restricted_candidate=exposure(coverage_of(trace['eligible'])),
            baseline_restricted=exposure(coverage_of(old['eligible'])),
            new_restricted_regions=sorted(set(exposure(coverage_of(trace['eligible'])))-set(exposure(coverage_of(old['eligible'])))),
            unregistered_scope_neighbors=neighbors,
            caveat='Source-neighbor flags do not establish wrong-product/version factual errors; independent semantic/bilingual review pending'))
    output.mkdir(parents=True)
    write(output/'per-question.json',rows)
    summary={}
    for arm in ('B','C'):
        for condition in ('equal10','equal20','expanded20perquery'):
            group=[r for r in rows if r['arm']==arm and r['condition']==condition];positive=[r for r in group if r['answerable']]
            summary[arm+'/'+condition]=dict(answerable=len(positive),candidate_coverage=statistics.mean(r['candidate_score']['positive_recall'] for r in positive),
                candidate_complete=sum(r['candidate_score']['complete'] for r in positive),
                gained_complete=[r['question_id'] for r in positive if r['candidate_score']['complete'] and not r['baseline_candidate_score']['complete']],
                lost_complete=[r['question_id'] for r in positive if r['baseline_candidate_score']['complete'] and not r['candidate_score']['complete']],
                requirements_gained=sum(len(r['gained_requirements']) for r in group),requirements_lost=sum(len(r['lost_requirements']) for r in group),
                critical_gained=sum(len(r['critical_gained']) for r in group),critical_lost=sum(len(r['critical_lost']) for r in group),
                condition_gained=sum(len(r['condition_gained']) for r in group),condition_lost=sum(len(r['condition_lost']) for r in group),
                duplicate_slots=sum(r['duplicate_slots'] for r in group),raw_slots=sum(r['raw_budget'] for r in group),
                unique_eligible=sum(r['unique_eligible'] for r in group),searches=sum(r['searches'] for r in group),
                restricted_questions=sum(bool(r['restricted_candidate']) for r in group),new_restricted=sum(bool(r['new_restricted_regions']) for r in group),
                extraction={g:dict(complete=sum(r['extractions'][g]['complete'] for r in positive),
                    coverage=statistics.mean(r['extractions'][g]['coverage'] for r in positive),
                    gained_complete=[r['question_id'] for r in positive if r['extractions'][g]['complete'] and not r['baseline_extraction'][g]['complete']],
                    lost_complete=[r['question_id'] for r in positive if r['baseline_extraction'][g]['complete'] and not r['extractions'][g]['complete']]) for g in oracle.GRANULARITIES},
                whole_complete=sum(r['whole_chunk_oracle']['complete'] for r in positive) if all(r['whole_chunk_oracle'] is not None for r in positive) else None)
    write(output/'summary.json',summary)
    write(output/'input-integrity.json',data['receipts'])
    write(output/'provenance.json',dict(retrieval_sha256=sha(retrieval/'integrity.json'),runner_sha256=sha(__file__),
        oracle_sha256=sha(oracle.__file__),labels_used_only_for_scoring=True,embedding_calls=0,generation_calls=0,network_calls=0))
    seal(output,['per-question.json','summary.json','input-integrity.json','provenance.json'])
    print({k:{x:v[x] for x in ['candidate_coverage','candidate_complete','gained_complete','lost_complete','whole_complete']} for k,v in summary.items()},flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['collect','score'])
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--retrieval',type=Path)
    args=parser.parse_args()
    with offline():
        if args.mode=='collect':collect(args.package,args.output)
        else:score(args.package,args.retrieval,args.output)


if __name__=='__main__':main()
