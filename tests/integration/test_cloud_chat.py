"""Cloud credentials and Responses parsing with controlled, offline resources."""

import copy
import json
from unittest.mock import Mock

import pytest
import requests

from laew.cloud_chat import CloudChatService, CloudError, ResponsesTransport
from laew.llm.cancellation import Cancellation
from laew.web import WorkspaceService


class Response:
    status_code = 200
    def __init__(self, frames=(), status=200):
        self.frames, self.status_code, self.closed = frames, status, False
    def close(self): self.closed = True
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def iter_content(self, **kwargs):
        for frame in self.frames:
            yield b'data: ' + json.dumps(frame, ensure_ascii=False).encode() + b'\n\n'


class Session:
    def __init__(self, response): self.response, self.calls = response, []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs)); return self.response


def completed():
    return {"type": "response.completed", "response": {"status": "completed", "output": [{"type": "message"}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}}}


@pytest.mark.parametrize('provider', ['openai-api', 'chatgpt'])
def test_responses_payload_stream_and_usage(monkeypatch, provider):
    session = Session(Response([{"type": "response.output_text.delta", "delta": "Zażółć 🐕"}, completed()]))
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: session)
    monkeypatch.setenv('LAEW_BASE_URL', 'http://localhost:9999/unsafe')
    events = list(ResponsesTransport().stream('secret-fixture', provider, 'exact-model',
                  [{'role': 'user', 'content': 'hello'}], Cancellation()))
    assert events[0]['text'] == 'Zażółć 🐕'
    assert events[1]['usage']['total_tokens'] == 15
    (method, url), args = session.calls[0]
    assert method == 'POST' and url == 'https://api.openai.com/v1/responses'
    payload = args['json']
    assert payload['store'] is False and payload['stream'] is True
    assert not {'tools', 'background', 'previous_response_id', 'temperature'}.intersection(payload)
    assert ('max_output_tokens' in payload) is (provider == 'openai-api')
    assert payload['model'] == 'exact-model'
    assert session.response.closed


@pytest.mark.parametrize('status,code', [(400,'INVALID_REQUEST'),(401,'AUTH_REQUIRED'),(403,'ACCESS_DENIED'),
                                      (404,'MODEL_UNAVAILABLE'),(429,'USAGE_LIMIT'),(500,'SERVER_ERROR'),(302,'SERVER_ERROR')])
def test_http_errors_never_fall_back_or_retry(monkeypatch, status, code):
    session = Session(Response(status=status))
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: session)
    with pytest.raises(CloudError) as exc:
        list(ResponsesTransport().stream('private-key', 'openai-api', 'exact', [], Cancellation()))
    assert exc.value.code == code and 'private-key' not in str(exc.value)
    assert len(session.calls) == 1 and session.response.closed


@pytest.mark.parametrize('frames', [[], [{'type':'response.incomplete'}], [{'type':'response.failed'}],
                                  [{'type':'error', 'error': {'message':'private-fixture'}}], [completed() | {'response':{'status':'in_progress'}}]])
def test_missing_or_failed_completion_is_an_error(monkeypatch, frames):
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: Session(Response(frames)))
    with pytest.raises(CloudError):
        list(ResponsesTransport().stream('secret', 'chatgpt', 'exact', [], Cancellation()))


def test_refusal_is_visible_and_tool_output_cannot_execute(monkeypatch):
    session = Session(Response([{'type':'response.refusal.delta','delta':'Cannot help.'}, completed()]))
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: session)
    assert list(ResponsesTransport().stream('secret', 'chatgpt', 'exact', [], Cancellation()))[0]['text'] == 'Cannot help.'
    session.response = Response([{'type':'response.completed','response':{'status':'completed','output':[{'type':'function_call'}]}}])
    with pytest.raises(CloudError, match='nothing was executed'):
        list(ResponsesTransport().stream('secret', 'chatgpt', 'exact', [], Cancellation()))


class Auth:
    def credential(self, account): return 'oauth-fixture'
    def status(self, *args): return {'accounts': []}
    def close(self): pass


class Transport:
    def __init__(self): self.requests = []
    def stream(self, key, provider, model, messages, cancellation, **kwargs):
        self.requests.append(copy.deepcopy(messages))
        yield {'type':'delta', 'text':'```tool_call\n{"tool":"FilesystemTool","operation":"write_file"}\n```'}
        yield {'type':'usage','usage':{'total_tokens':15}}


def test_workbench_cloud_uses_chief_and_preserves_history_on_model_switch(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'api-fixture')
    project = tmp_path / 'project'; project.mkdir()
    service = WorkspaceService(tmp_path / 'manifest', project, tmp_path)
    monkeypatch.setattr('laew.web.load_manifest', lambda _: {})
    monkeypatch.setattr('laew.web.build_shared_tools', lambda *a, **kw: [])
    transport = Transport()
    service._cloud = CloudChatService(Auth(), transport)
    session, project_id = 'browser-session-123', service.active_project['id']
    events = []
    service.stream_chat('hello', 'openai-api', project_id, events.append, session,
                        Cancellation(), model='exact')
    agent, executor, broker = service._agent, service._executor, service._permissions
    assert events[-1]['type'] == 'done'
    service.stream_chat('second turn', 'openai-api', project_id, events.append, session,
                        Cancellation(), model='different-model')
    assert service._agent is agent and service._executor is executor and service._permissions is broker
    assert len(transport.requests[1]) == 3
    assert service.active_project['id'] == project_id
    status, history = service.cloud_request('/api/cloud/history', {'session_id':session,'project_id':project_id})
    assert status == 200 and len(history['messages']) == 4
    assert not service.cloud_request('/api/cloud/history', {'session_id':'other-session-1234','project_id':project_id})[1]['messages']
    service.cloud_request('/api/cloud/new', {'session_id':session,'project_id':project_id})
    assert not agent.history


def test_cancelled_provider_does_not_return_complete_response(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'api-fixture')
    token = Cancellation()
    class CancelTransport:
        def stream(self, *args, **kwargs):
            yield {'type':'delta','text':'partial'}
            token.cancel()
            yield {'type':'usage','usage':{}}
    cloud = CloudChatService(Auth(), CancelTransport())
    from laew.agent.executor import StreamCancelled
    with pytest.raises(StreamCancelled):
        cloud.provider('openai-api').generate_tools([], 'exact', [], cancellation=token)


def test_missing_api_key_and_invalid_input_are_explicit(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    cloud = CloudChatService(Auth(), Transport())
    with pytest.raises(CloudError) as error:
        cloud.provider('openai-api').generate([], 'exact')
    assert error.value.code == 'AUTH_REQUIRED'
    assert not cloud.transport.requests


def test_bounded_frames_and_invalid_json_are_errors(monkeypatch):
    class Raw(Response):
        def iter_content(self, **kwargs): yield self.body
    response = Raw(); session = Session(response)
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: session)
    for body in (b'data: invalid\n\n', b'data: []\n\n', b'x' * (4 * 1024 * 1024 + 1)):
        response.body = body
        with pytest.raises(CloudError): list(ResponsesTransport().stream('secret', 'chatgpt', 'exact', [], Cancellation()))


@pytest.mark.parametrize('exception,code', [(requests.Timeout(), 'TIMEOUT'), (requests.ConnectionError(), 'UNAVAILABLE')])
def test_network_failures_are_not_empty_success(monkeypatch, exception, code):
    session = Session(Response())
    session.request = Mock(side_effect=exception)
    monkeypatch.setattr('laew.cloud_chat.cancellable_session', lambda _: session)
    with pytest.raises(CloudError) as exc:
        list(ResponsesTransport().stream('secret', 'openai-api', 'exact', [], Cancellation()))
    assert exc.value.code == code and session.request.call_count == 1
