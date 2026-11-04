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
EDUCATION = "Jaką edukację zakończyłem?"


@pytest.mark.parametrize("message,in_project,memory,scopes", [
    (PREFERENCE, False, True, ()),
    (ENVIRONMENT, False, True, ("global",)),
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
    (EDUCATION, False, True, ("global",)),
    ("Jaką szkołę ukończyłem?", False, True, ("global",)),
    ("Jakie mam wykształcenie?", False, True, ("global",)),
    ("Gdzie zdobyłem kwalifikacje zawodowe?", False, True, ("global",)),
    ("What education have I completed?", False, True, ("global",)),
    ("What qualifications do I have?", True, True, ("global",)),
    ("What hardware do I have?", False, True, ("global",)),
    ("What qualifications are required for this profession?", False, False, ()),
    ("Translate: What education have I completed?", False, False, ()),
    ("użyj rag", False, False, ("global",)),
    ("Przypomnij sobie, gdzie chciałbym polecieć w przyszłości.", False, True, ()),
    ("Gdzie chciałbym polecieć w przyszłości?", False, True, ()),
    ("Co zapamiętałeś o moich planach?", False, True, ()),
    ("Co masz zapisane o moich zainteresowaniach?", False, True, ()),
    ("Sprawdź moje wspomnienia.", False, True, ()),
    ("Sprawdź Long-Term Memory.", False, True, ()),
    ("A nie w RAG, tylko w Memory.", True, True, ()),
    ("A w pamięci długoterminowej?", True, True, ()),
    ("Sprawdź wyłącznie Long-Term Memory. Gdzie chciałbym pojechać?", False, True, ()),
    ("Where did I want to travel?", False, True, ()),
    ("What do you remember about my plans?", False, True, ()),
    ("Search my saved memories.", False, True, ()),
    ("Check Long-Term Memory.", False, True, ()),
    ("Explain the memory retrieval implementation.", False, False, ("global",)),
    ("Check memory usage on the GPU.", False, False, ("global",)),
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


@pytest.mark.parametrize("has_related_memory", [False, True])
def test_education_profile_reaches_first_request_without_education_memory(isolated_runtime, tmp_path,
                                                                  has_related_memory):
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore

    fixture = isolated_runtime
    (fixture.vault / "fixture.md").unlink()
    (fixture.vault / "education.md").write_text(
        "Completed education: Northbridge College, diploma in digital publishing PROFILE-417.",
        encoding="utf-8",
    )
    tool = fixture.build()
    store = MemoryStore(tmp_path / "education-memory.db")
    store.save_settings({"semantic_enabled": False})
    store.remember("My preferred drink is tea.", category="preference")
    if has_related_memory:
        store.remember("Chcę kontynuować edukację.", category="goal")
    memory = MemoryService(store)
    broker = PermissionBroker(None)
    provider = ObservingProvider("Fixture response")
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[tool]))
    turn = KnowledgeTurn(lambda t, op, args: broker.call(t, op, args, None))
    turn.prepare(executor, EDUCATION, None, lambda: memory, tool)
    assert executor.run(EDUCATION, on_tool_call=turn.call, on_diagnostic=turn.observe).success
    assert len(provider.messages) == 1
    context = provider.messages[0][0].content
    assert "Relevant Global Knowledge" in context and "PROFILE-417" in context
    assert ("Relevant Long-Term Memory" in context) == has_related_memory
    recall = turn.diagnostics["memory_recall"]
    assert recall["supplied"] == int(has_related_memory)
    assert recall["status"] == ("completed" if has_related_memory else "no_results")
    search, = turn.diagnostics["prefetch"]
    assert search["sources"] == ["@knowledge/education.md"] and search["supplied"] == 1
    assert turn.tools == []


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


@pytest.mark.parametrize("prompt", [
    "Przypomnij sobie, gdzie chciałbym polecieć w przyszłości.",
    "Sprawdź wyłącznie Long-Term Memory. Gdzie chciałbym pojechać?",
    "Nie w RAG, tylko w Memory.",
])
def test_travel_memory_routes_before_the_first_provider_request(isolated_runtime, tmp_path, prompt):
    from laew.llm.base import LLMMessage, MessageRole
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore
    from laew.memory.tool import MemoryTool

    store = MemoryStore(tmp_path / "memory.db")
    active = store.remember("The user wants to visit the city of Edinburgh in the future.", category="goal")
    # A controlled multilingual embedding and collection query, with canonical evidence from SQLite.
    queries = []
    def embed(text):
        queries.append(text)
        return [1., 0.]
    def semantic_query(**kwargs):
        assert kwargs["where"] == {"scope": "user"}
        return {"ids": [[active["id"]]], "metadatas": [[{"version": active["version"]}]], "distances": [[0.1]]}
    index = SimpleNamespace(_collection=SimpleNamespace(query=semantic_query))
    memory = MemoryService(store, index_factory=lambda: index, embedding_factory=lambda: SimpleNamespace(embed=embed))
    rag = isolated_runtime.build()
    broker = PermissionBroker(None)
    provider = ObservingProvider("Fixture reply")
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[rag, MemoryTool(memory)]))
    earlier = "Gdzie chciałbym polecieć w przyszłości?"
    correction = prompt.startswith("Nie w RAG")
    if correction:
        executor.agent.history = [LLMMessage(MessageRole.USER, earlier),
                                  LLMMessage(MessageRole.ASSISTANT, "Global Knowledge returned no travel evidence.")]
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None))
    turn.prepare(executor, prompt, None, lambda: memory, rag)
    assert executor.run(prompt, on_tool_call=turn.call, on_diagnostic=turn.observe).success
    assert queries == [earlier if correction else prompt]
    assert not turn.diagnostics["prefetch"] and not isolated_runtime.embedding.queries
    recall = turn.diagnostics["memory_recall"]
    assert recall["ids"] == [active["id"]]
    assert recall["candidates"] == recall["selected"] == recall["supplied"] == 1
    assert "Edinburgh" in provider.messages[0][0].content
    assert "GLOBAL-7319" not in provider.messages[0][0].content
    if turn.diagnostics["memory_only"]:
        assert not turn.call(rag, "query", {"scope": "global", "query": "travel"}).success


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


@pytest.mark.parametrize("mode,status,selected,omitted", [
    ("empty", "no_results", 0, 0),
    ("one", "completed", 1, 0),
    ("multiple", "completed", 2, 0),
    ("budget", "completed", 1, 1),
    ("disabled", "skipped", 0, 0),
    ("failed", "failed", 0, 0),
    ("semantic_failure_without_fallback", "failed", 0, 0),
])
def test_automatic_memory_recall_outcomes(tmp_path, monkeypatch, mode, status, selected, omitted):
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "fixture-memory.db")
    semantic_failure = mode == "semantic_failure_without_fallback"
    store.save_settings({"semantic_enabled": semantic_failure, "fallback_to_fts": not semantic_failure,
                         "recall_enabled": mode != "disabled",
                         "token_budget": 400 if mode == "budget" else 1000})
    if mode != "empty":
        store.remember("My hobbies include stargazing.", category="interest")
    if mode in {"multiple", "budget"}:
        store.remember("My hobbies include woodwork. " + "I carve small ornaments. " * (20 if mode == "budget" else 1),
                       category="interest")
    private = store.remember("My hobbies are classified by a different project.", scope="project",
                             project_id="other", category="interest")
    if mode == "failed":
        def fail(*_):
            raise RuntimeError("private error body")
        monkeypatch.setattr(store, "settings", fail)
    provider = ObservingProvider("Fixture reply")
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider))
    snapshots = []
    turn = KnowledgeTurn(lambda *_: pytest.fail("Automatic recall invoked a tool"), notify=snapshots.append)
    message = "What are my hobbies?"
    turn.prepare(executor, message, None, lambda: MemoryService(store), None)
    assert [entry["memory_recall"]["status"] for entry in snapshots[:2]] == ["selected", "started"]
    assert executor.run(message, stream=True, on_diagnostic=turn.observe).success
    recall = turn.diagnostics["memory_recall"]
    assert recall["status"] == status and recall["scopes"] == ["user"]
    assert recall.get("selected", 0) == recall.get("supplied", 0) == selected
    assert recall.get("budget_omitted", 0) == omitted
    if mode == "disabled":
        assert recall["skip_reason"] == "recall_disabled"
    if mode == "failed" or semantic_failure:
        assert recall["error_category"] == "RuntimeError"
    assert private["id"] not in str(turn.snapshot())
    assert "private error body" not in str(turn.snapshot())
    assert "stargazing" not in str(turn.snapshot())
    assert ("Relevant Long-Term Memory" in provider.messages[0][0].content) == bool(selected)
    assert not turn.tools


@pytest.mark.parametrize("adapter", ["llamacpp", "ollama"])
def test_local_stream_payload_contains_automatic_memory(tmp_path, monkeypatch, adapter):
    import json
    from laew.llm.llamacpp import LlamaCppProvider
    from laew.llm.ollama import OllamaProvider
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore
    from laew.memory.tool import MemoryTool

    store = MemoryStore(tmp_path / "fixture-memory.db")
    store.save_settings({"semantic_enabled": False})
    store.remember("My hobbies include stargazing.", category="interest")
    targeted = store.remember("Edinburgh is the next destination.", category="goal")
    tool_call = ' ```tool_call\n{"tool":"MemoryTool","operation":"recall","args":{"query":"Edinburgh"}}\n```'
    if adapter == "llamacpp":
        provider = LlamaCppProvider("fixture", "http://127.0.0.1:18999")
        def frames(text):
            return [b"data: " + json.dumps({"choices": [{"delta": {"content": text}}]}).encode(),
                    b"data: [DONE]"]
    else:
        provider = OllamaProvider("http://127.0.0.1:18999")
        def frames(text):
            return [json.dumps({"message": {"content": text}, "done": True})]
    monkeypatch.setattr(provider, "is_available", lambda: True)
    sent = []

    def response(_, json, **kwargs):
        sent.append(json)
        chunks = frames(tool_call if len(sent) == 1 else "Fixture reply")
        return SimpleNamespace(raise_for_status=lambda: None, close=lambda: None, iter_lines=lambda **_: iter(chunks))

    if adapter == "llamacpp":
        monkeypatch.setattr(provider, "_request", response)
    else:
        monkeypatch.setattr("laew.llm.ollama.requests.post", response)
    memory = MemoryService(store)
    executor = AgentExecutor(Agent(AgentConfig(model="fixture"), provider=provider, tools=[MemoryTool(memory)]))
    broker = PermissionBroker(None)
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None))
    message = "What are my hobbies?"
    turn.prepare(executor, message, None, lambda: memory, None)
    assert executor.run(message, stream=True, on_diagnostic=turn.observe, on_tool_call=turn.call).success
    assert len(sent) == 2
    system = sent[0]["messages"][0]
    assert system["role"] == "system"
    assert all(text in system["content"] for text in
               ("Relevant Long-Term Memory", "stargazing", "incomplete or outdated", "current statements take precedence"))
    assert turn.diagnostics["memory_recall"]["supplied"] == 1
    assert "recall(query)" in system["content"]
    assert targeted["id"] in sent[1]["messages"][-1]["content"]
    assert turn.tools[0]["memory_recall"]["supplied"] == 1

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
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore
    from laew.runtime import build_shared_tools

    fixture = isolated_runtime
    rag = fixture.build()
    tools = build_shared_tools(manifest={}, general=True, projects_root=fixture.active.parent,
                               knowledge_root=fixture.vault, rag_embedding_service=fixture.embedding)
    filesystem = next(tool for tool in tools if tool.name == "FilesystemTool")
    worker = SimpleNamespace(request=lambda: None)
    enrollment = {"baseline": lambda _: None, "enqueue": lambda *_: None}
    memories = MemoryStore(tmp_path / "memory.db")
    memories.save_settings({"semantic_enabled": False})
    initial_memory = memories.remember("My interests include PRIVATE-MEMORY-TEXT.")
    targeted_memory = memories.remember("Portobello SECOND-MEMORY-TEXT")
    memory = MemoryService(memories)
    for name, method in enrollment.items():
        monkeypatch.setattr(memory, name, method)
    replies = iter([
        RuntimeError("Temporary provider failure"),
        "Incremental indexing reply",
        '```tool_call\n{"tool":"FilesystemTool","operation":"view_file","args":{"file_path":"@knowledge/missing.md"}}\n```',
        '```tool_call\n{"tool":"FilesystemTool","operation":"view_file","args":{"file_path":"@knowledge/fixture.md"}}\n```',
        "Limitations reply",
        '```tool_call\n{"tool":"RagTool","operation":"query","args":{"query":"missing evidence","scope":"global"}}\n```',
        "No benchmarks reply",
        '```tool_call\n{"tool":"MemoryTool","operation":"recall","args":{"query":"Portobello"}}\n```',
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
        assert any(e.get("phase") == "provider_dispatch" and e["diagnostics"]["requests"][-1]["dispatched"]
                   for e in events[:-1])
        for started in (e for e in events if e.get("phase") == "tool_started"):
            tool = started["diagnostics"]["tools"][-1]
            assert tool["status"] == "started"
            assert sum(item["order"] == tool["order"] for item in events[-1]["diagnostics"]["tools"]) == 1
        streamed[events[-1]["run_id"]] = events[-1]["diagnostics"]
        assert all("PRIVATE-MEMORY-TEXT" not in str(event) and "SECOND-MEMORY-TEXT" not in str(event)
                   for event in events)

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
    assert fourth["routing"]["memory_recall"]["ids"] == [initial_memory["id"]]
    assert fourth["routing"]["memory_recall"]["supplied"] == 1
    recall_tool, = fourth["tools"]
    assert recall_tool["operation"] == "recall"
    assert recall_tool["memory_recall"]["ids"] == [targeted_memory["id"]]
    assert recall_tool["memory_recall"]["supplied"] == 1
    assert "SECOND-MEMORY-TEXT" not in str(events)


def test_live_workbench_browser(isolated_runtime, tmp_path, monkeypatch):
    """Run with LAEW_BROWSER_EXECUTABLE pointing to Chromium or Edge and Node 22+."""
    import os
    import subprocess
    from http.server import ThreadingHTTPServer
    from pathlib import Path
    from threading import Event, Thread

    from laew.console.session_store import SessionStore
    from laew.agent.executor import StreamCancelled
    from laew.memory.service import MemoryService
    from laew.memory.store import MemoryStore
    from laew.runtime import build_shared_tools
    from laew import web
    from laew.cli import cmd_ui

    browser = os.environ.get("LAEW_BROWSER_EXECUTABLE")
    if not browser:
        pytest.skip("Set LAEW_BROWSER_EXECUTABLE to run the actual browser test.")
    fixture = isolated_runtime
    rag = fixture.build()
    tools = build_shared_tools(manifest={}, general=True, projects_root=fixture.active.parent,
                               knowledge_root=fixture.vault, rag_embedding_service=fixture.embedding)
    filesystem = next(tool for tool in tools if tool.name == "FilesystemTool")
    store = MemoryStore(tmp_path / "fixture-memory.db")
    store.save_settings({"semantic_enabled": False})
    store.remember("My hobbies include stargazing.", category="interest")
    memory = MemoryService(store)
    enrollment = SimpleNamespace(baseline=lambda _: None, enqueue=lambda *_: None)
    monkeypatch.setattr(memory, "baseline", enrollment.baseline)
    monkeypatch.setattr(memory, "enqueue", enrollment.enqueue)
    gates = {name: Event() for name in ("tool", "reply", "recall")}
    original_recall = memory.recall

    def delayed_recall(message, *args, **kwargs):
        if message == "What are my hobbies?":
            assert gates["recall"].wait(20)
        return original_recall(message, *args, **kwargs)

    monkeypatch.setattr(memory, "recall", delayed_recall)

    class Provider(ObservingProvider):
        def generate_stream(self, messages, *, model, temperature, max_tokens, cancellation):
            self.messages.append(list(messages))
            index = len(self.messages)
            if index == 1:
                raise RuntimeError("Temporary fixture failure")
            if index <= 3:
                filename = "missing.md" if index == 2 else "fixture.md"
                yield ('```tool_call\n{"tool":"FilesystemTool","operation":"view_file",'
                       f'"args":{{"file_path":"@knowledge/{filename}"}}}}\n```')
            elif index == 4:
                assert gates["reply"].wait(20)
                yield "Fixture final response"
            elif index == 5:
                yield ('```tool_call\n{"tool":"RagTool","operation":"query",'
                       '"args":{"query":"shared technical evidence","scope":"global"}}\n```')
            elif index == 6:
                yield ('```tool_call\n{"tool":"MemoryTool","operation":"recall",'
                       '"args":{"query":"stargazing"}}\n```')
            else:
                import time
                deadline = time.monotonic() + 20
                while not cancellation.is_set() and time.monotonic() < deadline:
                    time.sleep(.01)
                raise StreamCancelled()

    service = WorkspaceService(tmp_path / "manifest", projects_root=fixture.active.parent, workspace_root=tmp_path)
    service._active_project_id = None
    service._conversation_store = SessionStore(tmp_path / "sessions")
    sessions = service._conversation_store
    legacy = sessions.create_conversation("general", None, title="Legacy fixture")
    sessions.append_conversation_event(legacy["id"], {"id": "legacy-run", "run_id": "legacy",
                                                       "kind": "run", "status": "completed", "content": ""})
    sessions.create_conversation("project", service._id_for_path(fixture.active), title="Project fixture")
    provider = Provider("")
    service._provider_name, service._model = "fixture", "test model"
    service._agent = Agent(AgentConfig(model="test model"), provider=provider, tools=[rag, filesystem])
    service._agent.config.retry.backoff_base_ms = 0
    service._executor = AgentExecutor(service._agent)
    service._permissions = PermissionBroker(None)
    monkeypatch.setattr(service, "_ensure_runtime", lambda *args: None)
    monkeypatch.setattr(service, "_activate_session", lambda *args: None)
    monkeypatch.setattr(service, "memory", lambda: memory)
    monkeypatch.setattr(service, "knowledge", lambda: enrollment)
    monkeypatch.setattr(service, "memory_selection", lambda: {})
    monkeypatch.setattr(service, "knowledge_selection", lambda _: {})
    monkeypatch.setattr(service, "knowledge_request", lambda *_: (200, {}))
    monkeypatch.setattr(service, "cloud_request", lambda *_: (200, {"accounts": [], "models": []}))
    sync_requests = []
    service._scheduler = SimpleNamespace(request=lambda scope, path: sync_requests.append((scope, path)))
    monkeypatch.setattr(service, "sync_status", lambda: {"global": {"state": "requested" if sync_requests else "ready"}})
    service._knowledge_worker = service._memory_worker = SimpleNamespace(request=lambda: None)
    call = service._call_tool

    def delayed_tool(tool, operation, args, *options):
        if tool is filesystem and args.get("file_path", "").endswith("missing.md"):
            assert gates["tool"].wait(20)
        return call(tool, operation, args, *options)

    monkeypatch.setattr(service, "_call_tool", delayed_tool)

    snapshots = {}
    stream_chat = service.stream_chat

    def capture_stream(message, selection, project_id, emit, *args, **kwargs):
        def capture(event):
            if event.get("run_status") in {"completed", "cancelled"}:
                snapshots[event["run_id"]] = event["diagnostics"]
            emit(event)
        return stream_chat(message, selection, project_id, capture, *args, **kwargs)

    monkeypatch.setattr(service, "stream_chat", capture_stream)
    started = Event()
    servers = []

    def server_factory(address, handler):
        class Handler(handler):
            def do_GET(self):
                if self.path.startswith("/release/") and self._local_host():
                    gates[self.path.rsplit("/", 1)[-1]].set()
                    self.send_response(204)
                    self.end_headers()
                else:
                    super().do_GET()

        server = ThreadingHTTPServer(address, Handler)
        server.daemon_threads = True
        servers.append(server)
        started.set()
        return server

    monkeypatch.setattr(web, "WorkspaceService", lambda *_: service)
    monkeypatch.setattr(web, "ThreadingHTTPServer", server_factory)
    monkeypatch.setattr(service, "start_sync", lambda: None)
    monkeypatch.setattr(service, "close", lambda: None)
    args = SimpleNamespace(manifest=str(tmp_path / "manifest"), port=0, no_browser=True,
                           projects_root=str(fixture.active.parent), workspace_root=str(tmp_path))
    worker = Thread(target=cmd_ui, args=(args,), daemon=True)
    worker.start()
    assert started.wait(5)
    server = servers[0]
    script = Path(__file__).resolve().parents[1] / "ui" / "live-diagnostics.browser.js"
    try:
        subprocess.run(["node", str(script), browser, str(tmp_path / "browser"),
                        f"http://127.0.0.1:{server.server_port}"], check=True, timeout=65)
        assert "Relevant Long-Term Memory" in provider.messages[0][0].content
        assert "stargazing" in provider.messages[0][0].content
        assert sync_requests == [("global", None), ("project", str(fixture.active))]
        chat, = [item for item in sessions.list_conversations() if item["title"].startswith("What are my hobbies")]
        persisted = {event["run_id"]: event["diagnostics"]
                     for event in sessions.load_conversation(chat["id"])["events"]
                     if event["kind"] == "run" and event["status"] in {"completed", "cancelled"}}
        assert len(persisted) == 2 and snapshots == persisted
    finally:
        for gate in gates.values():
            gate.set()
        server.shutdown()
        worker.join(3)
