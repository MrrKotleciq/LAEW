"""Separate frozen-candidate selection and reference evaluation processes."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import time

from laew.eval.complementary_context_study import (
    context_metrics, evaluate, load_inputs, offline, read, seal, sha, write,
)
from laew.eval.real_world_retrieval import payload_segments
from laew.rag.evidence_selection import SelectionConfig, select_scopes


def collect(config,output,freeze,split):
    from laew.eval import evidence_aware_selection as selector
    if output.exists():
        raise ValueError('Fresh output required')
    frozen=read(freeze)
    if frozen['version']!=selector.VERSION or frozen['selector_sha256']!=sha(selector.__file__) or frozen['settings']!=selector.SETTINGS:
        raise ValueError('Selector differs from pre-evaluation freeze')
    data=load_inputs(config,scoring=False)
    traces=[];metrics=[];timings=[];profiles=[]
    cfg=SelectionConfig(policy='ranked_fill',budget=1000)
    for baseline in data['traces']:
        if baseline['arm'] not in ('B','C') or (split!='all' and baseline['split']!=split):
            continue
        qid,arm,strategy=baseline['question_id'],baseline['arm'],baseline['strategy']
        if (baseline['k'],baseline['budget'],baseline['policy'])!=(10,1000,'ranked_fill'):
            raise ValueError('Native K10 baseline settings differ')
        pool=data['pools'][qid,arm]
        query=data['questions'][qid]['text']
        def mechanism(name):
            if name==selector.VERSION:
                return selector.select_evidence_scopes({'global':pool},cfg,query,version=selector.VERSION)
            return select_scopes({'global':[c for c in pool if not selector.anchor_only(c.chunk.text)]},cfg,8000)
        for name in (selector.VERSION,'anchor-only-filter-diagnostic'):
            started=time.perf_counter();selected,enclosing=mechanism(name)
            elapsed=(time.perf_counter()-started)*1000
            result=selected['global']
            encoded=[]
            for chunk,score in result.chunks:
                sid,mapping,text=data['sources'][strategy][chunk.chunk_id]
                encoded.append(dict(id=chunk.chunk_id,source_id=sid,source_sha256=data['units'][sid]['normalized_sha256'],
                    cosine=score,text=chunk.text,source_ranges=payload_segments(chunk,mapping,text,len(chunk.text))))
            if result.estimated_tokens>1000 or (len(enclosing)+3)//4>8000:
                raise ValueError('Budget exceeded')
            variant=arm+'-'+name
            trace={k:baseline[k] for k in ('question_id','family_id','language','split','strategy','k','budget')}
            trace.update(arm=variant,baseline_arm=arm,raw=baseline['raw'],eligible=baseline['eligible'],
                selected=encoded,context=result.context,enclosing_context=enclosing,
                estimated_tokens=result.estimated_tokens,selection_ms=elapsed,decisions=result.decisions)
            traces.append(trace)
            metrics.append(dict(question_id=qid,arm=variant,**context_metrics(result,enclosing,data['sources'][strategy])))
            samples={'baseline':[],'experimental':[]}
            for repeat in range(10):
                for kind in (('baseline','experimental') if repeat%2==0 else ('experimental','baseline')):
                    started=time.perf_counter()
                    if kind=='baseline':select_scopes({'global':pool},cfg,8000)
                    else:mechanism(name)
                    samples[kind].append((time.perf_counter()-started)*1000)
            timings.append(dict(question_id=qid,arm=variant,samples_ms=samples))
        profiles.append(dict(question_id=qid,arm=arm,**selector.profile_candidates(query,pool)))
    output.mkdir(parents=True)
    write(output/'selection-traces.json',traces)
    write(output/'metrics.json',metrics)
    write(output/'timing.json',timings)
    write(output/'profiles.json',profiles)
    write(output/'input-integrity.json',data['receipts'])
    write(output/'provenance.json',dict(version=selector.VERSION,settings=selector.SETTINGS,
        selector_sha256=sha(selector.__file__),runner_sha256=sha(__file__),freeze_sha256=sha(freeze),split=split,
        labels_read=False,rubric_read=False,answers_read=False,embedding_calls=0,generation_calls=0,
        retrieval_calls=0,network_calls=0,index_access=False,historical_contexts_reproduced=180,
        latency='10 alternating-order warm repeats per query/arm/mechanism; selection+render only; no reuse of feature computations',
        diagnostic='Anchor-only filter is an independent ranked_fill diagnostic, not an index change'))
    seal(output,['selection-traces.json','metrics.json','timing.json','profiles.json','input-integrity.json','provenance.json'])
    print(dict(output=str(output),version=selector.VERSION,rows=len(traces),
        fallback_reasons=dict(Counter(r['decisions'][0].get('fallback','changed') for r in traces if r['arm'].endswith(selector.VERSION) and r['decisions']))),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['collect','score'])
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--delivery',type=Path)
    parser.add_argument('--split',choices=['pilot','all'],default='pilot')
    args=parser.parse_args()
    with offline():
        if args.mode=='collect':
            if not args.freeze:parser.error('--freeze required')
            collect(read(args.config),args.output,args.freeze,args.split)
        else:
            if not args.delivery:parser.error('--delivery required')
            evaluate(read(args.config),args.delivery,args.output)


if __name__=='__main__':
    main()
