"""The conversation extension shares the legacy session directory."""

from concurrent.futures import ThreadPoolExecutor
import pytest

from laew.console.session_store import SessionStore, SessionStoreError


def test_conversations_are_isolated_and_survive_restart(tmp_path):
    store = SessionStore(tmp_path)
    general = store.create_conversation("general", None)
    project = store.create_conversation("project", "a123")
    store.append_conversation_event(general["id"], {"id": "event1", "kind": "user", "status": "completed", "content": "hello"})
    store.rename_conversation(general["id"], "First chat")
    reopened = SessionStore(tmp_path)
    assert reopened.load_conversation(general["id"])["title"] == "First chat"
    assert reopened.load_conversation(general["id"])["events"][0]["content"] == "hello"
    assert reopened.load_conversation(project["id"])["events"] == []
    assert {item["id"] for item in reopened.list_conversations()} == {general["id"], project["id"]}
    assert reopened.delete_conversation(general["id"])
    assert reopened.load_conversation(project["id"])["project_id"] == "a123"


def test_conversation_event_append_is_idempotent_and_concurrent(tmp_path):
    store = SessionStore(tmp_path)
    chat = store.create_conversation("general", None)
    event = {"id": "once", "kind": "tool_result", "status": "denied", "content": "denied", "call_id": "call1"}
    store.append_conversation_event(chat["id"], event)
    store.append_conversation_event(chat["id"], event)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: store.append_conversation_event(chat["id"], {
            "id": f"event{i}", "kind": "user", "status": "completed", "content": str(i)}), range(20)))
    events = store.load_conversation(chat["id"])["events"]
    assert len(events) == 21
    assert [event["sequence"] for event in events] == list(range(21))
    with pytest.raises(SessionStoreError):
        store.append_conversation_event(chat["id"], {**event, "content": "changed"})


def test_conversation_scope_and_path_validation(tmp_path):
    store = SessionStore(tmp_path)
    for scope, project in (("general", "x"), ("project", None), ("other", None)):
        with pytest.raises(SessionStoreError):
            store.create_conversation(scope, project)
    with pytest.raises(SessionStoreError):
        store.load_conversation("../outside")


def test_conversation_events_redact_credentials_and_preserve_legacy_sessions(tmp_path):
    from laew.console.session_store import make_chat_payload
    store = SessionStore(tmp_path)
    store.save("legacy", make_chat_payload("manifest.yaml", [{"role": "user", "content": "old"}]))
    chat = store.create_conversation("general", None)
    store.append_conversation_event(chat["id"], {
        "id": "event1", "kind": "tool_result", "status": "completed",
        "content": "Authorization: Bearer supersecret", "data": {"api_key": "private"},
    })
    raw = store._conversation_path(chat["id"]).read_text(encoding="utf-8")
    assert "supersecret" not in raw and "private" not in raw
    assert store.load("legacy")["conversation"][0]["content"] == "old"


def test_workbench_run_restarts_and_keeps_other_conversations_separate(tmp_path):
    from unittest.mock import patch
    from laew.llm.base import LLMResponse
    from laew.web import WorkspaceService

    class Provider:
        def __init__(self): self.contexts = []
        def is_available(self): return True
        def generate(self, messages, **kwargs):
            self.contexts.append([message.content for message in messages])
            return LLMResponse(content="answer", model="test")

    projects = tmp_path / "Projects"
    projects.mkdir()
    (tmp_path / "Knowledge").mkdir()
    store = SessionStore(tmp_path / "sessions")
    first = store.create_conversation("general", None)
    other = store.create_conversation("general", None)
    provider = Provider()
    with (patch("laew.web.load_manifest", return_value={}),
          patch("laew.web.build_provider_for_role", return_value=provider),
          patch("laew.web.resolve_model_name", return_value="test"),
          patch("laew.web.build_shared_tools", return_value=[])):
        service = WorkspaceService(tmp_path / "manifest", projects_root=projects, workspace_root=tmp_path)
        service._conversation_store = store
        events = []
        def observe(event):
            if event["type"] == "done":
                assert store.load_conversation(first["id"])["events"][-1]["status"] == "completed"
            events.append(event)
        service.stream_chat("first", "manifest", None, observe, "session", conversation_id=first["id"])
        assert events[-1]["type"] == "done"
        restarted = WorkspaceService(tmp_path / "manifest", projects_root=projects, workspace_root=tmp_path)
        restarted._conversation_store = SessionStore(tmp_path / "sessions")
        restarted.stream_chat("second", "manifest", None, lambda _: None, "session", conversation_id=first["id"])
        assert "first" in provider.contexts[-1] and "answer" in provider.contexts[-1]
        restarted.stream_chat("separate", "manifest", None, lambda _: None, "session", conversation_id=other["id"])
        assert "first" not in provider.contexts[-1]
        scoped = store.create_conversation("project", "other-project")
        errors = []
        restarted.stream_chat("blocked", "manifest", None, errors.append, "session", conversation_id=scoped["id"])
        assert errors[-1]["type"] == "error" and "scope" in errors[-1]["error"]
        first_project = projects / "A"
        second_project = projects / "B"
        first_project.mkdir()
        second_project.mkdir()
        first_id, second_id = restarted._id_for_path(first_project), restarted._id_for_path(second_project)
        project_chat = store.create_conversation("project", first_id)
        assert restarted.select_project(second_id)[0] == 200
        errors = []
        restarted.stream_chat("blocked in B", "manifest", second_id, errors.append, "session", conversation_id=project_chat["id"])
        assert errors[-1]["type"] == "error" and not store.load_conversation(project_chat["id"])["events"]
        assert restarted.select_project(None)[0] == 200
        from laew.llm.cancellation import Cancellation
        cancellation = Cancellation()
        cancellation.cancel()
        restarted.stream_chat("cancelled", "manifest", None, lambda _: None, "session",
                              cancellation, conversation_id=other["id"])
        assert store.load_conversation(other["id"])["events"][-1]["status"] == "cancelled"
        unavailable = WorkspaceService(tmp_path / "manifest", projects_root=projects, workspace_root=tmp_path)
        unavailable._conversation_store = store
        provider.is_available = lambda: False
        errors = []
        unavailable.stream_chat("save even when offline", "manifest", None, errors.append, "another",
                                conversation_id=other["id"])
        assert errors[-1]["type"] == "error"
        saved = store.load_conversation(other["id"])["events"]
        assert saved[-2]["content"] == "save even when offline" and saved[-1]["status"] == "failed"


def test_busy_conversation_cannot_be_renamed_or_deleted(tmp_path):
    store = SessionStore(tmp_path)
    chat = store.create_conversation("general", None)
    with store.conversation_run(chat["id"]):
        with pytest.raises(SessionStoreError, match="busy"):
            store.rename_conversation(chat["id"], "Other")
        with pytest.raises(SessionStoreError, match="busy"):
            store.delete_conversation(chat["id"])


def test_interrupted_tool_call_is_not_replayed_and_is_reported_as_unknown(tmp_path):
    from laew.llm.base import LLMMessage, MessageRole, ToolCall
    store = SessionStore(tmp_path)
    chat = store.create_conversation("general", None)
    run_id = "interrupted"
    def append(kind, status, event_id, message=None, **extra):
        store.append_conversation_event(chat["id"], {"id": event_id, "kind": kind, "status": status,
            "run_id": run_id, "content": message.content if message else "",
            **({"message": message.to_dict()} if message else {}), **extra})
    append("run", "running", "start")
    append("user", "completed", "user", LLMMessage(MessageRole.USER, "Do the work"))
    append("assistant", "completed", "assistant", LLMMessage(MessageRole.ASSISTANT, "", [ToolCall("call1", "Test__run", "{}")]))
    append("tool_call", "running", "call", call_id="call1")
    with store.conversation_run(chat["id"]):
        store.recover_interrupted_runs(chat["id"])
        history = store.conversation_messages(chat["id"])
    assert history[-1].role == MessageRole.TOOL
    assert history[-1].tool_call_id == "call1" and "outcome is unknown" in history[-1].content
    assert store.load_conversation(chat["id"])["events"][-1]["status"] == "failed"


def test_cli_general_conversation_can_be_resumed_with_shared_store(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import patch
    from laew.cli import cmd_chat
    from laew.llm.base import LLMResponse

    class Provider:
        base_url = "fixture"
        def __init__(self): self.contexts = []
        def is_available(self): return True
        def generate(self, messages, **kwargs):
            self.contexts.append([item.content for item in messages])
            return LLMResponse(content="cli answer", model="test")

    store = SessionStore(tmp_path / "sessions")
    provider = Provider()
    args = SimpleNamespace(general=True, workspace_root=str(tmp_path), model=None, base_url=None,
        timeout=None, provider=None, manifest="manifest.yaml", resume=None, session=None,
        no_persist=False, no_stream=True, conversation=None, new_conversation=True, list_conversations=False)
    with (patch("laew.cli.load_manifest", return_value={}),
          patch("laew.cli.build_provider_for_role", return_value=provider),
          patch("laew.cli.resolve_model_name", return_value="test"),
          patch("laew.cli.build_shared_tools", return_value=[]),
          patch("laew.console.session_store.conversation_store_from_manifest", return_value=store),
          patch("builtins.input", side_effect=["cli first", "exit", "cli second", "exit"])):
        assert cmd_chat(args) == 0
        args.general = False
        args.new_conversation = False
        args.conversation = store.list_conversations()[0]["id"]
        assert cmd_chat(args) == 0
    assert "cli first" in provider.contexts[-1] and "cli answer" in provider.contexts[-1]


def test_atomic_write_failure_and_cross_process_run_lease(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys
    from unittest.mock import patch

    store = SessionStore(tmp_path / "sessions")
    chat = store.create_conversation("general", None)
    with patch("laew.console.session_store.os.replace", side_effect=OSError("simulated failure")):
        with pytest.raises(OSError, match="simulated"):
            store.rename_conversation(chat["id"], "changed")
    assert store.load_conversation(chat["id"])["title"] == "New conversation"
    other_temp = tmp_path / "other-temp"
    other_temp.mkdir()
    env = dict(os.environ, TEMP=str(other_temp), TMP=str(other_temp))
    code = ("import sys; from laew.console.session_store import SessionStore,SessionStoreError; "
            "s=SessionStore(sys.argv[1]);\n"
            "try: s.rename_conversation(sys.argv[2], 'other')\n"
            "except SessionStoreError: print('busy')\n")
    with store.conversation_run(chat["id"]):
        result = subprocess.run([sys.executable, "-c", code, str(store.directory), chat["id"]],
                                capture_output=True, text=True, env=env, timeout=20, check=True)
    assert result.stdout.strip() == "busy"
    path = store._conversation_path(chat["id"])
    broken = '{"schema": "bad", "events": ['
    path.write_text(broken, encoding="utf-8")
    with pytest.raises(SessionStoreError):
        store.rename_conversation(chat["id"], "must not overwrite")
    assert path.read_text(encoding="utf-8") == broken
