"""Evaluation-only S0/S1 at-most-once dispatch. No live CLI or authorization.

The public CLI is deliberately offline. A future authorized orchestrator must
verify the sealed package, provider registration and source-owner gate before
calling execute. Mock tests inject the HTTP boundary, never real credentials.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from laew.eval.real_world_live_pilot import (
    GuardedTransport as HistoricalTransport, payload_sha, require, utc,
)

MAX_ATTEMPTS = 48
WALL_CEILING = 5400


class Ledger:
    """Bind an immutable ordered schedule to one durable experiment ledger."""

    def __init__(self, path, rows):
        require(0 < len(rows) <= MAX_ATTEMPTS, 'SCHEDULE_CAP')
        require([r['sequence'] for r in rows] == list(range(1, len(rows) + 1)), 'ORDER')
        require(len({(r['question_id'], r['arm'], r['variant']) for r in rows}) == len(rows), 'DUPLICATE')
        self.rows = copy.deepcopy(rows)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('PRAGMA synchronous=FULL')
        require(self.db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS attempts(
            sequence INTEGER PRIMARY KEY CHECK(sequence BETWEEN 1 AND 48),
            question_id TEXT NOT NULL, arm TEXT NOT NULL, variant TEXT NOT NULL,
            record TEXT NOT NULL, UNIQUE(question_id,arm,variant));
        ''')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('fixture', payload_sha(rows)))
        require(self.meta('fixture') == payload_sha(rows), 'FIXTURE_CHANGED')

    def check_next(self, row):
        records = self.records()
        require(not self.meta('stop'), 'EXPERIMENT_STOPPED')
        require(len(records) < len(self.rows), 'ATTEMPT_CAP')
        require(all(r['status'] == 'completed' for r in records), 'UNCERTAIN_DISPATCH')
        require(row == self.rows[len(records)], 'REQUEST_IDENTITY')
        started = self.meta('started_epoch')
        require(started is None or time.time() - float(started) < WALL_CEILING, 'WALL_CEILING')

    def close(self):
        self.db.close()

    def meta(self, key):
        row = self.db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def records(self):
        records = [json.loads(r[0]) for r in self.db.execute('SELECT record FROM attempts ORDER BY sequence')]
        for index,record in enumerate(records):
            require(index < len(self.rows) and record['sequence'] == index+1, 'LEDGER_ORDER')
            expected=self.rows[index]
            require(record['request_sha256'] == payload_sha(expected) and
                    record['payload_sha256'] == payload_sha(expected['payload']) and
                    record['payload'] == expected['payload'], 'LEDGER_IDENTITY')
            require(record['status'] in ('reserved','completed','failed'), 'LEDGER_STATUS')
        return records

    def reserve(self, row):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.check_next(row)
            record = dict(sequence=row['sequence'], question_id=row['question_id'],
                          arm=row['arm'], variant=row['variant'], status='reserved',
                          context_sha256=row['context_sha256'], payload=row['payload'],
                          payload_sha256=payload_sha(row['payload']), request_sha256=payload_sha(row),
                          started_utc=utc(), provider='chatgpt', requested_model='gpt-5.6-luna',
                          server_model=None, request_id=None, response_id=None, usage=None,
                          answer='', error_code=None)
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,?,?)',
                            (row['sequence'], row['question_id'], row['arm'], row['variant'], json.dumps(record)))
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('started_epoch', str(time.time())))
            self.db.commit()
            return record
        except BaseException:
            self.db.rollback()
            raise

    def save(self, record):
        with self.db:
            old = self.db.execute('SELECT record FROM attempts WHERE sequence=?', (record['sequence'],)).fetchone()
            require(old is not None, 'UNKNOWN_RESERVATION')
            original = json.loads(old[0])
            for key in ('sequence', 'question_id', 'arm', 'variant', 'payload', 'payload_sha256', 'request_sha256'):
                require(record[key] == original[key], 'RESERVATION_CHANGED')
            require(original['status'] == 'reserved', 'TERMINAL_RESERVATION')
            self.db.execute('UPDATE attempts SET record=? WHERE sequence=?', (json.dumps(record), record['sequence']))

    def stop(self, code):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('stop', code))

    def pin_model(self, model):
        require(model == 'gpt-5.6-luna', 'MODEL_MISMATCH')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('server_model', model))
        require(self.meta('server_model') == model, 'MODEL_CHANGED')


class GuardedTransport(HistoricalTransport):
    """Reuse the existing OAuth boundary with stricter terminal usage checks."""

    def _response(self, session, method, path, credential, **kwargs):
        require(bool(self.registration), 'PROVIDER_REGISTRATION')
        with self.ledger.db:
            self.ledger.db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)',
                                   ('registration', self.registration))
        require(self.ledger.meta('registration') == self.registration, 'REGISTRATION_CHANGED')
        return super()._response(session, method, path, credential, **kwargs)

    def _frames(self, response, cancellation):
        for frame in super()._frames(response, cancellation):
            if frame.get('type') == 'response.completed':
                usage = self.record.get('usage') or {}
                keys = ('input_tokens', 'output_tokens', 'total_tokens', 'cached_tokens', 'reasoning_tokens')
                require(all(type(usage.get(k)) is int and usage[k] >= 0 for k in keys), 'MISSING_USAGE')
                require(usage['input_tokens'] + usage['output_tokens'] == usage['total_tokens'], 'INVALID_USAGE')
                require(usage['cached_tokens'] <= usage['input_tokens'] and
                        usage['reasoning_tokens'] <= usage['output_tokens'], 'INVALID_USAGE')
                require(0 < usage['input_tokens'] <= 12000 and
                        0 < usage['output_tokens'] <= 4096, 'UNEXPECTED_USAGE')
                require(bool(self.record.get('response_id')), 'MISSING_RESPONSE_ID')
            yield frame


def execute(ledger, row, credential, registration, *, authorized=False, watchdog=120):
    """One fresh executor, no retry. Authorization defaults to denied."""
    require(authorized is True, 'SEPARATE_AUTHORIZATION_REQUIRED')
    from laew.agent import Agent, AgentConfig, AgentExecutor
    from laew.eval.real_world_answer_plan import INSTRUCTIONS, MODEL
    from laew.llm.cloud import OpenAIProvider
    from laew.llm.cancellation import Cancellation
    import threading

    transport = GuardedTransport(ledger, row, registration)
    cancellation = Cancellation()
    timer = threading.Timer(watchdog, cancellation.cancel)
    timer.daemon = True
    started = time.perf_counter()
    code = None
    try:
        ledger.check_next(row)
        require(hashlib.sha256(row['context'].encode()).hexdigest() == row['context_sha256'], 'CONTEXT')
        provider = OpenAIProvider('chatgpt', credential=credential, transport=transport, timeout=watchdog)
        executor = AgentExecutor(Agent(AgentConfig(model=MODEL, system_prompt=INSTRUCTIONS,
            project_scope=False, max_iterations=1, history_path=None), provider=provider, tools=[]))
        executor.knowledge_context = row['context']
        wall_start = ledger.meta('started_epoch')
        if wall_start:
            timer.interval = max(.001, min(watchdog, WALL_CEILING - (time.time()-float(wall_start))))
        timer.start()
        result = executor.run(row['payload']['input'][0]['content'], cancellation=cancellation)
        require(result.success and transport.completed and not cancellation.is_set(), 'EXECUTOR_FAILURE')
        require(not transport.refusal, 'REFUSAL')
        require(bool(transport.record['answer']), 'EMPTY_ANSWER')
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
            transport.record.update(ended_utc=utc(), latency_ms=round((time.perf_counter()-started)*1000, 3),
                                    answer_sha256=hashlib.sha256(transport.record['answer'].encode()).hexdigest())
            ledger.save(transport.record)
    return code is None


def validate_authorization(authorization, rows, generator_manifest_sha256):
    """Validate the scope of a later user authorization; never create it here."""
    require(authorization.get('explicit_new_user_authorization') is True,
            'SEPARATE_AUTHORIZATION_REQUIRED')
    require(authorization.get('provider') == 'chatgpt' and
            authorization.get('model') == 'gpt-5.6-luna', 'PROVIDER_MODEL')
    require(authorization.get('attempts') == len(rows) == MAX_ATTEMPTS, 'AUTHORIZATION_SCOPE')
    require(authorization.get('generator_manifest_sha256') == generator_manifest_sha256, 'AUTHORIZATION_SCOPE')
    require(authorization.get('plan_percentage_not_predictable_accepted') is True, 'USAGE_ACCEPTANCE')
    gate = authorization.get('source_owner_review') or {}
    require(bool(gate.get('reviewer_id')) and gate.get('visible_attribution_adequate') is True,
            'SOURCE_OWNER_REVIEW_REQUIRED')
    expected = sorted({(r['question_id'],r['arm']) for r in rows})
    require(gate.get('reviewed_question_arm_pairs') == [list(p) for p in expected], 'SOURCE_OWNER_SCOPE')
    require(gate.get('critical_unresolved_attribution_issues') == [], 'SOURCE_OWNER_UNRESOLVED')


def run_authorized(root, authorization):
    """Future orchestration entry point, deliberately absent from any live CLI.

    Requires a newly supplied authorization object and complete source-owner
    review. This task calls neither this function nor any provider preflight.
    Uses the single fixed ledger under the sealed experiment root on restart.
    """
    from laew.cloud_chat import CloudChatService
    from laew.eval.serialization_quality_study import verify
    root = Path(root).resolve()
    verify(root)
    contract = json.loads((root/'experiment-contract.json').read_text(encoding='utf-8'))
    rows = json.loads((root/'generator-only/requests.json').read_text(encoding='utf-8'))
    validate_authorization(authorization,rows,contract['generator_manifest_sha256'])
    # Pin every evaluation/provider dependency from the offline preparation.
    runtime = json.loads((root/'runtime-contract.json').read_text(encoding='utf-8'))
    repo = Path(__file__).resolve().parents[2]
    for entry in runtime['files']:
        require(hashlib.sha256((repo/entry['path']).read_bytes()).hexdigest() == entry['sha256'], 'RUNTIME_CHANGED')
    ledger = Ledger(root/'attempts.sqlite3',rows)
    cloud = None
    try:
        require(not ledger.meta('stop'), 'EXPERIMENT_STOPPED')
        records = ledger.records()
        require(all(r['status']=='completed' for r in records), 'UNCERTAIN_DISPATCH')
        if len(records)==len(rows):
            ledger.stop('EXPERIMENT_COMPLETE_NO_FURTHER_GENERATION')
            return
        cloud = CloudChatService()
        accounts = [a for a in cloud.auth.status()['accounts'] if a['authenticated']]
        require(len(accounts)==1, 'EVAL_ACCOUNT')
        account = accounts[0]['id']
        registration = hashlib.sha256(account.encode()).hexdigest()[:16]
        # No model-list probe is needed: exact requested and terminal server
        # identities are checked at the already-bounded Responses boundary.
        for row in rows[len(records):]:
            if not execute(ledger,row,lambda:cloud.credential('chatgpt',account)[0],
                           registration,authorized=True):
                return
        ledger.stop('EXPERIMENT_COMPLETE_NO_FURTHER_GENERATION')
    except BaseException as exc:
        ledger.stop(getattr(exc,'code',type(exc).__name__))
        raise
    finally:
        if cloud:
            cloud.close()
        ledger.close()
