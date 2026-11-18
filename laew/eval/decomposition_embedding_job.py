"""Explicitly authorized, exact question-only embedding job; no corpus rebuild.

No reference/rubric/answer input. Each frozen pending text is submitted once.
Ambiguous failures stop without automatic retries. Original cache is immutable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import numpy as np
import requests

from laew.eval.complementary_context_study import read, seal, sha, verify_manifest, write
from laew.rag.llamacpp import _validate_embeddings

EXPECTED_WEIGHT='06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439'
BASE='http://127.0.0.1:8081'


def catalog_compatible(old, current):
    """Server reload timestamp is not weight/embedding identity; disclose it."""
    def stable(value):
        return {k:v for k,v in value.items() if k!='created'}
    if stable(old)!=stable(current):
        raise ValueError('Model catalog changed beyond reload timestamp; stop')
    if current['meta']['n_embd']!=1024 or current['meta']['ftype']!='Q8_0':
        raise ValueError('Embedding model/dimensions differ')
    return dict(changed_fields=[k for k in set(old)|set(current) if old.get(k)!=current.get(k)],
                original_catalog_identity=hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest(),
                current_catalog_identity=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest(),
                accepted_reason='Only server reload timestamp; identical exact GGUF weight and last-token pooling separately verified',
                original_cache_rekeyed=False)


def execute(package, output, approved_count, workload_sha):
    if output.exists():
        raise ValueError('Fresh output required; ambiguous dispatches must not be repeated automatically')
    root=package/'decomposition'
    verify_manifest(root,'integrity.json',sha(root/'integrity.json'))
    pending_path=root/'pending-embedding-inputs.json'
    if sha(pending_path)!=workload_sha:
        raise ValueError('Approved workload hash differs')
    pending=read(pending_path);freeze=read(root/'freeze.json')
    if approved_count!=41 or len(pending)!=approved_count or len({r['text'] for r in pending})!=approved_count:
        raise ValueError('Only the approved 41 unique inputs may be embedded')
    if any(hashlib.sha256(r['text'].encode()).hexdigest()!=r['sha256'] for r in pending):
        raise ValueError('Pending input changed')
    session=requests.Session();session.trust_env=False
    def get(route):
        response=session.get(BASE+route,timeout=15,allow_redirects=False)
        response.raise_for_status();return response.json()
    catalog=next(m for m in get('/v1/models')['data'] if m['id']=='laew-qwen3-embedding')
    props=get('/props')
    weight=Path(props['model_path'])
    # Hash the actual service-owned local file before any embedding dispatch.
    digest=hashlib.file_digest(weight.open('rb'),'sha256').hexdigest()
    if digest!=EXPECTED_WEIGHT or props['model_alias']!=catalog['id']:
        raise ValueError('Loaded weight/model alias differs')
    compatibility=catalog_compatible(freeze['model_catalog'],catalog)
    # Last-token pooling was read from this process's quoted Windows arguments;
    # normalization uses llama.cpp default L2 (explicit override absent).
    output.mkdir(parents=True)
    write(output/'authorization.json',dict(user_authorized=True,approved_inputs=approved_count,
        workload_sha256=workload_sha,authorization_basis='Explicit approved count and workload hash supplied to the runner',
        weight_sha256=digest,model_path=str(weight),catalog=catalog,compatibility=compatibility,
        server=dict(alias=props['model_alias'],slots=props['total_slots'],build=props['build_info'],
                    pooling='last; verified from local process arguments',ctx_size=16384,batch_size=1024,ubatch_size=1024,
                    normalization='L2 default; no embd-normalize override in process arguments'),
        dimensions=1024,source_inputs=0,existing_query_reembeddings=0,model_answers=0,
        runner_sha256=sha(__file__),batch_inputs=8,automatic_retries=0))
    (output/'runner-snapshot.py').write_bytes(Path(__file__).read_bytes())
    identity=compatibility['current_catalog_identity']
    connection=sqlite3.connect(output/'query-vectors.sqlite3')
    connection.execute('create table vectors (key text primary key, vector blob not null)')
    ledger=[];started=time.perf_counter()
    try:
        for index in range(0,len(pending),8):
            batch=pending[index:index+8]
            row=dict(batch=len(ledger),input_sha256s=[r['sha256'] for r in batch],status='dispatch_intent',inputs=len(batch))
            ledger.append(row);write(output/'dispatch-ledger.json',ledger)
            tick=time.perf_counter()
            response=session.post(BASE+'/v1/embeddings',json=dict(model=catalog['id'],input=[r['text'] for r in batch]),
                                  timeout=180,allow_redirects=False)
            response.raise_for_status()
            vectors=_validate_embeddings(response.json()['data'],[r['text'] for r in batch],1024)
            for item,vector in zip(batch,vectors):
                value=np.asarray(vector,dtype=np.float32)
                if not np.isfinite(value).all() or np.linalg.norm(value)<=0:
                    raise ValueError('Invalid returned embedding')
                key=hashlib.sha256((identity+'\0'+item['text']).encode()).hexdigest()
                connection.execute('insert into vectors values (?,?)',(key,value.tobytes()))
            connection.commit()
            row.update(status='completed',seconds=time.perf_counter()-tick,usage=response.json().get('usage'))
            write(output/'dispatch-ledger.json',ledger)
            print(json.dumps(dict(completed=min(index+8,len(pending)),total=approved_count,batch_seconds=row['seconds'])),flush=True)
    except Exception as error:
        write(output/'failure.json',dict(error_type=type(error).__name__,message=str(error),
            dispatch_ambiguity='Do not automatically resubmit an incomplete batch',completed=sum(x['inputs'] for x in ledger if x['status']=='completed')))
        raise
    finally:
        connection.close();session.close()
    write(output/'metadata.json',dict(model_catalog=catalog,model_identity_sha256=identity,dimensions=1024,
        compatibility=compatibility,inputs=approved_count,requests=len(ledger),seconds=time.perf_counter()-started,
        original_cache_modified=False,corpus_reembedded=False,authorization_sha256=sha(output/'authorization.json')))
    seal(output,['authorization.json','runner-snapshot.py','dispatch-ledger.json','query-vectors.sqlite3','metadata.json'])
    print(json.dumps(read(output/'metadata.json')),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--approved-inputs',type=int,required=True)
    parser.add_argument('--workload-sha256',required=True)
    args=parser.parse_args()
    execute(args.package,args.output,args.approved_inputs,args.workload_sha256)


if __name__=='__main__':
    main()
