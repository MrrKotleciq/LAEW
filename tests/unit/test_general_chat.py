"""General scope must remain isolated below the UI boundary."""

from unittest.mock import MagicMock, patch

from laew.runtime import build_shared_tools
from laew.security.permissions import PermissionBroker
from laew.tools.git import GitTool
from laew.tools.terminal import TerminalTool
from laew.web import WorkspaceService
from tests.unit.test_rag import MockEmbeddingService


def roots(tmp_path):
    projects = tmp_path / "Projects"
    project = projects / "Alpha"
    knowledge = tmp_path / "Knowledge"
    project.mkdir(parents=True)
    knowledge.mkdir()
    (project / "secret.md").write_text("project-only", encoding="utf-8")
    (knowledge / "note.md").write_text("# Beacon\n\nUnique beacon knowledge", encoding="utf-8")
    return projects, project, knowledge


def test_general_tools_rag_and_broker_are_scope_restricted(tmp_path):
    projects, project, knowledge = roots(tmp_path)
    tools = build_shared_tools(manifest={}, general=True, projects_root=projects,
                               knowledge_root=knowledge, rag_embedding_service=MockEmbeddingService())
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {"FilesystemTool", "WebTool", "RagTool"}
    fs, rag = by_name["FilesystemTool"], by_name["RagTool"]
    broker = PermissionBroker(None)
    assert rag._pipeline.knowledge_base.project_root is None
    assert rag._pipeline.knowledge_base.project_store is None
    assert broker.call(fs, "view_file", {"file_path": "@knowledge/note.md"}, None).success
    for path in ("@project/secret.md", "@projects/Alpha/secret.md", str(project / "secret.md")):
        assert not broker.call(fs, "view_file", {"file_path": path}, None).success
    for scope in ("project", "hybrid"):
        assert not rag.execute("query", query="beacon", scope=scope).success
        assert not broker.call(rag, "query", {"query": "beacon", "scope": scope}, None).success
    assert not broker.call(GitTool(repo_root=project), "status", {}, None).success
    assert broker.classify(TerminalTool(workspace_root=project), "run", {}) == "denied"
    from laew.rag.sync import synchronize_scope
    synchronize_scope(rag._pipeline.knowledge_base, "global")
    result = broker.call(rag, "query", {"query": "beacon"}, None)
    assert result.success and result.data["sources"] == ["@knowledge/note.md"]
    from laew.agent import Agent, AgentConfig, AgentExecutor
    from tests.integration.test_chief_rag_scopes import Provider
    provider = Provider("beacon", "global")
    agent = Agent(AgentConfig(project_scope=False), provider=provider, tools=tools)
    from laew.console.session_store import SessionStore
    store = SessionStore(tmp_path / "sessions")
    conversation = store.create_conversation("general", None)
    result = AgentExecutor(agent).run(
        "Find beacon", on_tool_call=lambda tool, op, args: broker.call(tool, op, args, None),
        on_event=lambda event: store.append_conversation_event(conversation["id"], event))
    assert result.success and result.steps[0].tool_result.success
    assert "@knowledge/note.md" in provider.observation
    events = store.load_conversation(conversation["id"])["events"]
    assert [event["kind"] for event in events] == ["user", "assistant", "tool_call", "tool_result", "assistant"]
    assert events[2]["call_id"] == events[3]["call_id"]


def test_general_knowledge_write_requires_approval(tmp_path):
    projects, _, knowledge = roots(tmp_path)
    fs = build_shared_tools(general=True, projects_root=projects, knowledge_root=knowledge)[0]
    broker = PermissionBroker(None)
    args = {"file_path": "@knowledge/new.md", "content": "---\ntype: docs\nscope: global\n---\n# New\n", "expected_sha256": ""}
    assert not broker.call(fs, "write_knowledge_note", args, None).success
    def approve(event):
        if event["type"] == "approval":
            broker.decide(event["id"], "allow", "test")
    assert broker.call(fs, "write_knowledge_note", args, approve, "test").success
    assert (knowledge / "new.md").read_text(encoding="utf-8") == args["content"]


def test_workbench_switches_to_general_without_reusing_project_tools(tmp_path):
    projects, project, _ = roots(tmp_path)
    service = WorkspaceService(tmp_path / "manifest.yaml", project, projects, tmp_path)
    provider = MagicMock()
    provider.is_available.return_value = True
    with (patch("laew.web.load_manifest", return_value={}),
          patch("laew.web.build_provider_for_role", return_value=provider),
          patch("laew.web.resolve_model_name", return_value="test")):
        assert service.status()["project"] == "Alpha"
        assert "GitTool" in service._agent.tools
        assert service.chat("hello", expected_project_id=None)[0] == 409
        assert service.select_project(None)[1]["active_project"] is None
        assert service.status()["project"] is None
        assert set(service._agent.tools) == {"FilesystemTool", "WebTool", "RagTool"}
        assert service._agent.tools["FilesystemTool"].resolver.project_root is None
        events = []
        service.stream_chat("hello", "manifest", service._id_for_path(project), events.append)
        assert events[0]["type"] == "error"
        assert service.select_project(service._id_for_path(project))[0] == 200
        assert service.status()["project"] == "Alpha"
        with patch.object(service, "_discover_projects", return_value={}):
            assert service.list_projects()["active_project"] is None
        assert service.status()["project"] is None
        assert "GitTool" not in service._agent.tools


def test_cli_general_uses_the_same_scope_and_broker(tmp_path):
    from types import SimpleNamespace
    from laew.cli import cmd_chat
    roots(tmp_path)
    args = SimpleNamespace(general=True, workspace_root=str(tmp_path), model=None, base_url=None,
                           timeout=None, provider=None, manifest="manifest.yaml", resume=None,
                           session=None, no_persist=True, no_stream=True)
    provider = MagicMock()
    provider.base_url = "http://localhost"
    result = MagicMock(success=True, final_response="Hello")
    with (patch("laew.cli.load_manifest", return_value={}),
          patch("laew.cli.build_provider_for_role", return_value=provider),
          patch("laew.cli.resolve_model_name", return_value="model"),
          patch("laew.cli.AgentExecutor") as executor,
          patch("laew.rag.sync.SyncScheduler"),
          patch("builtins.input", side_effect=["hello", "exit"])):
        executor.return_value.run.return_value = result
        assert cmd_chat(args) == 0
    agent = executor.call_args.args[0]
    assert set(agent.tools) == {"FilesystemTool", "WebTool", "RagTool"}
    assert agent.tools["FilesystemTool"].resolver.project_root is None
