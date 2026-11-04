"""Routing policy tests and isolated retrieval with the real agent loop."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.knowledge.routing import KnowledgeTurn, route_sources
from laew.llm.base import LLMResponse
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.security.permissions import PermissionBroker
from laew.web import WorkspaceService


PREFERENCE = "Jakie są moje zainteresowania?"
ENVIRONMENT = "Jak wygląda konfiguracja mojego środowiska AI i z jakich narzędzi korzystam?"
TECHNICAL = "Jakie mamy ustalenia dotyczące poprawy jakości retrieval?"
PROJECT = "Wyjaśnij architekturę PermissionBroker w aktualnym projekcie."
BOTH = "Zaproponuj rozwiązanie dopasowane do mojego sprzętu i architektury aktualnego projektu."
EXPLICIT = "Sprawdź dokładnie, co mamy zapisane w Global Knowledge o indeksowaniu dokumentów."
GREETING = "Cześć, co słychać?"


@pytest.mark.parametrize("message,in_project,memory,scopes", [
    (PREFERENCE, False, True, ()),
    (ENVIRONMENT, False, False, ("global",)),
    (TECHNICAL, False, False, ("global",)),
    (PROJECT, True, False, ("project",)),
    (PROJECT, False, False, ()),
    (BOTH, True, False, ("global", "project")),
    (BOTH, False, False, ("global",)),
    (EXPLICIT, True, False, ("global",)),
    (GREETING, True, False, ()),
    ("What are my hobbies and which tools are in my setup?", True, True, ("global",)),
    ("Explain our repository architecture and check the shared @knowledge vault.", True, False, ("global", "project")),
    ("Translate: What is vector indexing?", False, False, ()),
    ("What is 2 + 2?", False, False, ()),
])
def test_source_classification(message, in_project, memory, scopes):
    route = route_sources(message, in_project=in_project)
    assert (route.memory, route.scopes) == (memory, scopes)
    assert route.reason


class Embedding:
    model = "routing-fixture"
    dimensions = 2

    def __init__(self):
        self.queries = []

    def embed(self, text):
        self.queries.append(text)
        return [0., 1.] if "missing" in text else [1., 0.]

    def embed_batch(self, texts):
        return [[1., 0.] for _ in texts]


class ObservingProvider:
    def __init__(self, reply, follow_up=None):
        self.reply = reply
        self.follow_up = follow_up
        self.messages = []

    def is_available(self):
        return True

    def generate(self, messages, **kwargs):
        self.messages.append(list(messages))
        if len(self.messages) == 1 and self.follow_up:
            return LLMResponse(content=self.follow_up, model="fixture")
        return LLMResponse(content=self.reply, model="fixture")


@pytest.fixture
def isolated_runtime(tmp_path, monkeypatch):
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path / "index"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    projects = tmp_path / "Projects"
    active, other = projects / "active", projects / "other"
    vault = tmp_path / "Knowledge"
    for folder in (active, other, vault):
        folder.mkdir(parents=True)
    (vault / "fixture.md").write_text("Shared technical evidence GLOBAL-7319.", encoding="utf-8")
    (active / "README.md").write_text("Active project evidence PROJECT-4281.", encoding="utf-8")
    (other / "README.md").write_text("Other project evidence PRIVATE-9999.", encoding="utf-8")
    manifest = {"rag": {"vector_store": {"enabled": True, "global_collection": "routing_" + uuid4().hex}}}
    embedding = Embedding()
    global_ready = False

    def build(project=None, ready=True):
        nonlocal global_ready
        tool = build_rag_tool(manifest, project_root=project, projects_root=projects, knowledge_root=vault,
                              embedding_service=embedding, general=project is None)
        if ready and not global_ready:
            synchronize_scope(tool._pipeline.knowledge_base, "global")
            global_ready = True
        if ready and project:
            synchronize_scope(tool._pipeline.knowledge_base, "project")
        return tool

    yield SimpleNamespace(build=build, embedding=embedding, active=active, other=other, vault=vault)
    client.close()


@pytest.mark.parametrize("message,in_project,expected", [
    (ENVIRONMENT, False, ["@knowledge/fixture.md"]),
    (TECHNICAL, False, ["@knowledge/fixture.md"]),
    (PROJECT, True, ["@project/README.md"]),
    (BOTH, True, ["@knowledge/fixture.md", "@project/README.md"]),
    (EXPLICIT, False, ["@knowledge/fixture.md"]),
])
def test_prefetch_reaches_provider_before_first_generation(isolated_runtime, message, in_project, expected):
    fixture = isolated_runtime
    project = fixture.active if in_project else None
    tool = fixture.build(project, ready=False)
    other = fixture.build(fixture.other, ready=False) if in_project else None
    synchronize_scope(tool._pipeline.knowledge_base, "global")
    if other is not None:
        synchronize_scope(other._pipeline.knowledge_base, "project")
        synchronize_scope(tool._pipeline.knowledge_base, "project")
    broker = PermissionBroker(project)
    provider = ObservingProvider("Fixture response with evidence " + ", ".join(expected))
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[tool]))
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    turn.prepare(executor, message, "active" if in_project else None, lambda: None, tool)
    result = executor.run(message, on_tool_call=turn.call)
    assert result.success and len(provider.messages) == 1
    context = provider.messages[0][0].content
    assert provider.messages[0][-1].content == message
    assert "PRIVATE-9999" not in context
    assert ("GLOBAL-7319" in context) == any(path.startswith("@knowledge") for path in expected)
    assert ("PROJECT-4281" in context) == any(path.startswith("@project") for path in expected)
    assert [path for call in turn.diagnostics["prefetch"] for path in call["sources"]] == expected
    assert len(fixture.embedding.queries) == len(expected)
    assert all(call["elapsed_ms"] >= 0 and call["chunks"] == 1 for call in turn.diagnostics["prefetch"])


def test_empty_stale_and_broker_denial_are_distinct(isolated_runtime):
    fixture = isolated_runtime
    tool = fixture.build(ready=False)
    broker = PermissionBroker(None)
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    executor = SimpleNamespace()
    turn.prepare(executor, EXPLICIT, None, lambda: None, tool)
    assert turn.diagnostics["prefetch"][0]["status"] == "error"
    assert "Do not claim documents were read" in executor.knowledge_context
    assert fixture.embedding.queries == []
    tool = fixture.build()
    turn.prepare(executor, "Check the Global Knowledge vault for a missing item", None, lambda: None, tool)
    assert turn.diagnostics["prefetch"][0]["status"] == "empty"
    assert "no relevant excerpts" in executor.knowledge_context
    assert len(fixture.embedding.queries) == 1
    assert not turn.call(tool, "query", {"query": "private", "scope": "project"}).success
    assert len(fixture.embedding.queries) == 1


def test_later_rag_tool_omits_same_fragment(isolated_runtime):
    tool = isolated_runtime.build()
    broker = PermissionBroker(None)
    provider = ObservingProvider("Use the earlier source.",
        '```tool_call\n{"tool": "RagTool", "operation": "query", "args": {"query": "indexing", "scope": "global"}}\n```')
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[tool]))
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    turn.prepare(executor, EXPLICIT, None, lambda: None, tool)
    result = executor.run(EXPLICIT, on_tool_call=turn.call)
    assert result.success and len(provider.messages) == 2
    assert "GLOBAL-7319" in provider.messages[1][0].content
    assert "GLOBAL-7319" not in provider.messages[1][-1].content
    assert "already supplied" in provider.messages[1][-1].content
    assert turn.diagnostics["follow_up"][0]["duplicates_omitted"] == 1


def test_web_prefetch_and_turn_reset(isolated_runtime, tmp_path, monkeypatch):
    fixture = isolated_runtime
    tool = fixture.build()
    provider = ObservingProvider("Fixture reply")
    service = WorkspaceService(tmp_path / "manifest.yaml", fixture.active, fixture.active.parent)
    service._active_project_id = None
    service._agent = Agent(AgentConfig(), provider=provider, tools=[tool])
    service._executor = AgentExecutor(service._agent)
    service._permissions = PermissionBroker(None)
    monkeypatch.setattr(service, "_ensure_runtime", lambda *args: None)
    status, response = service.chat(EXPLICIT)
    assert status == 200 and response["routing"]["prefetch"][0]["status"] == "found"
    assert "GLOBAL-7319" in provider.messages[0][0].content
    status, response = service.chat(GREETING)
    assert status == 200 and response["routing"]["prefetch"] == []
    assert "GLOBAL-7319" not in provider.messages[1][0].content
    assert len(fixture.embedding.queries) == 1


def test_preference_uses_memory_and_greeting_uses_neither():
    calls = []
    memory = SimpleNamespace(retrieval_mode="fts", recall=lambda message, project: calls.append(project) or ["Python"],
                             context=lambda rows: "Relevant Long-Term Memory: " + ", ".join(rows))
    executor = SimpleNamespace()
    turn = KnowledgeTurn(lambda *args: pytest.fail("Unnecessary RAG call"))
    assert turn.prepare(executor, PREFERENCE, None, lambda: memory, None) == ["Python"]
    assert calls == [None] and "Python" in executor.memory_context and not executor.knowledge_context
    assert not turn.prepare(executor, GREETING, None, lambda: memory, None)
    assert calls == [None] and not executor.memory_context

def test_workbench_stream_exposes_prefetch_and_source_paths(isolated_runtime, tmp_path, monkeypatch):
    fixture = isolated_runtime
    tool = fixture.build()
    provider = ObservingProvider("Fixture reply")
    service = WorkspaceService(tmp_path / "manifest.yaml", fixture.active, fixture.active.parent)
    service._active_project_id = None
    service._agent = Agent(AgentConfig(), provider=provider, tools=[tool])
    service._executor = AgentExecutor(service._agent)
    service._permissions = PermissionBroker(None)
    monkeypatch.setattr(service, "_ensure_runtime", lambda *args: None)
    monkeypatch.setattr(service, "_activate_session", lambda *args: None)
    monkeypatch.setattr(service, "knowledge", lambda: None)
    monkeypatch.setattr(service, "memory", lambda: None)
    events = []
    service.stream_chat(EXPLICIT, "manifest", None, events.append)
    routing = [event["routing"] for event in events if event["type"] == "routing"]
    assert routing[0]["scopes"] == ["global"] and routing[0]["prefetch"] == []
    assert routing[-1]["prefetch"][0]["sources"] == ["@knowledge/fixture.md"]
    assert events[-1]["type"] == "done"
    assert events[-1]["routing"] == routing[-1]
    assert "GLOBAL-7319" in provider.messages[0][0].content
    assert all("GLOBAL-7319" not in str(event) for event in events)


def test_cli_turn_prefetches_using_the_active_project(isolated_runtime, tmp_path, monkeypatch, capsys):
    from laew.cli import cmd_chat
    from laew.rag.sync import SyncScheduler

    fixture = isolated_runtime
    tool = fixture.build(fixture.active)
    provider = ObservingProvider("Fixture CLI reply")
    provider.base_url = "fixture"
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr("laew.cli.load_manifest", lambda path: {"workspace": {"root": str(fixture.active)}})
    monkeypatch.setattr("laew.cli.build_provider_for_role", lambda *a, **kw: provider)
    monkeypatch.setattr("laew.cli.build_shared_tools", lambda *a, **kw: [tool])
    monkeypatch.setattr(SyncScheduler, "start", lambda *a, **kw: None)
    messages = iter([PROJECT, "exit"])
    monkeypatch.setattr("builtins.input", lambda *args: next(messages))
    args = SimpleNamespace(manifest=manifest, model="fixture", base_url=None, timeout=None,
                           no_persist=True, resume=None, session=None, no_stream=True)
    assert cmd_chat(args) == 0
    assert "[RAG] project: found (1 fragments)" in capsys.readouterr().out
    assert "PROJECT-4281" in provider.messages[0][0].content
    assert "GLOBAL-7319" not in provider.messages[0][0].content

def test_combined_memory_and_global_context_are_separate_and_bounded(isolated_runtime):
    fixture = isolated_runtime
    tool = fixture.build(ready=False)
    (fixture.vault / "fixture.md").write_text("GLOBAL-LONG " + "engineering context " * 200, encoding="utf-8")
    kb = tool._pipeline.knowledge_base
    kb.chunk_size = 6000
    synchronize_scope(kb, "global")
    broker = PermissionBroker(None)
    memory = SimpleNamespace(retrieval_mode="fts", recall=lambda *args: ["GLOBAL-LONG"],
                             context=lambda rows: "Relevant Long-Term Memory: " + ", ".join(rows))
    executor = SimpleNamespace()
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    turn.prepare(executor, "What are my hobbies and which tools are in my setup?", None, lambda: memory, tool)
    assert executor.memory_context == "Relevant Long-Term Memory: GLOBAL-LONG"
    assert "Relevant Global Knowledge" in executor.knowledge_context
    assert "GLOBAL-LONG" in executor.knowledge_context and "fixture.md" in executor.knowledge_context
    assert executor.knowledge_context.endswith("...")
    _, context = executor.knowledge_context.split("\n", 1)
    assert len(context) <= 2000
    assert turn.diagnostics["prefetch"][0]["chunks"] == 1
    assert turn.diagnostics["memory"] == "fts"


def test_four_diagnostic_turns_remain_inspectable_after_restart(isolated_runtime, tmp_path, monkeypatch):
    import json
    from laew.console.session_store import SessionStore
    from laew.llm.cancellation import Cancellation
    from laew.runtime import build_shared_tools

    fixture = isolated_runtime
    rag = fixture.build()
    tools = build_shared_tools(manifest={}, general=True, projects_root=fixture.active.parent,
                               knowledge_root=fixture.vault, rag_embedding_service=fixture.embedding)
    filesystem = next(tool for tool in tools if tool.name == "FilesystemTool")
    private_memory = {"id": "memory-1", "scope": "user", "content": "PRIVATE-MEMORY-TEXT"}
    worker = SimpleNamespace(request=lambda: None)
    enrollment = {"baseline": lambda _: None, "enqueue": lambda *_: None}
    memory = SimpleNamespace(retrieval_mode="FTS5", recall=lambda *args: [private_memory],
                             context=lambda rows: rows[0]["content"], **enrollment)
    replies = iter([
        RuntimeError("Temporary provider failure"),
        "Incremental indexing reply",
        '```tool_call\n{"tool":"FilesystemTool","operation":"view_file","args":{"file_path":"@knowledge/missing.md"}}\n```',
        '```tool_call\n{"tool":"FilesystemTool","operation":"view_file","args":{"file_path":"@knowledge/fixture.md"}}\n```',
        "Limitations reply",
        '```tool_call\n{"tool":"RagTool","operation":"query","args":{"query":"missing evidence","scope":"global"}}\n```',
        "No benchmarks reply",
        "Interests reply",
    ])
    provider = ObservingProvider("")
    def generate(messages, **kwargs):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(content=reply, model="fixture")
    monkeypatch.setattr(provider, "generate", generate)
    store = SessionStore(tmp_path / "sessions")
    service = WorkspaceService(tmp_path / "manifest", projects_root=fixture.active.parent, workspace_root=tmp_path)
    service._conversation_store = store
    service._agent = Agent(AgentConfig(), provider=provider, tools=[rag, filesystem])
    service._agent.config.retry.backoff_base_ms = 0
    service._executor = AgentExecutor(service._agent)
    service._permissions = PermissionBroker(None)
    monkeypatch.setattr(service, "_ensure_runtime", lambda *args: None)
    monkeypatch.setattr(service, "_activate_session", lambda *args: None)
    monkeypatch.setattr(service, "memory", lambda: memory)
    monkeypatch.setattr(service, "knowledge", lambda: SimpleNamespace(**enrollment))
    monkeypatch.setattr(service, "knowledge_selection", lambda *_: {})
    monkeypatch.setattr(service, "memory_selection", lambda: {})
    service._knowledge_worker = service._memory_worker = worker
    chat = store.create_conversation("general", None)
    streamed = {}
    for prompt in ("Explain the incremental indexing strategy documented in Global Knowledge.",
                   "What are the limitations of that approach?",
                   "Do we have concrete performance benchmarks for this approach?",
                   "What are my interests?"):
        events = []
        service.stream_chat(prompt, "manifest", None, events.append, conversation_id=chat["id"])
        assert events[-1]["type"] == "done"
        assert len({e["run_id"] for e in events}) == 1
        streamed[events[-1]["run_id"]] = events[-1]["diagnostics"]
        assert all("PRIVATE-MEMORY-TEXT" not in str(event) for event in events)

    cancelled_chat = store.create_conversation("general", None)
    cancellation = Cancellation()
    def cancel_after_prefetch(event):
        routing = event.get("diagnostics", {}).get("routing") or {}
        if any(search["status"] == "found" for search in routing.get("prefetch", [])):
            cancellation.cancel()
    service.stream_chat(EXPLICIT, "manifest", None, cancel_after_prefetch,
                        cancellation=cancellation, conversation_id=cancelled_chat["id"])
    cancelled = store.load_conversation(cancelled_chat["id"])["events"][-1]
    assert cancelled["status"] == "cancelled" and cancelled["assistant_event_id"] is None
    assert cancelled["diagnostics"]["routing"]["prefetch"][0]["supplied"] == 0
    assert cancelled["diagnostics"]["requests"] == []

    monkeypatch.setattr("laew.knowledge.routing.route_sources", lambda *a, **k: pytest.fail("Historical routing replay"))
    restarted = WorkspaceService(tmp_path / "manifest", projects_root=fixture.active.parent, workspace_root=tmp_path)
    restarted._conversation_store = SessionStore(tmp_path / "sessions")
    events = restarted.read_conversation(chat["id"], None)["events"]
    completed = [e for e in events if e["kind"] == "run" and e["status"] == "completed"]
    assert len(completed) == 4
    for run in completed:
        assert run["diagnostics"] == streamed[run["run_id"]]
        assert any(e["id"] == run["assistant_event_id"] and e["run_id"] == run["run_id"] for e in events)
        diagnostic_json = json.dumps(run["diagnostics"])
        assert not any(private in diagnostic_json for private in
                       ("PRIVATE-MEMORY-TEXT", "GLOBAL-7319", "missing evidence", "Interests reply"))
    first, second, third, fourth = (run["diagnostics"] for run in completed)
    prefetch = first["routing"]["prefetch"][0]
    assert prefetch["status"] == "found" and prefetch["supplied"] == 1
    assert prefetch["fragments"][0]["path"] == "@knowledge/fixture.md"
    assert [(r["iteration"], r["attempt"], r["status"]) for r in first["requests"]] == [
        (1, 1, "failed"), (1, 2, "completed")]
    assert second["routing"]["prefetch"] == []
    assert [tool["status"] for tool in second["tools"]] == ["failed", "completed"]
    assert all(tool["tool"] == "FilesystemTool" and tool["supplied"] for tool in second["tools"])
    assert [item["tool_results"] for item in second["requests"]] == [0, 1, 2]
    follow_up = third["routing"]["follow_up"][0]
    assert follow_up["status"] == "empty" and follow_up["call_id"] == third["tools"][0]["call_id"]
    assert fourth["routing"]["memory_recall"]["ids"] == ["memory-1"]
    assert fourth["routing"]["memory_recall"]["supplied"] == 1 and fourth["tools"] == []
