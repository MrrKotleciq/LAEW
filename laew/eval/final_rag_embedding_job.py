"""Dispatch exactly the two approved, hash-pinned local embedding workloads."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import time

import numpy as np
import requests

from laew.eval.complementary_context_study import read, seal, sha, verify_manifest, write
from laew.eval.decomposition_embedding_job import BASE, catalog_compatible
from laew.eval.final_rag_preflight import WEIGHT_SHA, digest
from laew.rag.llamacpp import _validate_embeddings

WORKLOAD_SHA = '28667adbe886f2e14cd694913723e2d8bdff6569fb9606b8c92cdf660a71709f'
COUNTS = {'adaptive': 1307, 'contextual': 2161}
REQUESTS = {'adaptive': 333, 'contextual': 662}
ALIAS = 'laew-qwen3-embedding'


def schedule(entries):
    if len({row['sha256'] for row in entries}) != sum(COUNTS.values()) or len(entries) != sum(COUNTS.values()):
        raise ValueError('Approved unique input count differs')
    if any(digest(row['text']) != row['sha256'] or len(row['arms']) != 1 or row['arms'][0] not in COUNTS
           for row in entries):
        raise ValueError('Unapproved input or arm')
    for arm, count in COUNTS.items():
        items = [row for row in entries if row['arms'] == [arm]]
        if len(items) != count:
            raise ValueError('Approved arm count differs')
        pending, size, batches = [], 0, []
        for row in items:
            cost = len(row['text'].encode('utf-8')) + 8
            if cost > 4096:
                raise ValueError('Input exceeds approved payload budget')
            if len(pending) == 4 or size + cost > 4096:
                batches.append(pending)
                pending, size = [], 0
            pending.append(row)
            size += cost
        if pending:
            batches.append(pending)
        if len(batches) != REQUESTS[arm]:
            raise ValueError('Approved maximum request count differs')
        yield from ((arm, batch) for batch in batches)


def served_model(session, freeze):
    def get(path):
        response = session.get(BASE + path, timeout=10, allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError(f'Server metadata request failed: {path} HTTP {response.status_code}')
        return response.json()

    catalog = next(row for row in get('/v1/models')['data'] if row['id'] == ALIAS)
    props = get('/props')
    weight = Path(props['model_path']).resolve(strict=True)
    with weight.open('rb') as stream:
        weight_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    compatibility = catalog_compatible(freeze['model_catalog'], catalog)
    command = ('Get-CimInstance Win32_Process -Filter "Name = \'llama-server.exe\'" '
               '| Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress')
    processes = json.loads(subprocess.check_output(['pwsh', '-NoProfile', '-Command', command], text=True))
    if isinstance(processes, dict):
        processes = [processes]
    matching = [row for row in processes if f'"{weight}"'.casefold() in row['CommandLine'].casefold()
                and '"--port" "8081"' in row['CommandLine']]
    required = ['"--embedding"', '"--pooling" "last"', '"--host" "127.0.0.1"',
                '"--device" "CUDA0"', '"--gpu-layers" "all"', '"--parallel" "2"',
                '"--ctx-size" "16384"', '"--batch-size" "1024"', '"--ubatch-size" "1024"']
    if (weight_sha != freeze['weight_sha256'] or weight_sha != WEIGHT_SHA or props['model_alias'] != ALIAS
            or props['build_info'] != freeze['historical_server']['build'] or props['total_slots'] != 2
            or len(matching) != 1 or not all(flag in matching[0]['CommandLine'] for flag in required)
            or '"--embd-normalize"' in matching[0]['CommandLine']):
        raise ValueError('Loaded model or approved GPU execution settings changed')
    return dict(weight_sha256=weight_sha, model_path=str(weight), catalog=catalog, compatibility=compatibility,
                pid=matching[0]['ProcessId'], build=props['build_info'], slots=2, pooling='last',
                normalization='L2 default', cuda_device='CUDA0', gpu_layers='all', context_size=16384,
                batch_size=1024, ubatch_size=1024)


def execute(preflight, preflight_sha, output):
    if output.exists():
        raise ValueError('Fresh output required. Do not resubmit an ambiguous request.')
    verify_manifest(preflight, 'integrity.json', preflight_sha)
    inputs = preflight / 'pending-embedding-inputs.json'
    if sha(inputs) != WORKLOAD_SHA:
        raise ValueError('Approved workload hash differs')
    batches = list(schedule(read(inputs)))
    freeze = read(preflight / 'preflight.json')
    with requests.Session() as session:
        session.trust_env = False
        server = served_model(session, freeze)
        output.mkdir(parents=True, exist_ok=False)
        write(output / 'execution.json', dict(server=server, approved_inputs=COUNTS, max_requests=REQUESTS,
                                               workload_sha256=WORKLOAD_SHA, preflight_sha256=preflight_sha,
                                               runner_sha256=sha(__file__), automatic_retries=0))
        with closing(sqlite3.connect(output / 'vectors.sqlite3')) as db:
            db.executescript('create table batches (id integer primary key, arm text, hashes text, '
                             'seconds real, tokens integer, status text); '
                             'create table vectors (hash text primary key, batch integer, vector blob);')
            totals = Counter()
            start = time.perf_counter()
            for i, (arm, batch) in enumerate(batches):
                hashes = [item['sha256'] for item in batch]
                inputs = [item['text'] for item in batch]
                with db:
                    db.execute('insert into batches values (?,?,?,?,?,?)',
                               (i, arm, json.dumps(hashes), None, None, 'dispatch_intent'))
                tick = time.perf_counter()
                response = session.post(BASE + '/v1/embeddings',
                                        json=dict(model=ALIAS, input=inputs, encoding_format='float'),
                                        timeout=90, allow_redirects=False)
                if response.status_code != 200:
                    raise RuntimeError(f'Batch {i} stopped on HTTP {response.status_code}')
                payload = response.json()
                tokens = payload['usage']['prompt_tokens']
                if (payload['model'] != ALIAS or type(tokens) is not int or tokens <= 0
                        or payload['usage']['total_tokens'] != tokens or payload.get('truncated', False)):
                    raise RuntimeError(f'Batch {i} returned unexpected model, truncation, or usage')
                vectors = np.asarray(_validate_embeddings(payload['data'], inputs, 1024), dtype=np.float32)
                if not np.isfinite(vectors).all() or np.max(np.abs(np.linalg.norm(vectors, axis=1) - 1)) > 1e-4:
                    raise RuntimeError(f'Batch {i} returned invalid or non-L2 embeddings')
                with db:
                    db.executemany('insert into vectors values (?,?,?)',
                                   [(key, i, vector.tobytes()) for key, vector in zip(hashes, vectors)])
                    db.execute("update batches set seconds=?, tokens=?, status='completed' where id=?",
                               (time.perf_counter() - tick, tokens, i))
                totals[arm] += len(batch)
                if (i + 1) % 100 == 0 or totals[arm] == COUNTS[arm]:
                    print(json.dumps(dict(completed=dict(totals), requests=i + 1,
                                          elapsed_seconds=round(time.perf_counter() - start, 2))), flush=True)
            measures = {arm: dict(requests=n, seconds=seconds, input_tokens=tokens, inputs=totals[arm])
                        for arm, n, seconds, tokens in db.execute(
                            "select arm,count(*),sum(seconds),sum(tokens) from batches group by arm")}
        write(output / 'measurements.json', measures)
        seal(output, ['execution.json', 'vectors.sqlite3', 'measurements.json'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preflight', type=Path)
    parser.add_argument('preflight_sha')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    execute(args.preflight, args.preflight_sha, args.output)
