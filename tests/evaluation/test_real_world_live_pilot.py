"""Intercept the actual executor/provider/HTTP boundary; never contact a service."""
import copy
import hashlib
import json
import socket
import time

import pytest
import requests

from laew.cloud_chat import CloudError
from laew.eval.real_world_answer_plan import prepare
from laew.eval.real_world_live_pilot import Ledger, GuardedTransport, execute
from laew.llm.cancellation import Cancellation


@pytest.fixture
def rows():
    questions, traces = [], []
    for family in ('P01', 'P02', 'P03', 'P04'):
        for language in ('de', 'en', 'pl'):
            qid = family + '-' + language
            questions.append(dict(id=qid, family_id=family, language=language,
                                  text='Synthetic public question ' + qid, split='pilot'))
            traces.extend(dict(question_id=qid, family_id=family, language=language,
                               split='pilot', arm=arm, enclosing_context='Synthetic source ' + arm)
                          for arm in 'ABC')
    result = prepare(questions, traces)
    for r in result:
        r['context'] = 'Synthetic source ' + r['arm']
    return result


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError('Real network forbidden in pilot acceptance tests')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)


class Response:
    def __init__(self, frames, status=200, delay=0):
        self.frames, self.status_code, self.delay = frames, status, delay
        self.headers = {'x-request-id': 'synthetic-request'}

    def iter_content(self, chunk_size):
        for frame in self.frames:
            if self.delay:
                time.sleep(self.delay)
            yield ('data: ' + json.dumps(frame) + '\n\n').encode()

    def close(self):
        pass


def frames(model='gpt-5.6-luna', usage=True, text='Supported synthetic answer.'):
    result = dict(id='resp_synthetic', status='completed', output=[], model=model)
    if model is None:
        del result['model']
    if usage:
        result['usage'] = dict(input_tokens=90, output_tokens=6, total_tokens=96,
                               input_tokens_details={'cached_tokens': 4},
                               output_tokens_details={'reasoning_tokens': 2})
    return [{'type': 'response.output_text.delta', 'delta': text},
            {'type': 'response.completed', 'response': result}]


def intercept(monkeypatch, ledger, response):
    calls = []
    def request(session, method, url, **kw):
        # Reservation must already be durable in a separate connection.
        other = Ledger(ledger_path(ledger), 'fixture')
        assert other.records()[-1]['status'] == 'reserved'
        other.close()
        assert method == 'POST' and url == 'https://api.openai.com/v1/responses'
        assert kw['allow_redirects'] is False
        assert all(a.max_retries.total == 0 and a.max_retries.read == 0
                   for a in session.adapters.values())
        calls.append(kw['json'])
        if isinstance(response, Exception):
            raise response
        return response
    monkeypatch.setattr(requests.Session, 'request', request)
    return calls


def ledger_path(ledger):
    return ledger.db.execute('PRAGMA database_list').fetchone()[2]


def test_full_36_dispatches_and_37th_rejected(tmp_path, rows, monkeypatch):
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    calls = intercept(monkeypatch, ledger, Response(frames()))
    for row in rows:
        assert execute(ledger, row, lambda: 'synthetic-oauth', 'pseudonym')
    assert len(calls) == 36
    assert [r['payload'] for r in ledger.records()] == [r['payload'] for r in rows]
    assert all(r['server_model'] == 'gpt-5.6-luna' and r['usage']['reasoning_tokens'] == 2
               and r['request_id'] == 'synthetic-request' for r in ledger.records())
    with pytest.raises(CloudError, match='ATTEMPT_CAP'):
        ledger.reserve(rows[0])
    ledger.close()


def test_restart_after_reservation_never_redispatches(tmp_path, rows):
    path = tmp_path / 'attempts.db'
    ledger = Ledger(path, 'fixture')
    ledger.reserve(rows[0]); ledger.close()
    ledger = Ledger(path, 'fixture')
    with pytest.raises(CloudError, match='UNCERTAIN_DISPATCH'):
        ledger.reserve(rows[0])
    assert len(ledger.records()) == 1
    ledger.close()


def test_duplicate_order_fixture_and_stopped_guards(tmp_path, rows):
    path = tmp_path / 'attempts.db'
    ledger = Ledger(path, 'fixture')
    with pytest.raises(CloudError, match='ORDER'):
        ledger.reserve(rows[1])
    record = ledger.reserve(rows[0]); record['status'] = 'completed'; ledger.save(record)
    with pytest.raises(CloudError, match='DUPLICATE'):
        ledger.reserve(rows[0])
    ledger.stop('TEST')
    with pytest.raises(CloudError, match='EXPERIMENT_STOPPED'):
        ledger.reserve(rows[1])
    ledger.close()
    with pytest.raises(CloudError, match='INTEGRITY'):
        Ledger(path, 'different fixture')


@pytest.mark.parametrize('failure', ['wrong_model', 'missing_model', 'stream_end', 'usage_after_text',
                                  'tool_added', 'tool_terminal', 'auth', 'rate_limit', 'http500',
                                  'timeout_before', 'timeout_after', 'refusal'])
def test_failure_stops_and_preserves_attempt(tmp_path, rows, monkeypatch, failure):
    fs = frames()
    response = Response(fs)
    if failure == 'wrong_model':
        fs[-1]['response']['model'] = 'gpt-6-luna'
    elif failure == 'missing_model':
        del fs[-1]['response']['model']
    elif failure == 'stream_end':
        fs.pop()
    elif failure == 'usage_after_text':
        fs[-1] = {'type': 'response.failed', 'response': {'error': {'code': 'usage_limit_reached'}}}
    elif failure == 'tool_added':
        fs.insert(0, {'type': 'response.output_item.added', 'item': {'type': 'function_call'}, 'output_index': 0})
    elif failure == 'tool_terminal':
        fs[-1]['response']['output'] = [{'type': 'function_call'}]
    elif failure in {'auth', 'rate_limit', 'http500'}:
        response.status_code = {'auth': 401, 'rate_limit': 429, 'http500': 500}[failure]
    elif failure == 'timeout_before':
        response = requests.Timeout()
    elif failure == 'timeout_after':
        response = Response(fs, delay=.02)
    elif failure == 'refusal':
        fs[0]['type'] = 'response.refusal.delta'
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    calls = intercept(monkeypatch, ledger, response)
    assert not execute(ledger, rows[0], lambda: 'synthetic-oauth', 'pseudonym',
                       watchdog=.03 if failure == 'timeout_after' else 5)
    record = ledger.records()[0]
    assert record['status'] == 'failed' and record['error_code']
    assert ledger.meta('stop') and len(calls) == 1
    if failure in {'stream_end', 'usage_after_text', 'timeout_after'}:
        assert record['answer']
    if failure == 'usage_after_text':
        assert record['server_error_code'] == 'usage_limit_reached'
    with pytest.raises(CloudError):
        ledger.reserve(rows[1])
    ledger.close()


def test_usage_absent_remains_null(tmp_path, rows, monkeypatch):
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    intercept(monkeypatch, ledger, Response(frames(usage=False)))
    assert execute(ledger, rows[0], lambda: 'synthetic-oauth', 'pseudonym')
    assert ledger.records()[0]['usage'] is None
    ledger.close()


@pytest.mark.parametrize('tamper', ['context', 'payload'])
def test_tampering_never_reaches_http(tmp_path, rows, monkeypatch, tamper):
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    calls = intercept(monkeypatch, ledger, Response(frames()))
    row = copy.deepcopy(rows[0])
    if tamper == 'context':
        row['context'] += 'Injected gold'
    else:
        row['payload']['instructions'] += 'Injected gold'
    assert not execute(ledger, row, lambda: 'synthetic-oauth', 'pseudonym')
    assert not calls and not ledger.records()
    ledger.close()


def test_repeated_transport_call_and_forced_final_blocked(tmp_path, rows, monkeypatch):
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    transport = GuardedTransport(ledger, rows[0], 'pseudonym')
    calls = intercept(monkeypatch, ledger, Response(frames()))
    def run():
        return list(transport.stream('synthetic-oauth', 'chatgpt', 'gpt-5.6-luna',
                    rows[0]['payload']['input'], Cancellation(), tools=[],
                    instructions=rows[0]['payload']['instructions']))
    run()
    with pytest.raises(CloudError, match='DUPLICATE_DISPATCH'):
        run()
    assert len(calls) == 1
    ledger.close()


def test_wall_ceiling_and_model_snapshot_change(tmp_path, rows):
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    ledger.pin_model('gpt-5.6-luna-2026-11-01')
    with pytest.raises(CloudError, match='MODEL_CHANGED'):
        ledger.pin_model('gpt-5.6-luna-2026-11-02')
    ledger.db.execute('INSERT INTO meta VALUES (?,?)', ('started_epoch', str(time.time()-5401)))
    ledger.db.commit()
    with pytest.raises(CloudError, match='WALL_CEILING'):
        ledger.reserve(rows[0])
    ledger.close()


def test_executor_forced_final_cannot_dispatch_twice(tmp_path, rows, monkeypatch):
    from laew.agent import AgentExecutor
    from laew.llm.base import LLMMessage, MessageRole
    original_run = AgentExecutor.run
    def force_final(executor, *args, **kwargs):
        original_run(executor, *args, **kwargs)
        # Exercise the same provider entry point with an executor continuation.
        executor.agent.provider.generate_tools([
            LLMMessage(MessageRole.USER, 'Forced final after max iterations')],
            'gpt-5.6-luna', [])
    monkeypatch.setattr(AgentExecutor, 'run', force_final)
    ledger = Ledger(tmp_path / 'attempts.db', 'fixture')
    calls = intercept(monkeypatch, ledger, Response(frames()))
    assert not execute(ledger, rows[0], lambda: 'synthetic-oauth', 'pseudonym')
    assert len(calls) == 1 and len(ledger.records()) == 1
    assert ledger.meta('stop') == 'DUPLICATE_DISPATCH'
    ledger.close()


def test_concurrent_process_connection_cannot_reserve_next(tmp_path, rows):
    path = tmp_path / 'attempts.db'
    one, two = Ledger(path, 'fixture'), Ledger(path, 'fixture')
    one.reserve(rows[0])
    with pytest.raises(CloudError, match='UNCERTAIN_DISPATCH'):
        two.reserve(rows[1])
    assert len(two.records()) == 1
    one.close(); two.close()
