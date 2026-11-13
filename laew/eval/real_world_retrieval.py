"""Provisional, isolated real-world retrieval evaluation. No answer generation.

collect reads frozen source documents and questions ONLY. score is a separate
process reading draft labels after the immutable retrieval trace is written.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import statistics
import time
from unittest.mock import patch
import urllib.request
import sys

import numpy as np

ARMS={'A':('legacy',2,'top2',500),'B':('legacy',10,'ranked_fill',1000),'C':('structure-v2',10,'ranked_fill',1000)}


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def check(condition,message):
    if not condition:raise ValueError(message)


def union(ranges):
    result=[]
    for a,z in sorted(ranges):
        if a>=z:continue
        if result and a<=result[-1][1]:result[-1]=(result[-1][0],max(z,result[-1][1]))
        else:result.append((a,z))
    return result


def span_present(span, coverage, texts):
    """Source/version identity plus unioned visible offsets; no text-only hit test."""
    ranges=union(coverage.get(span['source_id'],[]));a,z=span['start'],span['end'];cursor=a
    text=texts[span['source_id']]
    for left,right in ranges:
        if right<=cursor or left>=z:continue
        if left>cursor and text[cursor:min(left,z)].strip():return False
        cursor=max(cursor,min(right,z))
        if cursor>=z:return True
    return not text[cursor:z].strip()


def payload_segments(chunk, mapping, text, length=None):
    """Map primary and actually visible V2 source context, including clipping."""
    limit=len(chunk.text) if length is None else length
    syn=mapping['synthetic_chars'];a,z=mapping['start'],mapping['end'];result=[]
    if limit>syn:result.append([a,min(z,a+limit-syn)])
    prefix=chunk.text[:min(syn,limit)]
    cursor=len('[Related context]\n') if prefix.startswith('[Related context]\n') else len(prefix)
    for left,right in mapping.get('context_spans',[]):
        raw=text[left:right];trim=len(raw)-len(raw.lstrip());value=raw.strip();left+=trim
        if not value:continue
        pos=prefix.find(value[:min(16,len(value))],cursor)
        if pos<0:
            # The production renderer may clip inside the last context phrase.
            # Credit only its exact visible prefix, never annotation characters.
            for short in range(min(15,len(value),len(prefix)-cursor),0,-1):
                candidate=prefix.find(value[:short],cursor)
                if candidate>=0 and candidate+short==len(prefix):pos=candidate;break
        if pos<0:continue
        n=0
        for x,y in zip(prefix[pos:],value):
            if x!=y:break
            n+=1
        if n:result.append([left,left+n]);cursor=pos+n
    if '[Table columns]\n' in prefix:
        # The actual chunker repeats an enclosing table's first two source lines.
        start=prefix.index('[Table columns]\n')+len('[Table columns]\n')
        value=prefix[start:]
        for m in __import__('re').finditer(r'(?m)^\|.*\n\|[- :|]+\n',text):
            header=m[0][:200]
            n=0
            for x,y in zip(value,header):
                if x!=y:break
                n+=1
            if n and a>=m.start() and text[m.end():a].count('\n\n')==0:
                result.append([m.start(),m.start()+n]);break
    return union(result)


def coverage_of(chunks):
    coverage=defaultdict(list)
    for c in chunks:coverage[c['source_id']].extend(c['source_ranges'])
    return {k:union(v) for k,v in coverage.items()}


def score_stage(label,spans,coverage,texts,warning_ids=()):
    if not label['positive_evidence_recall_applicable']:
        return dict(fact_recall=None,complete=None,warning_coverage=None,document_hit_rate=None,facts_hit=[],required_fact_count=0)
    candidates=[]
    for evidence_set in label['minimal_sufficient_evidence_sets']:
        hit=[]
        for fact in label['required_answer_facts']:
            if any(set(alt)<=set(evidence_set) and all(span_present(spans[s],coverage,texts) for s in alt) for alt in fact['evidence_alternatives']):hit.append(fact['id'])
        docs={spans[s]['source_id'] for s in evidence_set}
        docs_hit=sum(bool(coverage.get(d)) for d in docs)
        candidates.append((len(hit),docs_hit/len(docs) if docs else 0,hit,evidence_set))
    check(candidates,'Answerable label lacks sufficient sets')
    _,doc_rate,hit,chosen=max(candidates,key=lambda x:(x[0],x[1]));n=len(label['required_answer_facts'])
    relevant_warnings=set(warning_ids)&{f['id'] for f in label['required_answer_facts']}
    return dict(fact_recall=len(hit)/n,complete=len(hit)==n,warning_coverage=len(set(hit)&relevant_warnings)/len(relevant_warnings) if relevant_warnings else None,
                document_hit_rate=doc_rate,facts_hit=hit,required_fact_count=n,chosen_evidence_set=chosen)


def collect(corpus,questions,questions_sha,out,resume_cache=None):
    # Labels and dataset directories are deliberately not arguments to this mode.
    check(not out.exists(),'New output required; never overwrite traces/indexes')
    check(sha(questions)==questions_sha,'Questions-only trust anchor mismatch')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
    from prepare_real_world_pilot import verify_corpus
    verify_corpus(corpus)
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.rag.vector_store import ChromaVectorStore
    from laew.rag.llamacpp import LlamaCppEmbedding
    from laew.rag.evidence_selection import Candidate,SelectionConfig,select_scopes
    import chromadb
    from chromadb.config import Settings
    catalog=json.load(urllib.request.urlopen('http://127.0.0.1:8081/v1/models',timeout=10))
    model=next((x for x in catalog['data'] if x['id']=='laew-qwen3-embedding'),None)
    check(model and model.get('meta',{}).get('n_embd')==1024,'Embedding identity/dimensions unavailable or mismatched')
    qs=read(questions);check(len(qs)==60 and all('text' in q and 'id' in q for q in qs),'Expected 60 questions only')
    check(all(set(q)<= {'id','family_id','language','text','split'} for q in qs),'Questions input contains unexpected label/metadata fields')
    out.mkdir(parents=True)
    embedding=LlamaCppEmbedding(model='laew-qwen3-embedding',base_url='http://127.0.0.1:8081',target_dimensions=1024,timeout=60)
    resumed_cache_sha=None
    if resume_cache:
        import shutil
        resumed_cache_sha=sha(resume_cache);shutil.copyfile(resume_cache,out/'vector-cache.sqlite3')
    cache=sqlite3.connect(out/'vector-cache.sqlite3');cache.execute('create table if not exists vectors (key text primary key, vector blob)')
    identity=hashlib.sha256(json.dumps(model,sort_keys=True).encode()).hexdigest()
    counters=dict(inputs=0,requests=0,cache_hits=0,embedding_seconds=0.0)
    def vectors(inputs):
        result=[None]*len(inputs);missing={}
        for i,t in enumerate(inputs):
            key=hashlib.sha256((identity+'\0'+t).encode()).hexdigest();row=cache.execute('select vector from vectors where key=?',(key,)).fetchone()
            if row:
                arr=np.frombuffer(row[0],dtype=np.float32)
                check(arr.shape==(1024,) and np.isfinite(arr).all() and np.linalg.norm(arr)>0,'Cached vector is invalid')
                result[i]=arr.tolist();counters['cache_hits']+=1
            else:missing.setdefault(key,dict(text=t,indices=[]))['indices'].append(i)
        pairs=list(missing.items())
        for pos in range(0,len(pairs),8):
            batch=pairs[pos:pos+8];started=time.perf_counter();values=embedding.embed_batch([v['text'] for _,v in batch]);counters['embedding_seconds']+=time.perf_counter()-started
            counters['inputs']+=len(batch);counters['requests']+=1
            for (key,value),vector in zip(batch,values):
                arr=np.array(vector,dtype=np.float32);check(arr.shape==(1024,) and np.isfinite(arr).all() and np.linalg.norm(arr)>0,'Invalid vector')
                cache.execute('insert into vectors values (?,?)',(key,arr.tobytes()))
                for i in value['indices']:result[i]=arr.tolist()
            cache.commit()
            if counters['requests']%10==0:print('Embedded inputs:',counters['inputs'],flush=True)
        return result
    units=read(corpus/'corpus/source-manifest.json')['source_units'];check(len(units)==24,'Wrong source universe')
    check({u['normalized_path'] for u in units}=={'normalized/'+u['id']+'.md' for u in units},'Unexpected input path')
    texts={u['id']:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for u in units}
    client=chromadb.PersistentClient(path=str(out/'chroma'),settings=Settings(anonymized_telemetry=False))
    stores={};all_chunks={};maps={};costs={};indexed_coverage={}
    started_all=time.perf_counter()
    with patch('laew.rag.vector_store._build_chroma_client',return_value=client):
        for strategy,expected in [('legacy',2171),('structure-v2',2185)]:
            started=time.perf_counter();kb=object.__new__(KnowledgeBase);kb.chunk_size=1000;kb.chunk_overlap=200;kb.chunking_strategy=strategy
            chunks=[];mapping={};coverage=defaultdict(list)
            for u in units:
                path=corpus/'corpus'/u['normalized_path'];current=kb._load_file(path,'global',path.parent,content=texts[u['id']],embed=False)
                trace=read(corpus/f'corpus/chunk-maps/{u["id"]}-{strategy}.json')['records'];check(len(current)==len(trace),'Source map/loader count mismatch')
                for c,m in zip(current,trace):
                    check(hashlib.sha256(c.text.encode()).hexdigest()==m['text_sha256'],'Loader payload changed since freeze')
                    mapping[c.chunk_id]=(u['id'],m);coverage[u['id']].extend(payload_segments(c,m,texts[u['id']]))
                chunks.extend(current)
            check(len(chunks)==expected and len(chunks)<3000,'Resource/count gate failed')
            prepare_sec=time.perf_counter()-started
            before_embedding=dict(counters);v=vectors([c.text for c in chunks])
            for c,vector in zip(chunks,v):c.embedding=vector
            store=ChromaVectorStore(host='127.0.0.1',port=1,collection_name='real-world-'+strategy,source='global',embedding_model_id='laew-qwen3-embedding:'+identity)
            started=time.perf_counter()
            for i in range(0,len(chunks),128):store.add_chunks(chunks[i:i+128])
            check(store.count()==expected,'Isolated index count mismatch')
            check({c.file_path for c in store.sync_records('global')}=={Path(u['normalized_path']).name for u in units},'Index source universe differs from the 24 frozen documents')
            stores[strategy]=store;all_chunks[strategy]=chunks;maps[strategy]=mapping
            indexed_coverage[strategy]={k:union(v) for k,v in coverage.items()}
            costs[strategy]=dict(chunks=len(chunks),prepare_seconds=prepare_sec,index_seconds=time.perf_counter()-started,embedding_seconds=counters['embedding_seconds']-before_embedding['embedding_seconds'],embedding_inputs=counters['inputs']-before_embedding['inputs'])
            print('Indexed:',strategy,len(chunks),flush=True)
        before_queries=dict(counters);qv=vectors([q['text'] for q in qs]);rows=[]
        query_costs={k:counters[k]-before_queries[k] for k in counters}
        tokenizer_available=None
        def encode(c,score,mapping):
            sid,m=mapping[c.chunk_id]
            return dict(id=c.chunk_id,source_id=sid,source_sha256=next(u['normalized_sha256'] for u in units if u['id']==sid),cosine=score,text=c.text,source_ranges=payload_segments(c,m,texts[sid],len(c.text)))
        for qi,(q,vector) in enumerate(zip(qs,qv)):
            for arm,(strategy,k,policy,budget) in ARMS.items():
                started=time.perf_counter();raw=stores[strategy].search(vector,top_k=k,source_filter='global');search_ms=(time.perf_counter()-started)*1000
                started=time.perf_counter();selected,enclosing=select_scopes({'global':[Candidate(c,s) for c,s in raw]},SelectionConfig(policy=policy,budget=budget),overall_budget=8000)
                selected=selected['global'];selection_ms=(time.perf_counter()-started)*1000
                check(selected.estimated_tokens<=budget and math.ceil(len(enclosing)/4)<=8000,'Rendered budget exceeded')
                actual_tokens=None
                if tokenizer_available is not False:
                    try:
                        request=urllib.request.Request('http://127.0.0.1:8081/tokenize',data=json.dumps({'content':selected.context,'add_special':False}).encode(),headers={'Content-Type':'application/json'})
                        tokenized=json.load(urllib.request.urlopen(request,timeout=10));actual_tokens=len(tokenized['tokens']);tokenizer_available=True
                    except Exception:tokenizer_available=False
                rows.append(dict(question_id=q['id'],family_id=q['family_id'],language=q['language'],split=q['split'],arm=arm,strategy=strategy,k=k,policy=policy,budget=budget,
                    raw=[encode(c,s,maps[strategy]) for c,s in raw],eligible=[encode(c,s,maps[strategy]) for c,s in raw if s>=.3],selected=[encode(c,s,maps[strategy]) for c,s in selected.chunks],context=selected.context,enclosing_context=enclosing,estimated_tokens=selected.estimated_tokens,enclosing_estimated_tokens=math.ceil(len(enclosing)/4),search_ms=search_ms,selection_ms=selection_ms,actual_tokens=actual_tokens,tokenizer='embedding-model /tokenize; budget remains ceil(chars/4)' if actual_tokens is not None else 'unavailable; budget uses production ceil(chars/4)'))
            print('Retrieved question',qi+1,'of 60',flush=True)
        # Fixed, predeclared balanced pilot subset, 20 warm repetitions/arm.
        timing=[];subset=[i for i,q in enumerate(qs) if q['split']=='pilot']
        check(len(subset)==12,'Timing subset must be the 12 pilot questions')
        for i in subset:
            for arm,(strategy,k,_,_) in ARMS.items():
                samples=[]
                for _ in range(20):
                    started=time.perf_counter();stores[strategy].search(qv[i],top_k=k,source_filter='global');samples.append((time.perf_counter()-started)*1000)
                timing.append(dict(question_id=qs[i]['id'],arm=arm,samples_ms=samples))
        rebuild=[]
        for strategy in ['legacy','structure-v2']:
            test=ChromaVectorStore(host='127.0.0.1',port=1,collection_name='rebuild-'+strategy,source='global',embedding_model_id='laew-qwen3-embedding:'+identity)
            for i in range(0,len(all_chunks[strategy]),128):test.add_chunks(all_chunks[strategy][i:i+128])
            for i in subset:
                for arm,(s,k,_,_) in ARMS.items():
                    if s!=strategy:continue
                    ids=[c.chunk_id for c,_ in test.search(qv[i],top_k=k,source_filter='global')]
                    original=next(r for r in rows if r['question_id']==qs[i]['id'] and r['arm']==arm)
                    old=[c['id'] for c in original['raw']]
                    rebuild.append(dict(question_id=qs[i]['id'],arm=arm,membership_changed=set(ids)!=set(old),order_changed=ids!=old))
        write(out/'retrieval-traces.json',rows)
        write(out/'indexed-source-coverage.json',indexed_coverage)
        write(out/'timing.json',dict(warm=timing,rebuild_checks=rebuild,warm_searches=720,rebuild_searches=36))
        try:
            import psutil
            rss=psutil.Process().memory_info().rss
        except ImportError:rss=None
        write(out/'run-metadata.json',dict(status='retrieval-only-complete-no-generation',question_sha256=questions_sha,source_manifest_sha256=sha(corpus/'freeze-manifest.json'),model_catalog=model,model_identity_sha256=identity,dimensions=1024,chroma_version=__import__('importlib.metadata').metadata.version('chromadb'),costs=costs,embedding=counters,query_embedding=query_costs,index_disk_bytes=sum(p.stat().st_size for p in (out/'chroma').rglob('*') if p.is_file()),rss_bytes_at_end=rss,duration_seconds=time.perf_counter()-started_all,source_units=[dict(id=u['id'],sha256=u['normalized_sha256']) for u in units],primary_collections=['real-world-legacy','real-world-structure-v2'],rebuild_collections=['rebuild-legacy','rebuild-structure-v2'],project_scope='empty; no project collection or production HTTP Chroma client constructed',arms=ARMS,first_provider_dispatch='not invoked; delivered metrics refer to exact production renderer output',questions_only_input=True,labels_read=False,generation_calls=0))
    cache.close();verify_corpus(corpus)
    if resumed_cache_sha:write(out/'resumed-cache-provenance.json',dict(source=str(resume_cache),sha256=resumed_cache_sha,rule='Exact model-identity plus embedding-input hash only; no labels or retrieval results reused'))
    write(out/'trace-integrity.json',dict(files=[dict(path=n,sha256=sha(out/n)) for n in ['retrieval-traces.json','indexed-source-coverage.json','timing.json','run-metadata.json']],collector_sha256=sha(Path(__file__)),status='immutable-retrieval-trace-for-separate-scoring'))
    return dict(output=str(out),rows=180,traces_sha256=sha(out/'trace-integrity.json'),generation_calls=0)


def score(corpus,run,datasets,out):
    check(not out.exists(),'New scoring output required')
    integrity=read(run/'trace-integrity.json')
    for f in integrity['files']:check(sha(run/f['path'])==f['sha256'],'Trace changed before scoring')
    labels={};spans={};families={};datasets_sha={}
    for folder in datasets:
        inv=read(folder/'dataset-integrity.json');datasets_sha[str(folder)]=sha(folder/'dataset-integrity.json')
        for f in inv['files']:check(sha(folder/f['path'])==f['sha256'],'Dataset changed after freeze')
        labels.update({l['question_id']:l for l in read(folder/'draft-labels.json')})
        spans.update({s['id']:s for s in read(folder/'evidence-spans.json')})
        families.update({f['id']:f for f in read(folder/'families.json')})
    units=read(corpus/'corpus/source-manifest.json')['source_units'];texts={u['id']:(corpus/'corpus'/u['normalized_path']).read_text(encoding='utf-8') for u in units}
    for s in spans.values():check(hashlib.sha256(texts[s['source_id']][s['start']:s['end']].encode()).hexdigest()==s['text_sha256'],'Reference span no longer matches source')
    restrictions=read(corpus/'review/r3d/restricted-regions.json')['regions'];indexed=read(run/'indexed-source-coverage.json');rows=[]
    for r in read(run/'retrieval-traces.json'):
        label=labels[r['question_id']];family=families[r['family_id']]
        warnings=[f['id'] for f in family['facts'] if f.get('warning_or_condition')]
        warnings+= {'P01':['P01-F2','P01-F3'],'P02':['P02-F2','P02-F4','P02-F5'],'P03':['P03-F1','P03-F3','P03-F5','P03-F6']}.get(family['id'],[])
        stages={stage:score_stage(label,spans,coverage_of(r[stage]),texts,warnings) for stage in ['raw','eligible','selected']}
        avail=score_stage(label,spans,indexed[r['strategy']],texts,warnings)
        unavailable=[]
        selected_coverage=coverage_of(r['selected'])
        for reg in restrictions:
            if any(max(a,s['start'])<min(z,s['end']) for a,z in selected_coverage.get(reg['source_id'],[]) for s in reg['component_ranges']+reg['related_context_ranges']):unavailable.append(dict(source_id=reg['source_id'],pdf_page=reg['pdf_page']))
        judged=defaultdict(list)
        for s in spans.values():judged[s['source_id']].append((s['start'],s['end']))
        total=unknown=0
        for sid,ranges in selected_coverage.items():
            known=union(judged[sid])
            for a,z in ranges:
                total+=z-a;unknown+=sum(1 for i in range(a,z) if not any(x<=i<y for x,y in known))
        errors=[]
        if label['positive_evidence_recall_applicable']:
            for fact in label['required_answer_facts']:
                fid=fact['id']
                if fid not in avail['facts_hit']:reason='source-not-completely-indexed-or-span-attribution-gap'
                elif fid not in stages['raw']['facts_hit']:reason='evidence-present-but-not-retrieved'
                elif fid not in stages['eligible']['facts_hit']:reason='cosine-threshold'
                elif fid not in stages['selected']['facts_hit']:reason='context-selection-or-budget'
                else:continue
                errors.append(dict(fact_id=fid,reason=reason))
        groups=sorted({next(u['family'] for u in units if u['id']==spans[s]['source_id']) for f in label['required_answer_facts'] for alt in f['evidence_alternatives'] for s in alt}) or ['unavailable']
        rows.append(dict(question_id=r['question_id'],family_id=r['family_id'],split=r['split'],language=r['language'],category=family['category'],source_groups=groups,arm=r['arm'],k=r['k'],index_available=avail,**stages,estimated_tokens=r['estimated_tokens'],search_ms=r['search_ms'],selection_ms=r['selection_ms'],unavailable_context_exposure=unavailable,unjudged_context_characters=unknown,attributed_context_characters=total,errors=errors,reference_status='agent_draft-not-independently-adjudicated'))
    def summary(items):
        def mean(values):
            values=[v for v in values if v is not None];return statistics.mean(values) if values else None
        result=dict(questions=len(items),families=len({r['family_id'] for r in items}),answerable=sum(r['raw']['fact_recall'] is not None for r in items),mean_estimated_tokens=mean(r['estimated_tokens'] for r in items),mean_search_ms=mean(r['search_ms'] for r in items),unavailable_exposure_questions=sum(bool(r['unavailable_context_exposure']) for r in items),unjudged_characters=sum(r['unjudged_context_characters'] for r in items))
        for stage in ['raw','eligible','selected']:
            result[stage]={key:mean(r[stage][key] for r in items) for key in ['fact_recall','complete','warning_coverage','document_hit_rate']}
        return result
    grouped={}
    for split in ['pilot','sealed']:
        for arm in ARMS:
            selected=[r for r in rows if r['split']==split and r['arm']==arm]
            grouped[split+'/'+arm]=summary(selected)
            for key in ['language','category']:
                for value in sorted({r[key] for r in selected}):grouped[split+'/'+arm+'/'+key+'/'+value]=summary([r for r in selected if r[key]==value])
            for group in sorted({g for r in selected for g in r['source_groups']}):grouped[split+'/'+arm+'/source/'+group]=summary([r for r in selected if group in r['source_groups']])
    out.mkdir(parents=True)
    write(out/'per-question.json',rows);write(out/'summary.json',grouped)
    write(out/'provenance.json',dict(status='provisional-exploratory-agent-draft-reference',dataset_manifests=datasets_sha,trace_manifest_sha256=sha(run/'trace-integrity.json'),scorer_sha256=sha(Path(__file__)),metric='Conservative non-whitespace source-span coverage within a coherent alternative set; no substring-only scoring or semantic model judge',uncertainty='No independent human gold; unjudged context is not irrelevant. No inference of generalizable superiority.',generation_calls=0))
    return grouped


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['collect','score']);ap.add_argument('--corpus',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--questions',type=Path);ap.add_argument('--questions-sha');ap.add_argument('--run',type=Path);ap.add_argument('--dataset',type=Path,action='append');ap.add_argument('--resume-cache',type=Path)
    a=ap.parse_args()
    result=collect(a.corpus,a.questions,a.questions_sha,a.output,a.resume_cache) if a.mode=='collect' else score(a.corpus,a.run,a.dataset,a.output)
    print(json.dumps(result,indent=2))
