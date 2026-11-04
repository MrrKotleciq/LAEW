"""Deterministic cloud protocol -> Chief -> broker -> real isolated tool tests."""

import copy
import json

import pytest

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.cloud_chat import CloudError
from laew.llm.cloud import OpenAIProvider
from laew.llm.gemini import GeminiProvider
from laew.llm.base import LLMMessage, LLMResponse, MessageRole, ToolCall
from laew.llm.cancellation import Cancellation
from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool
from laew.runtime import build_rag_tool
from laew.rag.sync import synchronize_scope


class Response:
    def __init__(self, frames=(), status=200, headers=None):
        self.frames, self.status_code, self.headers = frames, status, headers or {}
        self.closed = False

    def iter_content(self, *args, **kwargs):
        # Exercise split UTF-8, SSE delimiters and arguments independently of packets.
        for frame in self.frames:
            raw = frame if isinstance(frame, str) else json.dumps(frame, ensure_ascii=False)
            data = ("data: " + raw + "\r\n\r\n").encode()
            for i in range(0, len(data), 3):
                yield data[i:i + 3]

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, copy.deepcopy(kwargs)))
        return next(self.responses)


def frames(provider, calls=(), text=""):
    if provider != "gemini":
        return ([{"type": "response.output_text.delta", "delta": text}] if text else []) + [
            {"type": "response.completed", "response": {"status": "completed", "output": [
                {"type": "function_call", "call_id": id, "name": name, "arguments": args,
                 **({"namespace": "laew"} if provider == "chatgpt" else {})} for id, name, args in calls],
                "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}}]
    result = []
    for index, (id, name, args) in enumerate(calls):
        result.append({"choices": [{"index": 0, "delta": {"tool_calls": [{"index": index, "id": id,
            "function": {"name": name, "arguments": args[:3]},
            "extra_content": {"google": {"thought_signature": "opaque-test-signature"}}}]}}]})
        result.append({"choices": [{"index": 0, "delta": {"tool_calls": [{"index": index,
            "function": {"arguments": args[3:]}}]}}]})
    result += [{"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": "tool_calls" if calls else "stop"}]}, "[DONE]"]
    return result


def adapter(monkeypatch, provider, responses):
    session = Session(responses)
    monkeypatch.setattr("laew.cloud_chat.cancellable_session", lambda _: session)
    monkeypatch.setattr("laew.llm.gemini.cancellable_session", lambda _: session)
    model = "gemini-3.8-flash" if provider == "gemini" else "exact-model"
    instance = (GeminiProvider(credential=lambda: "fixture") if provider == "gemini" else
                OpenAIProvider(provider, credential=lambda: "fixture"))
    return instance, session, model


@pytest.mark.parametrize('provider',['openai-api','chatgpt','gemini'])
def test_memory_category_schema_error_correction_and_review(tmp_path,monkeypatch,provider):
    from laew.memory.store import MemoryStore
    from laew.memory.service import MemoryService
    from laew.memory.tool import MemoryTool
    from laew.memory.categories import CATEGORIES
    memory=MemoryService(MemoryStore(tmp_path/'memory.db'))
    content='Użytkownik chce w przyszłości odwiedzić Edynburg.'
    responses=[Response(frames(provider,[(str(i),'MemoryTool__propose',json.dumps(
        dict(content=content,scope='user',category=category)))]))
        for i,category in enumerate(['preferencje i plany podróżnicze','goals'])]
    responses.append(Response(frames(provider,text='Proposal ready for review.')))
    instance,session,model=adapter(monkeypatch,provider,responses)
    broker=PermissionBroker(None)
    tool=MemoryTool(memory)
    result=AgentExecutor(Agent(AgentConfig(model=model),provider=instance,tools=[tool])).run(
        'Zapamiętaj, że chcę w przyszłości odwiedzić Edynburg',
        on_tool_call=lambda t,op,args:broker.call(t,op,args,None))
    assert result.success
    error=result.steps[0].tool_result
    assert not error.success and set(error.data['accepted_categories'])==CATEGORIES
    assert result.steps[1].tool_result.success
    assert len(memory.proposals())==1 and memory.proposals()[0]['category']=='goal'
    assert not memory.store.list_memories()
    first=session.calls[0][2]['json']['tools'][0]
    if provider=='chatgpt': first=first['tools'][0]
    elif provider=='gemini': first=first['function']
    assert set(first['parameters']['properties']['category']['enum'])==CATEGORIES
    correction=json.dumps(session.calls[1][2]['json'])
    assert 'accepted_categories' in correction and 'Correct category and retry' in correction


def filesystem(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "knowledge"; vault.mkdir()
    (project / "README.md").write_text("PROJECT-FIXTURE Zażółć 🧬", encoding="utf-8")
    fs = FilesystemTool(PathResolver(project_root=project, projects_root=tmp_path, knowledge_root=vault))
    return project, vault, fs


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
def test_native_multiple_calls_continuation_and_shared_rag(tmp_path, monkeypatch, provider):
    project, vault, fs = filesystem(tmp_path)
    class Embedding:
        model, dimensions = "synthetic", 3
        def embed(self, text): return [1., 0., 0.]
        def embed_batch(self, texts): return [self.embed(text) for text in texts]
    rag = build_rag_tool({"rag": {"vector_store": {"enabled": False}}}, project_root=project,
                         knowledge_root=vault, embedding_service=Embedding())
    synchronize_scope(rag._pipeline.knowledge_base, "project")
    calls = [("read", "FilesystemTool__view_file", '{"file_path":"README.md"}'),
             ("retrieve", "RagTool__query", '{"query":"PROJECT-FIXTURE","scope":"project"}')]
    instance, session, model = adapter(monkeypatch, provider, [Response(frames(provider, calls)),
        Response(frames(provider, text="Zażółć 🧬 [source](@project/README.md)"))])
    agent = Agent(AgentConfig(model=model), provider=instance, tools=[fs, rag])
    broker = PermissionBroker(project)
    deltas = []
    result = AgentExecutor(agent).run("Read and retrieve", stream=True, on_delta=deltas.append,
        on_tool_call=lambda t, op, args: broker.call(t, op, args, None, "session"))
    assert result.success and all(s.tool_result.success for s in result.steps if s.tool_result)
    assert "".join(deltas) == result.final_response
    second = session.calls[1][2]["json"]
    assert "PROJECT-FIXTURE" in json.dumps(second) and "@project/README.md" in json.dumps(second)
    assert [m.tool_call_id for m in agent.history if m.role == MessageRole.TOOL] == ["read", "retrieve"]
    first = session.calls[0][2]["json"]
    if provider == "chatgpt":
        assert first["tools"][0]["type"] == "namespace"
        assert first["store"] is False and first["stream"] is True
        assert not {"temperature", "max_output_tokens", "previous_response_id"}.intersection(first)
    elif provider == "openai-api":
        assert first["tools"][0]["type"] == "function" and "max_output_tokens" in first
    else:
        assert "/chat/completions" in session.calls[0][1]
        assert "opaque-test-signature" in json.dumps(second)


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
def test_persisted_tool_history_resumes_without_reexecution(tmp_path, monkeypatch, provider):
    from laew.console.session_store import SessionStore
    project, _, fs = filesystem(tmp_path)
    calls = [("read", "FilesystemTool__view_file", '{"file_path":"README.md"}'),
             ("read-again", "FilesystemTool__view_file", '{"file_path":"README.md"}')]
    instance, session, model = adapter(monkeypatch, provider, [Response(frames(provider, calls)),
        Response(frames(provider, text="First answer")), Response(frames(provider, text="Resumed answer"))])
    store = SessionStore(tmp_path / "sessions")
    chat = store.create_conversation("project", "fixture-project")
    broker = PermissionBroker(project)
    def persist(event):
        store.append_conversation_event(chat["id"], {**event, "run_id": "first"})
    agent = Agent(AgentConfig(model=model), provider=instance, tools=[fs])
    result = AgentExecutor(agent).run("Read the file", on_event=persist,
        on_tool_call=lambda tool, op, args: broker.call(tool, op, args, None))
    assert result.success
    store = SessionStore(tmp_path / "sessions")
    resumed = Agent(AgentConfig(model=model), provider=instance, tools=[fs])
    resumed.history = store.conversation_messages(chat["id"])
    assert AgentExecutor(resumed).run("Continue", on_tool_call=lambda *args: pytest.fail("Historical call replayed")).success
    serialized = json.dumps(session.calls[-1][2]["json"])
    assert "read-again" in serialized and "PROJECT-FIXTURE" in serialized
    if provider == "gemini":
        assert "opaque-test-signature" in serialized
    target = "openai-api" if provider == "gemini" else "gemini"
    switched_provider, switched_session, switched_model = adapter(monkeypatch, target, [Response(frames(target, text="Switched answer"))])
    switched = Agent(AgentConfig(model=switched_model), provider=switched_provider, tools=[fs])
    switched.history = store.conversation_messages(chat["id"])
    assert AgentExecutor(switched).run("Continue with another provider", on_tool_call=lambda *args: pytest.fail("Historical call replayed")).success
    switched_payload = json.dumps(switched_session.calls[-1][2]["json"])
    assert "read-again" in switched_payload and "PROJECT-FIXTURE" in switched_payload
    assert "opaque-test-signature" not in switched_payload
    class LocalProvider:
        def is_available(self): return True
        def generate(self, messages, **kwargs):
            self.messages = messages
            return LLMResponse(content="Local answer", model="local")
    local_provider = LocalProvider()
    local = Agent(AgentConfig(model="local"), provider=local_provider, tools=[fs])
    local.history = store.conversation_messages(chat["id"])
    assert AgentExecutor(local).run("Continue locally", on_tool_call=lambda *args: pytest.fail("Historical call replayed")).success
    assert "read-again" in " ".join(message.content for message in local_provider.messages)


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
@pytest.mark.parametrize("arguments", ['{broken', '{}', '[]', '{"file_path":12}', '{"file_path":"README.md","unknown":true}'])
def test_invalid_arguments_never_reach_broker(tmp_path, monkeypatch, provider, arguments):
    _, _, fs = filesystem(tmp_path)
    instance, session, model = adapter(monkeypatch, provider, [
        Response(frames(provider, [("bad", "FilesystemTool__view_file", arguments)])),
        Response(frames(provider, text="Cannot execute invalid arguments."))])
    agent = Agent(AgentConfig(model=model), provider=instance, tools=[fs])
    result = AgentExecutor(agent).run("read", on_tool_call=lambda *a: pytest.fail("Invalid call reached broker"))
    assert result.success and result.steps[0].tool_result.error_code == "ERR_INVALID_INPUT"
    assert "ERR_INVALID_INPUT" in json.dumps(session.calls[1][2]["json"])


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
@pytest.mark.parametrize("decision", ["allow", "deny", "timeout"])
def test_real_approval_result_and_duplicate_mutation(tmp_path, monkeypatch, provider, decision):
    project, _, fs = filesystem(tmp_path)
    call = ("write", "FilesystemTool__write_file", '{"file_path":"result.md","content":"approved"}')
    instance, session, model = adapter(monkeypatch, provider, [Response(frames(provider, [call])),
        Response(frames(provider, [call])), Response(frames(provider, text="Finished."))])
    broker = PermissionBroker(project, "manual", timeout=.01)
    approvals = []
    def emit(event):
        if event["type"] == "approval":
            approvals.append(event)
            assert not (project / "result.md").exists()
            if decision != "timeout": broker.decide(event["id"], decision, "session")
    agent = Agent(AgentConfig(model=model), provider=instance, tools=[fs])
    events = []
    result = AgentExecutor(agent).run("write", on_event=events.append,
        on_tool_call=lambda t, op, args: broker.call(t, op, args, emit, "session"))
    assert result.success and len(approvals) == 1
    assert (project / "result.md").exists() == (decision == "allow")
    assert result.steps[0].tool_result.success == (decision == "allow")
    tool_result = next(event for event in events if event["kind"] == "tool_result")
    assert tool_result["status"] == {"allow": "completed", "deny": "denied", "timeout": "failed"}[decision]


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
def test_incomplete_stream_never_executes_call(tmp_path, monkeypatch, provider):
    _, _, fs = filesystem(tmp_path)
    call = ("write", "FilesystemTool__delete_file", '{"file_path":"README.md"}')
    incomplete = frames(provider, [call])[:-1]
    instance, session, model = adapter(monkeypatch, provider, [Response(incomplete)])
    result = AgentExecutor(Agent(AgentConfig(model=model), provider=instance, tools=[fs])).run(
        "delete", on_tool_call=lambda *a: pytest.fail("Incomplete call executed"))
    assert not result.success and len(session.calls) == 1


@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
def test_text_json_is_never_a_native_call(tmp_path, monkeypatch, provider):
    _, _, fs = filesystem(tmp_path)
    text = '```tool_call\n{"tool":"FilesystemTool","operation":"delete_file","args":{"file_path":"README.md"}}\n```'
    instance, _, model = adapter(monkeypatch, provider, [Response(frames(provider, text=text))])
    result = AgentExecutor(Agent(AgentConfig(model=model), provider=instance, tools=[fs])).run(
        "show an example", on_tool_call=lambda *a: pytest.fail("Text executed"))
    assert result.success and result.final_response == text


def test_gemini_retry_after_and_no_model_switch(monkeypatch):
    instance, session, model = adapter(monkeypatch, "gemini", [Response(status=429, headers={"Retry-After":"0"}),
        Response(frames("gemini", text="OK"))])
    assert instance.generate([LLMMessage(MessageRole.USER, "hello")], model).content == "OK"
    assert len(session.calls) == 2
    assert all(call[2]["json"]["model"] == model for call in session.calls)


def test_gemini_complete_calls_without_index_preserve_ids_and_signatures(monkeypatch):
    calls = [{"id": "call_a", "type": "function", "function": {"name": "RagTool__query", "arguments": '{"query":"fixture"}'},
              "extra_content": {"google": {"thought_signature": "opaque"}}},
             {"id": "call_b", "type": "function", "function": {"name": "FilesystemTool__view_file", "arguments": '{"file_path":"README.md"}'}}]
    events = [{"choices": [{"delta": {"role": "assistant", "tool_calls": calls}}]},
              {"choices": [{"delta": {"role": "assistant"}, "finish_reason": "stop"}]}, "[DONE]"]
    instance, session, model = adapter(monkeypatch, "gemini", [Response(events), Response(frames("gemini", text="OK"))])
    response = instance.generate_tools([], model, [])
    assert [c.id for c in response.tool_calls] == ["call_a", "call_b"]
    history = [LLMMessage(MessageRole.ASSISTANT, "", response.tool_calls, provider_data=response.provider_data)]
    history.extend(LLMMessage(MessageRole.TOOL, "result", tool_call_id=c.id) for c in response.tool_calls)
    assert instance.generate_tools(history, model, []).content == "OK"
    assert session.calls[1][2]["json"]["messages"][0]["tool_calls"] == calls


def test_oauth_completed_event_can_omit_output(monkeypatch):
    call = {"type": "function_call", "call_id": "one", "name": "RagTool__query",
            "arguments": '{"query":"fixture"}', "namespace": "laew"}
    events = [{"type": "response.output_item.added", "output_index": 0, "item": call | {"arguments": ""}},
              {"type": "response.function_call_arguments.delta", "output_index": 0, "delta": '{"query":'},
              {"type": "response.output_item.done", "output_index": 0, "item": call},
              {"type": "response.completed", "response": {"status": "completed", "output": []}}]
    instance, _, model = adapter(monkeypatch, "chatgpt", [Response(events)])
    result = instance.generate_tools([], model, [])
    assert result.tool_calls == [ToolCall("one", "RagTool__query", '{"query":"fixture"}')]
    assert result.provider_data["output"] == [call]


def test_oauth_unfinished_arguments_fail_even_with_completed_event(monkeypatch):
    events = [{"type": "response.output_item.added", "output_index": 0,
               "item": {"type": "function_call", "arguments": "{"}},
              {"type": "response.completed", "response": {"status": "completed"}}]
    instance, _, model = adapter(monkeypatch, "chatgpt", [Response(events)])
    with pytest.raises(CloudError, match="unfinished"):
        instance.generate_tools([], model, [])


@pytest.mark.parametrize("status,code", [(400,"INVALID_REQUEST"),(401,"AUTH_REQUIRED"),(403,"ACCESS_DENIED"),(404,"MODEL_UNAVAILABLE"),(429,"USAGE_LIMIT")])
def test_gemini_redacted_api_errors(monkeypatch, status, code):
    instance, session, model = adapter(monkeypatch, "gemini", [Response(status=status, headers={"Retry-After":"60"})])
    with pytest.raises(CloudError) as error:
        instance.generate([], model)
    assert error.value.code == code and "fixture" not in str(error.value)
    assert len(session.calls) == 1

@pytest.mark.parametrize("provider", ["openai-api", "chatgpt", "gemini"])
def test_native_transport_receives_automatic_knowledge_before_first_response(tmp_path, monkeypatch, provider):
    from laew.knowledge.routing import KnowledgeTurn

    project, vault, _ = filesystem(tmp_path)
    (vault / "environment.md").write_text("Shared environment evidence GLOBAL-NATIVE-54", encoding="utf-8")

    class Embedding:
        model, dimensions = "synthetic", 2

        def embed(self, text):
            return [1., 0.]

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

    rag = build_rag_tool({"rag": {"vector_store": {"enabled": False}}}, project_root=project,
                         knowledge_root=vault, embedding_service=Embedding())
    synchronize_scope(rag._pipeline.knowledge_base, "global")
    instance, session, model = adapter(monkeypatch, provider, [
        Response(frames(provider, text="Fixture response [source](@knowledge/environment.md)"))
    ])
    executor = AgentExecutor(Agent(AgentConfig(model=model), provider=instance, tools=[rag]))
    broker = PermissionBroker(project)
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None))
    message = "What is my AI environment configuration?"
    turn.prepare(executor, message, "project", lambda: None, rag)
    result = executor.run(message, stream=True, on_tool_call=turn.call)
    assert result.success and len(session.calls) == 1
    first = json.dumps(session.calls[0][2]["json"])
    assert "GLOBAL-NATIVE-54" in first and "environment.md" in first
    assert "PROJECT-FIXTURE" not in first
    assert "RagTool__query" in first
    assert turn.diagnostics["prefetch"][0]["status"] == "found"
