"""Replay immutable native candidates with compact attribution, without scoring.

No labels, rubric, answer facts, question text, embeddings or indexes are read.
The source loader runs embed=False and is checked against frozen chunk hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

from laew.eval.compact_context_delivery import MECHANISM_ID, VARIANTS, select_compact_scopes
from laew.eval.real_world_retrieval import payload_segments, union
from laew.rag.evidence_selection import Candidate, SelectionConfig, select_scopes
from laew.rag.knowledge_base import KnowledgeBase


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def context_metrics(selection, enclosing, source_by_chunk):
    coverage = {}
    source_chars = 0
    sections = set()
    for chunk, _ in selection.chunks:
        sid, mapping, text = source_by_chunk[chunk.chunk_id]
        ranges = payload_segments(chunk, mapping, text, len(chunk.text))
        coverage.setdefault(sid, []).extend(ranges)
        source_chars += sum(z-a for a,z in ranges)
        section = chunk.metadata.get('section_path') or [chunk.metadata.get('section_header')]
        sections.add((sid, tuple(section)))
    unique = sum(z-a for ranges in coverage.values() for a,z in union(ranges))
    body = sum(len(chunk.text) for chunk,_ in selection.chunks)
    return dict(selected_chunks=len(selection.chunks), estimated_tokens=selection.estimated_tokens,
                enclosing_estimated_tokens=(len(enclosing)+3)//4, body_chars=body,
                attribution_chars=len(selection.context)-body-7*max(0,len(selection.chunks)-1),
                total_source_chars=source_chars, unique_source_chars=unique,
                repeated_source_chars=source_chars-unique, sources=len(coverage), sections=len(sections))


def replay(corpus, run, trace_sha, split, output, freeze=None):
    if output.exists():
        raise ValueError('Use a fresh output directory')
    if sha(run/'trace-integrity.json') != trace_sha:
        raise ValueError('Trace trust anchor mismatch')
    for entry in read(run/'trace-integrity.json')['files']:
        path=(run/entry['path']).resolve()
        if not path.is_relative_to(run.resolve()) or sha(path)!=entry['sha256']:
            raise ValueError('Frozen trace changed')
    if split == 'sealed':
        if freeze is None:
            raise ValueError('Sealed replay requires a mechanism freeze after pilot review')
        frozen=read(freeze)
        from laew.eval import compact_context_delivery
        if (frozen['mechanism_id']!=MECHANISM_ID or
                frozen['selector_sha256']!=sha(compact_context_delivery.__file__) or
                frozen['replay_sha256']!=sha(__file__)):
            raise ValueError('Mechanism changed after freeze')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/corpus'))
    from prepare_real_world_pilot import verify_corpus
    verify_corpus(corpus)
    units={u['id']:u for u in read(corpus/'corpus/source-manifest.json')['source_units']}
    traces=[r for r in read(run/'retrieval-traces.json') if r['split']==split]
    expected=36 if split=='pilot' else 144
    if len(traces)!=expected:
        raise ValueError('Unexpected split size')
    chunks={};source_by_chunk={'legacy':{},'structure-v2':{}}
    # Reconstruct source serialization only; no vector store or embedding object.
    for strategy in ('legacy','structure-v2'):
        ids={c['source_id'] for r in traces if r['strategy']==strategy for c in r['raw']}
        loader=object.__new__(KnowledgeBase)
        loader.chunk_size=1000;loader.chunk_overlap=200;loader.chunking_strategy=strategy
        for sid in sorted(ids):
            unit=units[sid];path=corpus/'corpus'/unit['normalized_path']
            text=path.read_text(encoding='utf-8')
            generated=loader._load_file(path,'global',path.parent,content=text,embed=False)
            mapping=read(corpus/f'corpus/chunk-maps/{sid}-{strategy}.json')['records']
            if len(generated)!=len(mapping):
                raise ValueError('Frozen loader count changed')
            for chunk, record in zip(generated,mapping):
                if hashlib.sha256(chunk.text.encode()).hexdigest()!=record['text_sha256']:
                    raise ValueError('Frozen chunk text changed')
                chunks[strategy,chunk.chunk_id]=chunk
                source_by_chunk[strategy][chunk.chunk_id]=(sid,record,text)
    rows=[];metrics=[];timing=[]
    for original in traces:
        arm=original['arm'];variant=arm+'-D1'
        _,strategy,k,policy,budget=VARIANTS[variant]
        sources=source_by_chunk[strategy]
        if (original['strategy'],original['k'],original['policy'],original['budget'])!=(strategy,k,policy,budget):
            raise ValueError('Historical settings changed')
        candidates=[]
        for raw in original['raw']:
            chunk=chunks[strategy,raw['id']]
            if chunk.text!=raw['text'] or raw['source_sha256']!=units[raw['source_id']]['normalized_sha256']:
                raise ValueError('Candidate identity/text mismatch')
            sid,mapping,text=sources[chunk.chunk_id]
            if [[a,z] for a,z in payload_segments(chunk,mapping,text,len(chunk.text))]!=raw['source_ranges']:
                raise ValueError('Frozen candidate source attribution differs')
            candidates.append(Candidate(chunk,raw['cosine']))
        config=SelectionConfig(policy=policy,budget=budget)
        pools={'global':candidates}
        baseline,enclosing=select_scopes(pools,config,8000)
        baseline=baseline['global']
        if (baseline.context!=original['context'] or enclosing!=original['enclosing_context'] or
                [(c.chunk_id,c.text) for c,_ in baseline.chunks]!=[(c['id'],c['text']) for c in original['selected']]):
            raise ValueError('Historical context replay differs')
        started=time.perf_counter()
        experimental,new_enclosing=select_compact_scopes(pools,config,8000)
        elapsed=(time.perf_counter()-started)*1000
        experimental=experimental['global']
        if experimental.estimated_tokens>budget or (len(new_enclosing)+3)//4>8000:
            raise ValueError('Experimental budget exceeded')
        selected=[]
        for chunk,score in experimental.chunks:
            sid,mapping,text=sources[chunk.chunk_id]
            selected.append(dict(id=chunk.chunk_id,source_id=sid,source_sha256=units[sid]['normalized_sha256'],
                                 cosine=score,text=chunk.text,
                                 source_ranges=payload_segments(chunk,mapping,text,len(chunk.text))))
        rows.append(dict(question_id=original['question_id'],family_id=original['family_id'],language=original['language'],
                         split=split,arm=variant,baseline_arm=arm,strategy=strategy,k=k,policy=policy,budget=budget,
                         raw=original['raw'],eligible=original['eligible'],selected=selected,
                         context=experimental.context,enclosing_context=new_enclosing,
                         estimated_tokens=experimental.estimated_tokens,selection_ms=elapsed,
                         mechanism_id=MECHANISM_ID))
        metrics.append(dict(question_id=original['question_id'],arm=variant,baseline_arm=arm,
                            original=context_metrics(baseline,enclosing,sources),
                            experimental=context_metrics(experimental,new_enclosing,sources)))
        if split=='pilot':
            samples={'original':[],'experimental':[]}
            for repeat in range(20):
                order=('original','experimental') if repeat%2==0 else ('experimental','original')
                for name in order:
                    started=time.perf_counter()
                    (select_scopes if name=='original' else select_compact_scopes)(pools,config,8000)
                    samples[name].append((time.perf_counter()-started)*1000)
            timing.append(dict(question_id=original['question_id'],arm=variant,samples_ms=samples,
                               median_ms={name:statistics.median(v) for name,v in samples.items()}))
    output.mkdir(parents=True)
    write(output/'delivery-traces.json',rows)
    write(output/'delivery-metrics.json',metrics)
    write(output/'selection-timing.json',timing)
    write(output/'provenance.json',dict(mechanism_id=MECHANISM_ID,split=split,rows=len(rows),
        native_candidates_reused=True,original_context_replay_exact=True,labels_read=False,rubric_read=False,
        question_text_read=False,embedding_calls=0,retrieval_calls=0,index_writes=0,generation_calls=0,
        trace_manifest_sha256=trace_sha,replay_sha256=sha(__file__),
        freeze_sha256=sha(freeze) if freeze else None,
        latency_scope='Pilot only: 20 alternating-order warm repeats of selection+render per pair; excludes source loading, retrieval and generation.'))
    write(output/'delivery-integrity.json',dict(files=[dict(path=name,sha256=sha(output/name)) for name in
        ('delivery-traces.json','delivery-metrics.json','selection-timing.json','provenance.json')]))
    return dict(output=str(output),rows=len(rows),original_replay_exact=True,generation_calls=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--trace-sha',required=True)
    parser.add_argument('--split',choices=('pilot','sealed'),required=True)
    parser.add_argument('--freeze',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(replay(args.corpus,args.run,args.trace_sha,args.split,args.output,args.freeze),indent=2))
