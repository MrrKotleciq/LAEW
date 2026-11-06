"""Exercise both recall entry points through the agent adapter, using isolated data."""
from types import SimpleNamespace

import pytest
from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.knowledge import horizon
from laew.knowledge.routing import KnowledgeTurn
from laew.knowledge.sufficiency import configured_assessor
from laew.llm.llamacpp import LlamaCppProvider
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore
from laew.memory.tool import MemoryTool
from laew.security.permissions import PermissionBroker
from test_knowledge_routing import ObservingProvider, isolated_runtime  # noqa: F401


class Judge:
    def __init__(self, sufficient):
        self.sufficient = sufficient
        self.questions = []
    def assess(self, question, memories):
        self.questions.append(question)
        return {'status': 'completed', 'sufficient': self.sufficient, 'calls': 1, 'elapsed_ms': 0}


@pytest.mark.parametrize('model_initiated', [False, True])
@pytest.mark.parametrize('sufficient', [False, True])
def test_assessment_controls_search_and_evidence(isolated_runtime, tmp_path, model_initiated, sufficient):
    rag = isolated_runtime.build()
    store = MemoryStore(tmp_path / 'isolated.db')
    store.save_settings({'semantic_enabled': False})
    store.remember('My favorite book is Dune.')
    memory = MemoryService(store)
    prompt = 'Tell me about the favorite book.' if model_initiated else 'What is my favorite book?'
    request = ('```tool_call\n{"tool":"MemoryTool","operation":"recall",'
               '"args":{"query":"favorite book"}}\n```') if model_initiated else None
    provider = ObservingProvider('Fixed response', follow_up=request)
    agent = Agent(AgentConfig(), provider=provider, tools=[rag, MemoryTool(memory)])
    executor = AgentExecutor(agent)
    broker = PermissionBroker(None)
    judge = Judge(sufficient)
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None), assessor=judge)
    turn.prepare(executor, prompt, None, lambda: memory, rag)
    assert executor.run(prompt, on_tool_call=turn.call, on_diagnostic=turn.observe,
                        on_tool_batch=turn.after_tools).success
    context = '\n'.join(message.content for batch in provider.messages for message in batch)
    assert 'Dune' in context
    assert ('GLOBAL-7319' in context) is (not sufficient)
    assert len(judge.questions) == 1 and judge.questions[0] == prompt
    assessments = [turn.diagnostics.get('assessment')] if not model_initiated else [
        t.get('memory_recall', {}).get('assessment') for t in turn.tools]
    assert any(a and a['status'] == ('sufficient' if sufficient else 'unverified') for a in assessments)


def test_polish_natural_language_memory_reaches_adapter_without_rag(isolated_runtime, tmp_path):
    rag = isolated_runtime.build()
    store = MemoryStore(tmp_path / 'isolated-polish.db')
    store.save_settings({'semantic_enabled': False})
    store.remember('Użytkownik uczył się hiszpańskiego, ale zakończył naukę.')
    memory = MemoryService(store)
    provider = ObservingProvider('Fixed response')
    agent = Agent(AgentConfig(), provider=provider, tools=[rag])
    executor = AgentExecutor(agent)
    broker = PermissionBroker(None)
    judge = Judge(True)
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None), assessor=judge)
    prompt = 'Jakiego języka się uczyłem?'
    turn.prepare(executor, prompt, None, lambda: memory, rag)
    assert executor.run(prompt, on_diagnostic=turn.observe).success
    assert 'hiszpańskiego' in provider.messages[0][0].content
    assert turn.diagnostics['assessment']['status'] == 'sufficient'
    assert not turn.diagnostics['prefetch']


@pytest.mark.parametrize("model_initiated", [False, True])
@pytest.mark.parametrize("scenario", ["horizon", "invalid_active", "positive_active"])
def test_horizon_policy_for_both_recall_paths_with_project_isolation(
        isolated_runtime, tmp_path, monkeypatch, model_initiated, scenario):
    rag = isolated_runtime.build()
    store = MemoryStore(tmp_path / "horizon.db")
    store.save_settings({"semantic_enabled": False})
    store.remember("My favorite book is Dune.", scope="project", project_id="current")
    store.remember("My favorite book is PRIVATE-OTHER-PROJECT.", scope="project", project_id="other")
    memory = MemoryService(store)
    prompt = "Tell me about the favorite book." if model_initiated else "What is my favorite book?"
    tool_call = ('```tool_call\n{"tool":"MemoryTool","operation":"recall",'
                 '"args":{"query":"favorite book"}}\n```') if model_initiated else None
    provider = ObservingProvider("Fixed response", follow_up=tool_call)
    agent = Agent(AgentConfig(model="local-test"), provider=provider,
                  tools=[rag, MemoryTool(memory, "current")])
    assessed_text = []

    def nli(path, timeout, payload=None):
        if scenario != "horizon":
            raise TimeoutError()
        if path == "/readyz":
            return {"ready": True, "max_input_tokens": 1024}
        assessed_text.append(payload["premise"])
        return {"entailment_score": 0.999, "not_entailment_score": 0.001, "input_tokens": 20}

    def active_request(_provider, _url, payload, *, session):
        assessed_text.append(payload["messages"][-1]["content"])
        content = '{"sufficient":true}' if scenario == "positive_active" else "invalid"
        return SimpleNamespace(json=lambda: {"choices": [{"message": {"content": content}}]})

    monkeypatch.setattr(horizon, "_request", nli)
    monkeypatch.setattr("laew.knowledge.sufficiency.horizon_assessor", horizon.HorizonAssessor())
    monkeypatch.setattr(LlamaCppProvider, "_request", active_request)
    selected = SimpleNamespace(selected_provider=LlamaCppProvider("local-test"), config=agent.config)
    config = {"memory_sufficiency": {"enabled": True, "model": "horizon-preferred"}}
    assessor = configured_assessor(config, selected)
    broker = PermissionBroker(tmp_path)
    turn = KnowledgeTurn(lambda tool, op, args: broker.call(tool, op, args, None), assessor=assessor)
    executor = AgentExecutor(agent)
    turn.prepare(executor, prompt, "current", lambda: memory, rag)
    assert executor.run(prompt, on_tool_call=turn.call, on_diagnostic=turn.observe,
                        on_tool_batch=turn.after_tools).success
    context = "\n".join(message.content for batch in provider.messages for message in batch)
    assert "Dune" in context and "GLOBAL-7319" in context
    assert "PRIVATE-OTHER-PROJECT" not in context
    assert len(assessed_text) == 1 and "Dune" in assessed_text[0]
    assert "PRIVATE-OTHER-PROJECT" not in assessed_text[0]
    if model_initiated:
        assessment = next(t["memory_recall"]["assessment"] for t in turn.tools if "memory_recall" in t)
    else:
        assessment = turn.diagnostics["assessment"]
    assert assessment["status"] == "unverified"
    model = assessment["model_assessment"]
    if scenario == "horizon":
        assert model["backend"] == "horizon" and model["signal"] == "strong_entailment"
    else:
        assert model["backend"] == "active"
        assert model["horizon"]["error_category"] == "TimeoutError"
        if scenario == "positive_active":
            assert model["status"] == "completed" and model["signal"] == "reported_sufficient"
        else:
            assert model["status"] == "failed" and model["error_category"] == "JSONDecodeError"
