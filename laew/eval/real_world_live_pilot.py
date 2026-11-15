"""Evaluation-only frozen-context pilot; durable at-most-once OAuth dispatch.

No retrieval, embedding, judge, fallback, or production configuration changes.
The SQLite reservation is committed with FULL synchronization before HTTP. An
unresolved reservation or a stopped experiment requires investigation, never
automatic replacement. Safe telemetry excludes credentials and reasoning.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import threading
import time

from laew.cloud_chat import CloudChatService, CloudError, ResponsesTransport
from laew.eval.real_world_answer_plan import INSTRUCTIONS, MODEL, prepare
from laew.llm.cancellation import Cancellation

MAX_ATTEMPTS = 36
WATCHDOG = 120
CEILING = 5400
REQUESTS_SHA = '796f4ae2df948cb1a334b423230c211f6162f03fe6179f8067b5ace122b9e3ab'


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, data):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def payload_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def require(condition, code='INTEGRITY'):
    if not condition:
        raise CloudError(code, 'Frozen pilot safety check failed: ' + code)


def inventory(root, name, anchor=None):
    manifest = root / name
    if anchor:
        require(sha(manifest) == anchor)
    entries = read(manifest)['files']
    for e in entries:
        path = (root / e['path']).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file())
        require(sha(path) == e['sha256'])
        require('bytes' not in e or path.stat().st_size == e['bytes'])
    return dict(manifest_sha256=sha(manifest), members=len(entries))


def verify_inputs(repo, data, previous):
    """Hash-check inputs and reproduce exact payloads without external services."""
    sys.path.insert(0, str(repo / 'tools/corpus'))
    import prepare_real_world_pilot as base
    import prepare_real_world_dataset as dataset
    from laew.eval.scoring_calibration import validate_atoms, validate_family

    corpus = data / 'stage-2b2-real-world-20261112-freeze-v1'
    retrieval = data / 'stage-2b2-real-world-retrieval-20261113-v2'
    audit = previous / 'laew-evidence-audit-v1'
    calibration = previous / 'laew-scoring-calibration-v2'
    report = dict(utc=utc(), corpus=base.verify_corpus(corpus), datasets={})
    for name, anchor in [
        ('stage-2b2-real-world-pilot-20261113-v4', '9060c3027424da26c5c49888cea62d423a7df543242258f8eb0629c58360bcf6'),
        ('stage-2b2-real-world-sealed-20261113-v3', '4f19aba5f77f8012d74bdfdfc7305cdbba330672fa82138c8b108480eec9e437')]:
        report['datasets'][name] = dict(members=len(dataset.verify_dataset(data / name, anchor)['files']),
                                      manifest_sha256=anchor)
    for key, root, name, anchor in [
        ('retrieval', retrieval, 'artifact-integrity.json', '4bdbeed19cf75a4e435dc1d5ee1111cf26736c29f1ed3436acd6b99d52b5aad5'),
        ('audit', audit, 'artifact-integrity.json', '2d0665746a3b0847f0c84552f835e9fec3d61bce7d93ebf3dc69c329c8a67383'),
        ('calibration', calibration, 'artifact-integrity.json', None),
        ('rubric', calibration, 'rubric-manifest-v2.1.json', '36f985c702203012166f99b5a53850acea6e77f5d80ef25c0514dcdec870cee3'),
        ('generator', audit / 'generator-only', 'manifest.json', None),
        ('traces', retrieval / 'run-v2', 'trace-integrity.json', 'e91d52ea4209fc44dc32faaa22ad5e8adda13367939f6e21fc3db20116cb342a'),
        ('delivery', previous / 'laew-context-delivery-v1', 'artifact-integrity.json', None),
    ]:
        report[key] = inventory(root, name, anchor)
    rubric_manifest = read(calibration / 'rubric-manifest-v2.1.json')
    require(sha(repo / 'laew/eval/scoring_calibration.py') == rubric_manifest['scorer_sha256'])
    # Existing runtime/builder must still match the original offline capture.
    for e in read(audit / 'artifact-integrity.json')['files']:
        if e['path'].startswith('code/'):
            local = repo / e['path'][5:]
            if local.is_file() and not e['path'].startswith('code/docs/'):
                require(sha(local) == e['sha256'])
    units = {u['id']: u for u in read(corpus / 'corpus/source-manifest.json')['source_units']}
    texts = {sid: (corpus / 'corpus' / u['normalized_path']).read_text(encoding='utf-8')
             for sid, u in units.items()}
    atoms = read(calibration / 'source-atoms-v2.1.json')
    validate_atoms(atoms, texts, units)
    for f in read(calibration / 'rubric-v2.1.json')['families'].values():
        validate_family(f, atoms)
    require(sha(audit / 'generator-only/requests.json') == REQUESTS_SHA)
    require(sha(audit / 'pilot-questions-only.json') == '6ae0b1d4dbeb8a80f151c3d946162a75eee84f7f7ff2e456606904172ae9e2aa')
    rows = read(audit / 'generator-only/requests.json')
    questions = read(audit / 'pilot-questions-only.json')
    traces = read(retrieval / 'run-v2/retrieval-traces.json')
    require(prepare(questions, traces) == rows)
    report.update(payloads_reproduced=36, atoms_verified=len(atoms), source_units=len(units),
                  generator_input='sanitized questions and original contexts only',
                  embeddings_computed=0, inference_attempts=0)
    return report, rows


class Ledger:
    """Transactional global cap, unique pairs, strict sequence, crash conservatism."""
    def __init__(self, path, fixture_hash):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA synchronous=FULL')
        require(self.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS attempts(
            sequence INTEGER PRIMARY KEY CHECK(sequence BETWEEN 1 AND 36),
            question_id TEXT NOT NULL, arm TEXT NOT NULL,
            record TEXT NOT NULL, UNIQUE(question_id,arm));
        ''')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('fixture', fixture_hash))
        require(self.meta('fixture') == fixture_hash)

    def close(self):
        self.db.close()

    def meta(self, key):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def records(self):
        return [json.loads(r[0]) for r in self.db.execute('SELECT record FROM attempts ORDER BY sequence')]

    def reserve(self, row):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            records = self.records()
            require(not self.meta('stop'), 'EXPERIMENT_STOPPED')
            require(len(records) < MAX_ATTEMPTS, 'ATTEMPT_CAP')
            require(not any(r['status'] == 'reserved' for r in records), 'UNCERTAIN_DISPATCH')
            require(not any((r['question_id'], r['arm']) == (row['question_id'], row['arm']) for r in records), 'DUPLICATE')
            require(row['sequence'] == len(records) + 1, 'ORDER')
            started = self.meta('started_epoch')
            if started is None:
                started = str(time.time())
                self.db.execute('INSERT INTO meta VALUES (?,?)', ('started_epoch', started))
            require(time.time() - float(started) < CEILING, 'WALL_CEILING')
            record = dict(sequence=row['sequence'], question_id=row['question_id'], arm=row['arm'],
                          context_sha256=row['context_sha256'], payload=row['payload'],
                          payload_sha256=payload_sha(row['payload']), status='reserved',
                          started_utc=utc(), provider='chatgpt', requested_model=MODEL,
                          server_model=None, request_id=None, response_id=None,
                          usage=None, answer='', error_code=None)
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?)',
                            (row['sequence'], row['question_id'], row['arm'], json.dumps(record)))
            self.db.commit()
            return record
        except BaseException:
            self.db.rollback()
            raise

    def save(self, record):
        with self.db:
            self.db.execute('UPDATE attempts SET record=? WHERE sequence=?',
                            (json.dumps(record), record['sequence']))

    def pin_model(self, model):
        require(isinstance(model, str) and re.fullmatch(r'gpt-5\.6-luna(?:-\d{4}-\d{2}-\d{2})?', model), 'MODEL_MISMATCH')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('server_model', model))
        require(self.meta('server_model') == model, 'MODEL_CHANGED')

    def stop(self, code):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('stop', code))


class GuardedTransport(ResponsesTransport):
    """Guard the actual POST; observe server frames before metadata is discarded."""
    def __init__(self, ledger, row, registration):
        self.ledger, self.row, self.registration = ledger, row, registration
        self.record = None
        self.dispatched = False
        self.completed = False
        self.refusal = False

    def stream(self, credential, provider, model, messages, cancellation, **kwargs):
        require(provider == 'chatgpt' and model == MODEL, 'PROVIDER_MODEL')
        try:
            yield from super().stream(credential, provider, model, messages, cancellation, **kwargs)
        except BaseException as exc:
            if self.record and not self.record.get('error_code'):
                self.record['error_code'] = getattr(exc, 'code', type(exc).__name__)
                self.ledger.save(self.record)
            raise

    def _response(self, session, method, path, credential, **kwargs):
        from urllib3.util.retry import Retry
        require((method, path) == ('POST', '/responses'), 'UNEXPECTED_REQUEST')
        require(not self.dispatched, 'DUPLICATE_DISPATCH')
        require(kwargs.get('json') == self.row['payload'], 'PAYLOAD_CHANGED')
        for adapter in session.adapters.values():
            adapter.max_retries = Retry(total=0, connect=0, read=0, redirect=0, status=0, other=0)
        self.record = self.ledger.reserve(self.row)
        self.record['registration_pseudonym'] = self.registration
        self.ledger.save(self.record)
        self.dispatched = True
        request = session.request

        def observed_request(*args, **kw):
            response = request(*args, **kw)
            self.record['http_status'] = response.status_code
            self.record['request_id'] = response.headers.get('x-request-id')
            self.ledger.save(self.record)
            return response

        session.request = observed_request
        response = super()._response(session, method, path, credential, **kwargs)
        return response

    def _frames(self, response, cancellation):
        for frame in super()._frames(response, cancellation):
            kind = frame.get('type', '')
            result = frame.get('response') or {}
            if result.get('model'):
                self.record['server_model'] = result['model']
                self.ledger.save(self.record)
                self.ledger.pin_model(result['model'])
            if result.get('id'):
                self.record['response_id'] = result['id']
            if result.get('usage') is not None:
                # Only documented token counters; no raw protocol/headers/reasoning.
                usage = result['usage']
                self.record['usage'] = {k: usage.get(k) for k in
                    ('input_tokens', 'output_tokens', 'total_tokens')}
                for field, key in [('input_tokens_details', 'cached_tokens'),
                                   ('output_tokens_details', 'reasoning_tokens')]:
                    details = usage.get(field) or {}
                    self.record['usage'][key] = details.get(key)
            if kind in {'response.output_text.delta', 'response.refusal.delta'}:
                self.record['answer'] += frame.get('delta', '')
                self.refusal |= kind == 'response.refusal.delta'
            item = frame.get('item') or {}
            output = result.get('output') or []
            if item and item.get('type') not in {'message', 'reasoning'}:
                raise CloudError('UNEXPECTED_TOOL', 'Unexpected output; nothing executed.')
            require(all(i.get('type') in {'message', 'reasoning'} for i in output), 'UNEXPECTED_TOOL')
            if kind in {'response.failed', 'response.incomplete', 'error'}:
                error = result.get('error') or frame.get('error') or {}
                code = error.get('code') or frame.get('code')
                self.record['server_error_code'] = code if isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', code) else None
                self.ledger.save(self.record)
                raise CloudError('SERVER_STREAM_FAILURE', 'Server returned a failure event.')
            if kind == 'response.completed':
                require(result.get('status') == 'completed', 'INCOMPLETE')
                # Require a server identity on the terminal event, not an adapter echo.
                require(bool(result.get('model')), 'MISSING_SERVER_MODEL')
                self.completed = True
                if any(p.get('type') == 'refusal' for i in output for p in i.get('content', [])):
                    self.refusal = True
            self.ledger.save(self.record)
            yield frame


def execute(ledger, row, credential, registration, watchdog=WATCHDOG):
    from laew.agent import Agent, AgentConfig, AgentExecutor
    from laew.llm.cloud import OpenAIProvider
    transport = GuardedTransport(ledger, row, registration)
    cancellation = Cancellation()
    wall_start = ledger.meta('started_epoch')
    remaining = CEILING - (time.time() - float(wall_start)) if wall_start else CEILING
    timer = threading.Timer(max(.001, min(watchdog, remaining)), cancellation.cancel)
    timer.daemon = True
    started = time.perf_counter()
    code = None
    try:
        # No persistent history, workers, tools, callbacks, memory, or RAG services.
        provider = OpenAIProvider('chatgpt', credential=credential, transport=transport,
                                  timeout=WATCHDOG)
        executor = AgentExecutor(Agent(AgentConfig(model=MODEL, system_prompt=INSTRUCTIONS,
            project_scope=False, max_iterations=1, history_path=None), provider=provider, tools=[]))
        # The exact context is supplied separately by the offline verified loader.
        require(hashlib.sha256(row['context'].encode()).hexdigest() == row['context_sha256'])
        executor.knowledge_context = row['context']
        timer.start()
        result = executor.run(row['payload']['input'][0]['content'], cancellation=cancellation)
        require(result.success and transport.completed, 'EXECUTOR_FAILURE')
        require(not transport.refusal, 'REFUSAL')
        require(not cancellation.is_set(), 'TIMEOUT')
        transport.record['executor_answer'] = result.final_response
        if not transport.record['answer']:
            transport.record['answer'] = result.final_response
        transport.record['status'] = 'completed'
    except BaseException as exc:
        code = ('TIMEOUT' if cancellation.is_set() else
                (transport.record or {}).get('error_code') or getattr(exc, 'code', type(exc).__name__))
        ledger.stop(code)
        if transport.record:
            transport.record.update(status='failed', error_code=code)
    finally:
        timer.cancel()
        if transport.record:
            transport.record.update(ended_utc=utc(), latency_ms=round((time.perf_counter() - started)*1000, 3))
            transport.record['answer_sha256'] = hashlib.sha256(transport.record['answer'].encode()).hexdigest()
            ledger.save(transport.record)
    return code is None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-root', type=Path, required=True)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    root = args.artifact_root.resolve()
    require(root.is_dir() and not any((p / '.obsidian').exists() for p in (root, *root.parents)))
    repo = Path(__file__).resolve().parents[2]
    require(not root.is_relative_to(repo))
    report, rows = verify_inputs(repo, args.data, args.previous)
    write(root / ('integrity-' + str(time.time_ns()) + '.json'), report)
    ledger = Ledger(root / 'attempts.sqlite3', REQUESTS_SHA)
    if not args.live:
        ledger.close()
        print(json.dumps(report, indent=2))
        return 0
    require((root / 'usage-acceptance.json').is_file(), 'USAGE_ACCEPTANCE_REQUIRED')
    require(read(root / 'usage-acceptance.json').get('accepted') is True, 'USAGE_ACCEPTANCE_REQUIRED')
    require(not ledger.meta('stop'), 'EXPERIMENT_STOPPED')
    require(not any(r['status'] != 'completed' for r in ledger.records()), 'UNCERTAIN_DISPATCH')
    cloud = CloudChatService()
    try:
        accounts = [a for a in cloud.auth.status()['accounts'] if a['authenticated']]
        require(len(accounts) == 1, 'EVAL_ACCOUNT')
        account = accounts[0]['id']
        registration = hashlib.sha256(account.encode()).hexdigest()[:16]
        require(MODEL in [m['id'] for m in cloud.transport.models(cloud.credential('chatgpt', account)[0], 'chatgpt')], 'MODEL_UNAVAILABLE')
        write(root / ('live-preflight-' + str(time.time_ns()) + '.json'), dict(utc=utc(),
              provider='chatgpt', registration_pseudonym=registration, model=MODEL, catalog_verified=True,
              plan_percentage=None, retries=0, watchdog=WATCHDOG, wall_ceiling=CEILING,
              generation_settings=read(args.previous / 'laew-evidence-audit-v1/generator-only/plan.json')))
        traces = read(args.data / 'stage-2b2-real-world-retrieval-20261113-v2/run-v2/retrieval-traces.json')
        contexts = {(t['question_id'], t['arm']): t['enclosing_context'] for t in traces if t['split'] == 'pilot'}
        for row in rows[len(ledger.records()):]:
            row['context'] = contexts[row['question_id'], row['arm']]
            success = execute(ledger, row, lambda: cloud.credential('chatgpt', account)[0], registration)
            record = ledger.records()[-1] if ledger.records() else {}
            print(json.dumps({k: record.get(k) for k in ('sequence', 'question_id', 'arm', 'status', 'error_code', 'latency_ms')}), flush=True)
            if not success:
                break
    except BaseException as exc:
        ledger.stop(getattr(exc, 'code', type(exc).__name__))
        raise
    finally:
        cloud.close()
        write(root / ('attempt-history-' + str(time.time_ns()) + '.json'), ledger.records())
        ledger.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
