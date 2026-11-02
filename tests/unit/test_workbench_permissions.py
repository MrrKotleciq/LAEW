"""Workbench approval decisions against temporary project files."""

import threading
from pathlib import Path

from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool
from laew.tools.terminal import TerminalTool


def make_tools(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    fs = FilesystemTool(PathResolver(project_root=project, projects_root=tmp_path,
                                     knowledge_root=tmp_path / "knowledge"))
    return project, fs


def test_auto_regular_write_and_hard_boundaries(tmp_path):
    project, fs = make_tools(tmp_path)
    broker = PermissionBroker(project)
    result = broker.call(fs, "write_file", {"file_path": "note.md", "content": "Zażółć\n```python\nprint(1)\n```"}, None)
    assert result.success and "Zażółć" in (project / "note.md").read_text(encoding="utf-8")
    assert not broker.call(fs, "write_file", {"file_path": "../outside.md", "content": "x"}, None).success
    assert not broker.call(fs, "delete_file", {"file_path": "note.md"}, None).success
    assert (project / "note.md").exists()
    terminal = TerminalTool(project)
    assert not broker.call(terminal, "run_command", {"command": "cat ../secret"}, None).success
    assert not broker.call(terminal, "run_command", {"command": "ls | cat"}, None).success


def test_manual_one_time_approval_and_denial(tmp_path):
    project, fs = make_tools(tmp_path)
    broker = PermissionBroker(project, "manual", timeout=2)
    events, results = [], []
    worker = threading.Thread(target=lambda: results.append(broker.call(fs, "write_file", {"file_path": "note.md", "content": "first"}, events.append)))
    worker.start()
    for _ in range(100):
        if events: break
        threading.Event().wait(.01)
    assert events and not (project / "note.md").exists()
    assert not broker.decide("invalid", "allow")
    assert broker.decide(events[0]["id"], "allow")
    worker.join(3)
    assert results[0].success and (project / "note.md").read_text() == "first"
    assert not broker.decide(events[0]["id"], "allow")
    denied_events, denied_results = [], []
    worker = threading.Thread(target=lambda: denied_results.append(broker.call(fs, "delete_file", {"file_path": "note.md"}, denied_events.append)))
    worker.start()
    for _ in range(100):
        if denied_events: break
        threading.Event().wait(.01)
    assert not broker.decide(denied_events[0]["id"], "allow_session")
    assert broker.decide(denied_events[0]["id"], "deny")
    worker.join(3)
    assert not denied_results[0].success and (project / "note.md").exists()


def test_restricted_sensitive_and_timeout(tmp_path):
    project, fs = make_tools(tmp_path)
    restricted = PermissionBroker(project, "restricted")
    assert not restricted.call(fs, "write_file", {"file_path": "note.md", "content": "x"}, None).success
    auto = PermissionBroker(project, "auto", timeout=.01)
    events = []
    result = auto.call(fs, "write_file", {"file_path": "settings.ps1", "content": "x"}, events.append)
    assert events and events[0]["allow_session"] is False
    assert not result.success and not (project / "settings.ps1").exists()


def test_session_grant_is_limited_to_same_operation_path_and_arguments(tmp_path):
    project, fs = make_tools(tmp_path)
    broker = PermissionBroker(project, "manual", timeout=.1)
    events, result = [], []
    worker = threading.Thread(target=lambda: result.append(broker.call(fs, "write_file", {"file_path": "note.md", "content": "first", "overwrite": True}, events.append, "session-a")))
    worker.start()
    for _ in range(100):
        if events: break
        threading.Event().wait(.01)
    assert not broker.decide(events[0]["id"], "allow_session", "session-b")
    assert broker.decide(events[0]["id"], "allow_session", "session-a")
    worker.join(3)
    assert result[0].success
    assert broker.call(fs, "write_file", {"file_path": "note.md", "content": "first", "overwrite": True}, events.append, "session-a").success
    assert not broker.call(fs, "write_file", {"file_path": "note.md", "content": "second", "overwrite": True}, events.append, "session-a").success
    assert not broker.call(fs, "write_file", {"file_path": "note.md", "content": "other session", "overwrite": True}, events.append, "session-b").success
    assert (project / "note.md").read_text() == "first"
    assert not broker.call(fs, "write_file", {"file_path": "other.md", "content": "x"}, events.append, "session-a").success
    assert not (project / "other.md").exists()
    fresh = PermissionBroker(project, "manual", timeout=.01)
    assert not fresh.call(fs, "write_file", {"file_path": "note.md", "content": "x", "overwrite": True}, events.append).success


def test_pending_call_keeps_original_arguments(tmp_path):
    project, fs = make_tools(tmp_path)
    broker = PermissionBroker(project, "manual", timeout=2)
    args = {"file_path": "original.md", "content": "approved"}
    events, result = [], []
    worker = threading.Thread(target=lambda: result.append(broker.call(fs, "write_file", args, events.append, "session-a")))
    worker.start()
    for _ in range(100):
        if events: break
        threading.Event().wait(.01)
    args["file_path"] = "different.md"
    args["content"] = "changed"
    assert broker.decide(events[0]["id"], "allow", "session-a")
    worker.join(3)
    assert result[0].success
    assert (project / "original.md").read_text() == "approved"
    assert not (project / "different.md").exists()


def test_stream_resumes_after_actual_approval(tmp_path):
    from laew.agent import Agent, AgentConfig, AgentExecutor
    from laew.llm.base import LLMResponse
    from laew.web import WorkspaceService
    project, fs = make_tools(tmp_path)
    class Provider:
        def __init__(self): self.calls = 0
        def is_available(self): return True
        def generate(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(content='```tool_call\n{"tool":"FilesystemTool","operation":"write_file","args":{"file_path":"test.txt","content":"ok"}}\n```', model="fake")
            return LLMResponse(content="Done", model="fake")
    service = WorkspaceService(tmp_path / "manifest", project, tmp_path)
    service._ensure_runtime = lambda *_: None
    service._agent = Agent(AgentConfig(), provider=Provider(), tools=[fs])
    service._executor = AgentExecutor(service._agent)
    service._permissions = PermissionBroker(project, "manual", timeout=2)
    events = []
    worker = threading.Thread(target=service.stream_chat,
        args=("write", "manifest", service.active_project["id"], events.append, "browser-a"))
    worker.start()
    for _ in range(200):
        if any(e["type"] == "approval" for e in events): break
        threading.Event().wait(.01)
    request = next(e for e in events if e["type"] == "approval")
    assert not (project / "test.txt").exists()
    assert service._permissions.decide(request["id"], "allow", "browser-a")
    worker.join(5)
    assert not worker.is_alive()
    assert (project / "test.txt").read_text() == "ok"
    assert any(e["type"] == "step" and e["step"]["success"] for e in events)
    assert any(e["type"] == "done" for e in events)


def test_knowledge_write_requests_only_global_sync(tmp_path):
    from http import HTTPStatus
    from laew.web import WorkspaceService
    project, _ = make_tools(tmp_path)
    vault = tmp_path / "knowledge"; vault.mkdir()
    fs = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    service = WorkspaceService(tmp_path / "manifest", project, tmp_path)
    service._permissions = PermissionBroker(project, "auto", timeout=1)
    calls = []
    service.request_sync = lambda scope: (calls.append(scope) or
                                          (HTTPStatus.ACCEPTED, {"message": "queued"}))
    def approve(event):
        if event["type"] == "approval":
            assert service._permissions.decide(event["id"], "allow", "s")
    result = service._call_tool(fs, "write_knowledge_note", {
        "file_path": "@knowledge/test.md", "expected_sha256": "",
        "content": "---\ntype: docs\nscope: global\n---\n# Test\n"}, approve, "s")
    assert result.success and result.data["synchronization"] == "requested"
    assert calls == ["global"]


def test_terminal_exact_diagnostic_requires_one_time_approval(tmp_path, monkeypatch):
    from laew.tools.base import ToolResult
    project, _ = make_tools(tmp_path)
    terminal = TerminalTool(project)
    calls = []
    monkeypatch.setattr(terminal, "call", lambda operation, **kwargs: calls.append(kwargs) or ToolResult.ok({"exit_code": 0}))
    broker = PermissionBroker(project, "auto", timeout=2)
    args = {"command": "git diff --stat --no-ext-diff --no-textconv"}
    events, result = [], []
    worker = threading.Thread(target=lambda: result.append(broker.call(terminal, "run_command", args, events.append, "browser-a")))
    worker.start()
    for _ in range(100):
        if events: break
        threading.Event().wait(.01)
    assert events and not calls and not events[0]["allow_session"]
    assert broker.decide(events[0]["id"], "allow", "browser-a")
    worker.join(3)
    assert result[0].success and calls == [args]
    assert not broker.call(terminal, "run_command", {"command": "python script.py"}, None).success


def test_broker_approval_does_not_leak_to_other_threads(tmp_path, monkeypatch):
    project, fs = make_tools(tmp_path)
    broker = PermissionBroker(project, "auto")
    started, release = threading.Event(), threading.Event()
    original = fs._write_file
    def delayed(**kwargs):
        if kwargs["file_path"] == "first.txt":
            started.set(); assert release.wait(3)
        return original(**kwargs)
    monkeypatch.setattr(fs, "_write_file", delayed)
    results = []
    worker = threading.Thread(target=lambda: results.append(broker.call(fs, "write_file", {"file_path": "first.txt", "content": "ok"}, None)))
    worker.start()
    assert started.wait(3)
    try:
        assert not fs.write_file("second.txt", "unauthorized").success
        assert not (project / "second.txt").exists()
    finally:
        release.set(); worker.join(5)
    assert results[0].success
