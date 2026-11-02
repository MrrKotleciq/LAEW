"""Real HTTP cloud cancellation and Workbench routing on isolated loopback ports."""

import json
import select
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from laew.cloud_chat import CloudChatService
from laew.web import WorkspaceService, make_handler


@pytest.mark.parametrize('phase', ['headers', 'reasoning', 'text'])
@pytest.mark.parametrize('provider', ['openai-api', 'chatgpt'])
def test_http_stop_interrupts_cloud_without_retry(tmp_path, monkeypatch, phase, provider):
    started, disconnected = threading.Event(), threading.Event()
    calls = []
    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            calls.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            if phase != 'headers':
                self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.end_headers()
                event = {'type':'response.in_progress'} if phase == 'reasoning' else {'type':'response.output_text.delta','delta':'partial'}
                self.wfile.write(('data: ' + json.dumps(event) + '\n\n').encode()); self.wfile.flush()
            started.set()
            readable, _, _ = select.select([self.connection], [], [], 5)
            if readable:
                try:
                    if not self.connection.recv(1): disconnected.set()
                except ConnectionResetError: disconnected.set()
    upstream = ThreadingHTTPServer(('127.0.0.1',0), Upstream)
    upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True); upstream_thread.start()
    monkeypatch.setattr('laew.cloud_chat.API_ROOT', f'http://127.0.0.1:{upstream.server_port}')
    monkeypatch.setenv('OPENAI_API_KEY','synthetic-key')
    class Auth:
        def credential(self, account): return 'synthetic-oauth-token'
        def close(self): pass
    project = tmp_path / 'project'; project.mkdir()
    service = WorkspaceService(tmp_path / 'manifest', project, tmp_path)
    service._cloud = CloudChatService(Auth())
    monkeypatch.setattr('laew.web.load_manifest', lambda _: {})
    monkeypatch.setattr('laew.web.build_shared_tools', lambda *a, **kw: [])
    workbench = ThreadingHTTPServer(('127.0.0.1',0), make_handler(service))
    workbench_thread = threading.Thread(target=workbench.serve_forever, daemon=True); workbench_thread.start()
    session = '11111111-1111-4111-8111-111111111111'
    run = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    base = f'http://127.0.0.1:{workbench.server_port}'
    response = None
    try:
        response = requests.post(base + '/api/chat', json={'message':'synthetic prompt','provider':provider,
            'model':'fixture','session_id':session,'run_id':run,'project_id':service.active_project['id'], 'account_id':'fixture'},
            stream=True, timeout=5)
        assert started.wait(3)
        stopped = requests.post(base + '/api/chat/cancel',json={'session_id':session,'run_id':run},timeout=3)
        assert stopped.json()['accepted'] and disconnected.wait(3)
        events = [json.loads(line) for line in response.iter_lines() if line]
        assert not any(event['type'] == 'done' for event in events)
        deadline = time.monotonic() + 2
        while service._runs and time.monotonic() < deadline: time.sleep(.01)
        assert not service._runs and len(calls) == 1
        assert all(m.role.value != "assistant" for m in service._agent.history)
    finally:
        if response is not None: response.close()
        service.close()
        workbench.shutdown(); workbench.server_close(); workbench_thread.join(3)
        upstream.shutdown(); upstream.server_close(); upstream_thread.join(3)
