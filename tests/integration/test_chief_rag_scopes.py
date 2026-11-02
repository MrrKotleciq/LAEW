"""Chief Agent retrieval through isolated project collections and a shared vault."""

import json

import pytest

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.base import LLMResponse
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool


class Embedding:
    model = "scope-integration"
    dimensions = 3

    def embed_batch(self, texts):
        return [self.embed(text) for text in texts]

    def embed(self, text):
        if "PROJECT-A" in text: return [1., 0., 0.]
        if "PROJECT-B" in text: return [0., 1., 0.]
        return [0., 0., 1.]


class Provider:
    def __init__(self, query, scope): self.query, self.scope, self.calls, self.observation = query, scope, 0, ""
    def is_available(self): return True
    def generate(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            call = {"tool": "RagTool", "operation": "query", "args": {"query": self.query, "scope": self.scope}}
            return LLMResponse(content="```tool_call\n" + json.dumps(call) + "\n```", model="fake")
        self.observation = messages[-1].content
        return LLMResponse(content="Retrieved the requested knowledge.", model="fake")


def test_chief_uses_selected_project_and_shared_global(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path / "db"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    projects = tmp_path / "projects"; projects.mkdir()
    first = projects / "a"; first.mkdir()
    second = tmp_path / "external"; second.mkdir()
    vault = tmp_path / "knowledge"; vault.mkdir()
    (first / "README.md").write_text("PROJECT-A-VERIFY-7319", encoding="utf-8")
    (second / "README.md").write_text("PROJECT-B-VERIFY-4826", encoding="utf-8")
    (vault / "shared.md").write_text("Shared engineering knowledge", encoding="utf-8")
    manifest = {"memory": {"second_brain": {"path": "@knowledge"}},
                "rag": {"vector_store": {"enabled": True, "global_collection": "chief_shared_test"}}}
    tools = [build_rag_tool(manifest, project_root=p, projects_root=projects, knowledge_root=vault,
                            embedding_service=Embedding()) for p in (first, second)]
    for tool in tools:
        synchronize_scope(tool._pipeline.knowledge_base, "project")
    synchronize_scope(tools[0]._pipeline.knowledge_base, "global")
    for tool, code, language in zip(tools, ("PROJECT-A-VERIFY-7319", "PROJECT-B-VERIFY-4826"), ("en", "pl")):
        provider = Provider(code, "project")
        executor = AgentExecutor(Agent(AgentConfig(documentation_language=language), provider=provider, tools=[tool]))
        result = executor.run("Find the project code")
        assert result.success and result.steps[0].tool_result.success
        assert code in provider.observation and "@project/README.md" in provider.observation
        assert ("PROJECT-B-VERIFY-4826" if "PROJECT-A" in code else "PROJECT-A-VERIFY-7319") not in provider.observation
    provider = Provider("shared knowledge", "global")
    executor = AgentExecutor(Agent(AgentConfig(), provider=provider, tools=[tools[1]]))
    result = executor.run("Find the shared note")
    assert result.steps[0].tool_result.success
    assert "@knowledge/shared.md" in provider.observation
