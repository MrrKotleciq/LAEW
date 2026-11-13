"""Task 3B isolated actual-Chroma quality, context and cost benchmark."""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from collections import defaultdict
import hashlib
import math
from pathlib import Path
import statistics
import tempfile
import time
import tracemalloc
from urllib.parse import urlparse
from types import SimpleNamespace

from laew.eval.lexical_benchmark import read, write, digest, hydrate, record, DenseIndex, stats, rss
from laew.eval.reranker_benchmark import atom_present, scoped_ranking_metrics, replay
from laew.rag.evidence_selection import SelectionConfig, select_ranked_scopes
from laew.rag.hierarchical_experiment import Binding, Snapshot, ChromaDrillDown, UnsafeEvidence


def prepare(corpus):
    if corpus['content_hash'] != digest(corpus['conditions']):
        raise ValueError('Original corpus cache changed')
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.manifest import load_manifest
    from laew.runtime import build_embedding_service
    embedding = build_embedding_service(load_manifest('manifests/SYSTEM_MANIFEST.yaml'))
    if (urlparse(embedding.base_url).hostname not in ('127.0.0.1','localhost','::1') or
            embedding.model != corpus['embedding_model'] or embedding.dimensions != corpus['dimensions']):
        raise ValueError('Existing local embedding configuration required')
    root = Path('tests/rag/hierarchical_long_v1')
    freeze = read(root/'FREEZE.json')
    for file, sha in freeze['sha256'].items():
        if hashlib.sha256((root/file).read_bytes()).hexdigest() != sha:
            raise ValueError('Authored fixture changed after freeze')
    conditions = deepcopy(corpus['conditions'])
    legacy = next(c for c in conditions if c['dataset_directory']=='stress_1036')
    supplement = next(c for c in conditions if c['dataset_directory']=='evidence_supplement_v1' and c['chunking']['strategy']=='structure-v2')
    v2 = {**legacy, 'chunking': {'strategy':'structure-v2'}, 'chunks':
          [deepcopy(r) for r in supplement['chunks'] if r['source']=='global' and r['path']=='atlas.md'] +
          [deepcopy(r) for r in legacy['chunks'] if r['path']!='atlas.md']}
    v2['note']='1035 chunks: same 1024 distractors plus 11 existing structure-v2 Atlas leaves; no new embeddings.'
    conditions.append(v2)
    for original in (legacy,v2):
        grouped=deepcopy(original)
        grouped['dataset_directory']='stress_grouped'
        grouped['note']='Same vectors/text; 1024 distractor leaves grouped into 16 documents of 64 leaves.'
        for r in grouped['chunks']:
            if r['id'].startswith('stress-'):
                number=int(r['id'].split('-')[1])
                r['metadata']['control_original_path']=r['path']
                r['path']=f'stress-grouped/{number//64}.md'
        conditions.append(grouped)
    dataset=read(root/'dataset.json')
    cached={r['text']:r['embedding'] for c in corpus['conditions'] for r in c['chunks']}
    cached.update({q['query']['text']:q['embedding'] for c in corpus['conditions'] for q in c['queries']})
    authored=[]
    for strategy in ('legacy','structure-v2'):
        kb=KnowledgeBase(str(root/'project'),str(root/'global'),embedding,
                         vector_store_config={'enabled':False},chunking_strategy=strategy)
        chunks=[record(c) for scope in ('global','project') for p in sorted((root/scope).glob('*.md'))
                for c in kb._load_file(p,scope,root/scope,embed=False)]
        authored.append({'dataset_directory':'hierarchical_long_v1','chunking':{'strategy':strategy},
                         'chunks':chunks,'queries':[{'query':q} for q in dataset['queries']],
                         'document_languages':dataset['document_languages'],'judgment':dataset['judgment']})
    missing=list(dict.fromkeys([r['text'] for c in authored for r in c['chunks']] + [q['text'] for q in dataset['queries']]))
    missing=[text for text in missing if text not in cached]
    started=time.perf_counter()
    for offset in range(0,len(missing),16):
        batch=missing[offset:offset+16]
        vectors=embedding.embed_batch(batch)
        if len(vectors)!=len(batch):
            raise RuntimeError('Incomplete embedding response')
        cached.update(zip(batch,vectors))
        print(f'Authored fixture initialization {min(offset+16,len(missing))}/{len(missing)}',flush=True)
    for c in authored:
        for r in c['chunks']:
            r['embedding']=cached[r['text']]
        for q in c['queries']:
            q['embedding']=cached[q['query']['text']]
            q['index_atom_available']=[any(atom_present(a,hydrate(r)) for r in c['chunks']) for a in q['query']['evidence']]
    conditions.extend(authored)
    return {'protocol':'hierarchical-task3b-v1','original_corpus_hash':corpus['content_hash'],
            'content_hash':digest(conditions),'conditions':conditions,'embedding_model':embedding.model,
            'dimensions':embedding.dimensions,'authored_fixture_freeze':freeze,
            'initialization':{'new_unique_text_embeddings':len(missing),'seconds':time.perf_counter()-started,
                              'retrieval_additional_query_embeddings':0}}


class FrozenLease:
    """Immutable fixture generation; mutations are exercised separately in tests."""
    def __init__(self,generation):
        self.generation=generation
        self.current=generation
    @contextmanager
    def lease(self):
        def check():
            if self.current != self.generation:
                raise UnsafeEvidence('Fixture generation changed')
        check()
        yield check
        check()


def metrics(query,pools):
    return scoped_ranking_metrics(query,sorted(pools.items()),10)


def evaluate(condition,adapters,method,overall_budget):
    rows=[]
    for item in condition['queries']:
        q=item['query']
        scopes=('global','project') if q['allowed_scope']=='hybrid' else (q['allowed_scope'],)
        pools,diagnostics={},{}
        seed_ids={}
        started=time.perf_counter()
        for scope in scopes:
            result=adapters[scope].retrieve(item['embedding'],hierarchical=method=='hierarchical')
            pools[scope]=result.pairs
            diagnostics[scope]=result.diagnostics
            seed_ids[scope]=[c.chunk_id for c,_ in result.seeds]
        retrieval_ms=(time.perf_counter()-started)*1000
        candidate=metrics(q,pools)
        started=time.perf_counter()
        selected,context=select_ranked_scopes(pools,SelectionConfig(policy='ranked_fill',budget=1000),overall_budget)
        selection_ms=(time.perf_counter()-started)*1000
        final_pools={s:r.chunks for s,r in selected.items()}
        received,system_tokens=replay(q,[(s,r.context) for s,r in sorted(selected.items())])
        final=metrics(q,final_pools)
        relevant={d for d,g in q['relevance'].items() if g>0}
        used=[c for pairs in final_pools.values() for c,_ in pairs]
        document=lambda c:('@knowledge/' if c.source=='global' else '@project/')+c.file_path.replace('\\','/')
        rows.append({'dataset':condition['dataset_directory'],'chunker':condition['chunking']['strategy'],
                     'query_id':q['id'],'method':method,'no_answer':bool(q['no_answer']),'language':q['language'],
                     'multi_document':len(q['expected_document_ids'])>1,
                     'cross_language':any(condition.get('document_languages',{}).get(d) not in (None,q['language']) for d in q['expected_document_ids']),
                     'candidate':candidate,'final':final,'diagnostics':diagnostics,
                     'seed_ids':seed_ids,
                     'candidate_ids':{s:[c.chunk_id for c,_ in pairs] for s,pairs in pools.items()},
                     'candidate_documents':{s:[document(c) for c,_ in pairs] for s,pairs in pools.items()},
                     'selected_ids':{s:[c.chunk_id for c,_ in r.chunks] for s,r in selected.items()},
                     'tokens':math.ceil(len(context)/4),'per_scope_tokens':{s:r.estimated_tokens for s,r in selected.items()},
                     'fragments':len(used),'irrelevant_fragments':sum(document(c) not in relevant for c in used),
                     'no_atom_fragments':sum(not any(atom_present(a,c) for a in q['evidence']) for c in used),
                     'adapter_received':received,'adapter_system_tokens':system_tokens,
                     'allocation_compliant':math.ceil(len(context)/4)<=overall_budget and all(r.estimated_tokens<=1000 for r in selected.values()),
                     'retrieval_ms_single':retrieval_ms,'selection_ms_single':selection_ms,
                     'index_atom_available':item['index_atom_available']})
    return rows


def summarize(rows):
    groups=defaultdict(list)
    for row in rows:
        groups[row['dataset'],row['chunker'],row['method']].append(row)
    summaries=[]
    for key,group in sorted(groups.items()):
        answered=[r for r in group if not r['no_answer']]
        mean=lambda values:statistics.mean(values) if values else None
        summary=dict(zip(('dataset','chunker','method'),key)) | {'queries':len(group),'answerable':len(answered)}
        for stage in ('candidate','final'):
            summary[stage+'_coverage']=mean([r[stage]['evidence_coverage'] for r in answered])
            summary[stage+'_complete']=mean([r[stage]['complete_evidence'] for r in answered])
            summary[stage+'_document_recall']=mean([r[stage]['document_recall'] for r in answered])
        summary.update(tokens=stats([r['tokens'] for r in group]),fragments=stats([r['fragments'] for r in group]),
                       irrelevant_rate=sum(r['irrelevant_fragments'] for r in group)/max(1,sum(r['fragments'] for r in group)),
                       no_atom_rate=sum(r['no_atom_fragments'] for r in group)/max(1,sum(r['fragments'] for r in group)),
                       unsupported_empty=mean([r['final']['no_answer_empty'] for r in group if r['no_answer']]),
                       fallback_scopes=sum(bool(d['fallback']) for r in group for d in r['diagnostics'].values()),
                       adapter_received=all(r['adapter_received'] for r in group),allocation_compliant=all(r['allocation_compliant'] for r in group))
        summary['subsets']={name:{'n':len(subset),'candidate_coverage':mean([r['candidate']['evidence_coverage'] for r in subset]),
                                 'final_coverage':mean([r['final']['evidence_coverage'] for r in subset]),
                                 'final_complete':mean([r['final']['complete_evidence'] for r in subset])}
                            for name in ('multi_document','cross_language') if (subset:=[r for r in answered if r[name]])}
        summaries.append(summary)
    return summaries


def comparisons(rows):
    lookup={(r['dataset'],r['chunker'],r['query_id'],r['method']):r for r in rows}
    output=[]
    for row in rows:
        if row['method']!='hierarchical' or row['no_answer']:
            continue
        baseline=lookup[row['dataset'],row['chunker'],row['query_id'],'dense']
        for stage in ('candidate','final'):
            before,after=(r[stage]['evidence_positions'] for r in (baseline,row))
            gain=[i for i,(a,b) in enumerate(zip(before,after)) if a is None and b is not None]
            loss=[i for i,(a,b) in enumerate(zip(before,after)) if a is not None and b is None]
            worse=[i for i,(a,b) in enumerate(zip(before,after)) if a is not None and b is not None and b>a]
            if gain or loss or worse:
                output.append({k:row[k] for k in ('dataset','chunker','query_id','multi_document','cross_language')} |
                              {'stage':stage,'recovered_atoms':gain,'lost_atoms':loss,'ranking_worse_atoms':worse,
                               'before':before,'after':after,'routing':row['diagnostics']})
    return output


def exact_diagnostics(corpus, rows):
    """Offline comparator only; never supplies candidates to either method."""
    import numpy as np
    output=[]
    lookup={(r['dataset'],r['chunker'],r['query_id'],r['method']):r for r in rows}
    for condition in corpus['conditions']:
        if condition['dataset_directory'] not in ('stress_1036','stress_grouped'):
            continue
        records=condition['chunks']
        matrix=np.asarray([r['embedding'] for r in records],dtype=np.float64)
        matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
        for item in condition['queries']:
            vector=np.asarray(item['embedding'],dtype=np.float64)
            scores=matrix@(vector/np.linalg.norm(vector))
            order=sorted(range(len(records)),key=lambda i:(-scores[i],records[i]['id']))
            pairs=[(hydrate(records[i]),float(scores[i])) for i in order if scores[i]>=.3]
            q=item['query']
            native=lookup[condition['dataset_directory'],condition['chunking']['strategy'],q['id'],'dense']
            output.append({'dataset':condition['dataset_directory'],'chunker':condition['chunking']['strategy'],
                           'query_id':q['id'],'exact_atom_ranks':scoped_ranking_metrics(q,[('global',pairs)],None)['evidence_positions'],
                           'exact_top10_ids':[c.chunk_id for c,_ in pairs[:10]],
                           'native_top10_ids':native['candidate_ids']['global'],
                           'native_overlap_exact_top10':len(set(native['candidate_ids']['global']) & {c.chunk_id for c,_ in pairs[:10]})})
    return output


def benchmark(corpus,repeats=20,overall_budget=8000):
    if corpus['content_hash']!=digest(corpus['conditions']):
        raise ValueError('Corpus cache changed')
    rows,performance,resources=[],[],[]
    with tempfile.TemporaryDirectory(prefix='laew-hierarchical-') as scratch:
        # The grouped control updates metadata in THE SAME native vector graph.
        # Rebuilding an approximate index would confound layout with ANN variance.
        conditions=[c for c in corpus['conditions'] if c['dataset_directory']!='stress_grouped']
        for number,condition in enumerate(conditions):
            name,strategy=condition['dataset_directory'],condition['chunking']['strategy']
            adapters,indexes={},[]
            before=rss()
            started=time.perf_counter()
            try:
                registry_bytes=0
                registry_build_ms=0
                registry_python_peak=0
                for scope in ('global','project'):
                    records=[r for r in condition['chunks'] if r['source']==scope]
                    index=DenseIndex(Path(scratch)/f'{number}-{scope}',SimpleNamespace(scope=scope))
                    indexes.append(index)
                    index.rebuild(records)
                    binding=Binding(str(index.store._collection.id),scope,str(Path(scratch)/'project') if scope=='project' else None)
                    registry_start=time.perf_counter()
                    tracemalloc.start()
                    snapshot=Snapshot.build(binding,corpus['content_hash'],[hydrate(r) for r in records])
                    _,registry_peak=tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    registry_python_peak+=registry_peak
                    registry_build_ms+=(time.perf_counter()-registry_start)*1000
                    registry_bytes+=len(str(snapshot).encode())
                    lease=FrozenLease(snapshot.generation)
                    adapters[scope]=ChromaDrillDown(index.store._collection,snapshot,lease.lease)
                build_ms=(time.perf_counter()-started)*1000
                built=rss()
                views=[condition]
                if name=='stress_1036':
                    views.append(next(c for c in corpus['conditions'] if c['dataset_directory']=='stress_grouped' and c['chunking']['strategy']==strategy))
                for view in views:
                    current_adapters=adapters
                    view_name=view['dataset_directory']
                    if view_name=='stress_grouped':
                        # Metadata-only updates retain the original HNSW graph.
                        import json
                        index=indexes[0]
                        original=index.store._collection.get(include=['metadatas'])
                        by_id={r['id']:r for r in view['chunks']}
                        metas=[]
                        for id_,meta in zip(original['ids'],original['metadatas']):
                            r=by_id[id_]
                            meta['file_path']=r['path']
                            if 'control_original_path' in r['metadata']:
                                meta['control_original_path']=json.dumps(r['metadata']['control_original_path'])
                            metas.append(meta)
                        index.store._collection.update(ids=original['ids'],metadatas=metas)
                        snapshot=Snapshot.build(adapters['global'].snapshot.binding,corpus['content_hash'],[hydrate(r) for r in view['chunks']])
                        current_adapters={'global':ChromaDrillDown(index.store._collection,snapshot,FrozenLease(snapshot.generation).lease)}
                    for method in ('dense','hierarchical'):
                        rows.extend(evaluate(view,current_adapters,method,overall_budget))
                    if view_name in ('reranker_holdout_v1','stress_1036','stress_grouped','hierarchical_long_v1'):
                        # First three queries, independent of labels/outcomes.
                        for item in view['queries'][:3]:
                            scopes=('global','project') if item['query']['allowed_scope']=='hybrid' else (item['query']['allowed_scope'],)
                            for method in ('dense','hierarchical'):
                                operation=lambda:[current_adapters[s].retrieve(item['embedding'],hierarchical=method=='hierarchical') for s in scopes]
                                operation()
                                samples=[]
                                for _ in range(repeats):
                                    tick=time.perf_counter(); result=operation(); samples.append((time.perf_counter()-tick)*1000)
                                tracemalloc.start(); operation(); _,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
                                performance.append({'dataset':view_name,'chunker':strategy,'query_id':item['query']['id'],'method':method,
                                                    'latency_ms':stats(samples),'python_peak_bytes':peak,
                                                    'calls':sum(r.diagnostics['chroma_calls'] for r in result),
                                                    'bytes':sum(r.diagnostics['fetched_metadata_bytes'] for r in result),
                                                    'records':sum(r.diagnostics['fetched_records'] for r in result)})
                resources.append({'dataset':name,'chunker':strategy,'chunks':len(condition['chunks']),
                                  'registry_serialized_repr_bytes':registry_bytes,'index_and_registry_build_ms':build_ms,
                                  'registry_build_ms_traced':registry_build_ms,'registry_python_peak_bytes':registry_python_peak,
                                  'rss_before':before,'rss_after_build':built,'rss_after_warm':rss(),
                                  'index_bytes':sum(p.stat().st_size for index in indexes for p in index.path.rglob('*') if p.is_file())})
            finally:
                for index in indexes:
                    index.close()
            print(f'Evaluated {name}/{strategy}',flush=True)
    lookup={(r['dataset'],r['chunker'],r['query_id'],r['method']):r for r in rows}
    for row in rows:
        if row['method']=='hierarchical':
            assert row['seed_ids']==lookup[row['dataset'],row['chunker'],row['query_id'],'dense']['seed_ids'], 'A/B seed drift'
        if row['dataset']=='stress_grouped':
            assert row['seed_ids']==lookup['stress_1036',row['chunker'],row['query_id'],row['method']]['seed_ids'], 'Control changed native seed ranking'
    return {'protocol':'hierarchical-task3b-v1','corpus_hash':corpus['content_hash'],'repeats':repeats,
            'quality_backend':'Actual isolated PersistentClient Chroma; production metadata serializer; cached vectors.',
            'performance_boundary':'Warm local retrieval + payload validation; excludes shared embedding, index build, selector and adapter. Bytes are serialized result metadata, not network traffic.',
            'rows':rows,'summary':summarize(rows),'comparisons':comparisons(rows),'performance':performance,'resources':resources,
            'exact_stress_diagnostics':exact_diagnostics(corpus,rows),
            'controls':{'same_seeds_both_methods':True,'grouped_control_same_native_seed_ids':True}}


def export_report(result, previous, output):
    """Reproducible compact artifacts, including prior native D10 sensitivity."""
    import csv
    prior={(r['dataset'],r['chunker'],r['query_id']):r for r in previous['rows']
           if r['backend']=='dense_eligible' and r['k']==10}
    differences=[]
    checked=0
    for row in result['rows']:
        key=row['dataset'],row['chunker'],row['query_id']
        if row['method']!='dense' or key not in prior:
            continue
        checked+=1
        expected={s:[h['id'] for h in prior[key]['hits'] if h['source']==s] for s in row['candidate_ids']}
        if expected!=row['candidate_ids']:
            differences.append({k:row[k] for k in ('dataset','chunker','query_id')} |
                               {'prior':expected,'current':row['candidate_ids'],
                                'prior_coverage':prior[key]['metrics']['evidence_coverage'],
                                'current_coverage':row['candidate']['evidence_coverage']})
    prefix=output.stem.removesuffix('-summary')
    write(output.with_name(prefix+'-controls.json'),{'same_seeds_controls':result['controls'],
          'prior_pairs_checked':checked,'prior_native_d10_differences':differences})
    write(output.with_name(prefix+'-regressions.json'),result['comparisons'])
    flat=[{**{k:r[k] for k in ('dataset','chunker','query_id','method','language','multi_document','cross_language',
                              'no_answer','tokens','fragments','irrelevant_fragments','no_atom_fragments')},
           'candidate_coverage':r['candidate']['evidence_coverage'],'candidate_complete':r['candidate']['complete_evidence'],
           'final_coverage':r['final']['evidence_coverage'],'final_complete':r['final']['complete_evidence'],
           'calls':sum(d['chroma_calls'] for d in r['diagnostics'].values()),
           'bytes':sum(d['fetched_metadata_bytes'] for d in r['diagnostics'].values())} for r in result['rows']]
    with output.with_name(prefix+'-queries.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
    return {k:v for k,v in result.items() if k not in ('rows','comparisons','performance')} | {
        'row_count':len(result['rows']),'adapter_replays':sum(r['adapter_received'] for r in result['rows']),
        'allocation_violations':sum(not r['allocation_compliant'] for r in result['rows']),
        'max_scope_candidates':max(len(ids) for r in result['rows'] for ids in r['candidate_ids'].values()),
        'max_scope_tokens':max(v for r in result['rows'] for v in r['per_scope_tokens'].values())}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=('prepare','benchmark','export'))
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=20)
    parser.add_argument('--retrieval',type=Path)
    args=parser.parse_args()
    corpus=read(args.corpus)
    if args.phase=='export':
        result=export_report(corpus,read(args.retrieval),args.output)
    elif args.phase=='prepare':
        result=prepare(corpus)
    else:
        from laew.manifest import load_manifest
        from laew.runtime import context_budget_from_manifest
        result=benchmark(corpus,args.repeats,context_budget_from_manifest(load_manifest('manifests/SYSTEM_MANIFEST.yaml')).rag)
    write(args.output,result)
    print(f'Saved {args.output}',flush=True)


if __name__=='__main__':
    main()
