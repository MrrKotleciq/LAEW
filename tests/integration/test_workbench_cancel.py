"""Cancellation interrupts a quiet upstream stream without production services."""

import json
import select
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
import pytest

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.cancellation import Cancellation
from laew.llm.llamacpp import LlamaCppProvider
from laew.llm.ollama import OllamaProvider
from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool
from laew.web import WorkspaceService, make_handler


@pytest.mark.parametrize("before_headers", [False, True])
@pytest.mark.parametrize("provider_name", ["llamacpp", "ollama"])
def test_cancel_interrupts_suppressed_tool_stream(tmp_path, before_headers, provider_name):
    sent = threading.Event()
    disconnected = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            if not before_headers:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                if provider_name == "llamacpp":
                    frame = {"choices": [{"delta": {"content": "```tool_call"}}]}
                    payload = "data: " + json.dumps(frame) + "\n\n"
                else:
                    payload = json.dumps({"message": {"content": "```tool_call"}}) + "\n"
                self.wfile.write(payload.encode())
                self.wfile.flush()
            sent.set()
            readable, _, _ = select.select([self.connection], [], [], 5)
            if readable:
                try:
                    if not self.connection.recv(1): disconnected.set()
                except ConnectionResetError:
                    disconnected.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = Cancellation()
    provider_url = f"http://127.0.0.1:{server.server_port}"
    provider = (LlamaCppProvider("fixture", provider_url, timeout=2, stream_timeout=5)
                if provider_name == "llamacpp" else OllamaProvider(provider_url, timeout=5))
    provider.is_available = lambda: True
    agent = Agent(AgentConfig(model="fixture"), provider=provider, tools=[])
    executor = AgentExecutor(agent)
    results = []
    worker = threading.Thread(target=lambda: results.append(executor.run("test", stream=True,
                                         on_delta=lambda _: None, cancellation=token)), daemon=True)
    try:
        worker.start()
        assert sent.wait(3)
        token.cancel()
        worker.join(3)
        assert not worker.is_alive()
        assert not results[0].success and "cancelled" in results[0].error
        assert disconnected.wait(3)
    finally:
        token.cancel()
        worker.join(6)
        server.shutdown()
        server.server_close()
        thread.join(3)


def test_run_identity_and_early_stop_are_isolated(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    service = WorkspaceService(tmp_path / "manifest", project, tmp_path)
    session = "11111111-1111-4111-8111-111111111111"
    other = "22222222-2222-4222-8222-222222222222"
    run = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    assert service.cancel_run(session, run)
    token = service.register_run(session, run)
    assert token.is_set()
    other_token = service.register_run(other, run)
    assert not other_token.is_set()
    assert service.cancel_run(other, run)
    assert other_token.is_set()
    assert not service.cancel_run("bad", run)
    service.unregister_run(session, run, token)
    service.unregister_run(other, run, other_token)
    assert not service._runs


def test_stop_cancels_pending_approval_without_writing(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=5)
    token = Cancellation()
    events = []
    started = threading.Event()
    def emit(event):
        events.append(event)
        if event["type"] == "approval": started.set()
    def run():
        from laew.agent.executor import StreamCancelled
        try:
            broker.call(tool, "write_knowledge_note", {"file_path": "@knowledge/test.md",
                        "expected_sha256": "", "content": "---\ntype: docs\nscope: global\n---\n"},
                        emit, "s", cancellation=token)
        except StreamCancelled:
            pass
    worker = threading.Thread(target=run, daemon=True); worker.start()
    assert started.wait(2)
    token.cancel(); worker.join(2)
    assert not worker.is_alive()
    assert not broker.decide(events[0]["id"], "allow", "s")
    assert not (vault / "test.md").exists()


def test_http_stop_reaches_a_quiet_workbench_run(tmp_path):
    started = threading.Event()
    project = tmp_path / "project"; project.mkdir()
    service = WorkspaceService(tmp_path / "manifest", project, tmp_path)
    service._ensure_runtime = lambda *_: None
    class Executor:
        def run(self, prompt, **kwargs):
            started.set()
            while not kwargs["cancellation"].is_set():
                time.sleep(.01)
            from laew.agent.executor import StreamCancelled
            raise StreamCancelled()
    service._executor = Executor()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(service))
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    session = "11111111-1111-4111-8111-111111111111"
    run = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    base = f"http://127.0.0.1:{server.server_port}"
    chat = None
    try:
        chat = requests.post(base + "/api/chat", json={"message": "test", "session_id": session,
                             "run_id": run}, stream=True, timeout=3)
        assert started.wait(2)
        response = requests.post(base + "/api/chat/cancel", json={"session_id": session, "run_id": run}, timeout=3)
        assert response.json()["accepted"]
        assert list(chat.iter_lines())
        deadline = time.monotonic() + 2
        while service._runs and time.monotonic() < deadline:
            time.sleep(.01)
        assert not service._runs
    finally:
        if chat is not None: chat.close()
        server.shutdown(); server.server_close(); thread.join(3)
