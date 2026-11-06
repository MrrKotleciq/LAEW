"""Source policy survives intent classification and topic binding."""

from types import SimpleNamespace

import pytest

from laew.knowledge.routing import KnowledgeTurn, resolve_turn, route_sources
from laew.llm.base import LLMMessage, MessageRole
from laew.security.path_resolver import PathResolver
from laew.tools.base import ErrorCode, ToolResult
from laew.tools.filesystem import FilesystemTool
from laew.tools.git import GitTool
from laew.tools.terminal import TerminalTool
from laew.tools.web import WebTool


@pytest.mark.parametrize("message,policy", [
    ("Przetłumacz poniższy tekst. Nie używaj Global Knowledge.", {"excluded_scopes": ("global",)}),
    ("Przeredaguj tekst. Użyj wyłącznie pamięci długoterminowej.",
     {"memory_only": True, "rag_disabled": True}),
    ("Use only the Global Knowledge. Rewrite the supplied paragraph.", {"only_scope": "global"}),
    ("Based on the supplied data, answer the question. Use only @project.", {"only_scope": "project"}),
    ("Ile to 2 + 2? Nie używaj pamięci.", {"memory_excluded": True}),
    ("Skip RAG. What is 2 + 2?", {"rag_disabled": True}),
    ("Rewrite this. Don't use Global RAG or Project RAG.",
     {"excluded_scopes": ("global", "project"), "rag_disabled": False}),
    ("Translate this. Use only Memory. Do not use Memory.",
     {"memory_only": True, "memory_excluded": True}),
    ("Rewrite this. Use only @project. Do not use @project.",
     {"only_scope": "project", "excluded_scopes": ("project",)}),
    ("Rewrite this. Use only @project. Use only @knowledge.", {"source_conflict": True}),
    ("Rewrite this. Use only Memory. Use only @knowledge.", {"source_conflict": True}),
])
def test_self_contained_tasks_keep_policy_without_automatic_lookup(message, policy):
    decision = route_sources(message, in_project=True)

    assert decision.self_contained and not decision.memory and not decision.scopes
    for field, value in policy.items():
        assert getattr(decision, field) == value


def test_follow_up_keeps_an_exclusion_after_the_bounded_search_anchor():
    topic = "Translate this text. " + "a " * 420 + "Do not use Global Knowledge."
    history = [LLMMessage(MessageRole.USER, topic)]
    decision, query, bound = resolve_turn("More details?", history, in_project=True)

    assert bound and query.startswith(topic[:800])
    assert decision.self_contained and decision.excluded_scopes == ("global",)
    assert not decision.memory and not decision.scopes


def test_a_question_about_skipping_rag_is_not_a_source_restriction():
    assert not route_sources("When should I skip RAG?", in_project=True).rag_disabled


def test_follow_up_exclusions_narrow_the_previous_policy_until_a_source_switch():
    history = [LLMMessage(MessageRole.USER, "Use only @project to explain the indexing strategy.")]
    for message in ("Without @project.", "And its limitations?"):
        decision, _, bound = resolve_turn(message, history, in_project=True)
        assert bound and not decision.scopes and not decision.memory
        assert decision.only_scope == "project" and decision.excluded_scopes == ("project",)
        history.append(LLMMessage(MessageRole.USER, message))

    switch = "Check only @knowledge."
    decision, _, bound = resolve_turn(switch, history, in_project=True)
    assert bound and decision.scopes == ("global",) and not decision.excluded_scopes
    history.append(LLMMessage(MessageRole.USER, switch))
    decision, _, bound = resolve_turn("And its limitations? Do not use Memory.", history, in_project=True)
    assert bound and decision.scopes == ("global",) and decision.memory_excluded


@pytest.mark.parametrize("message,allowed", [
    ("Rewrite this. Use only Global Knowledge.", set()),
    ("Rewrite this. Use only Project Knowledge.", {"git", "terminal", "nested terminal"}),
    ("Rewrite this. Without Project Knowledge.", {"web"}),
    ("Rewrite this. Without Global Knowledge.", {"git", "terminal", "nested terminal", "web"}),
    ("What is an embedding?", {"git", "terminal", "nested terminal", "vault terminal", "web"}),
])
def test_other_evidence_tools_keep_their_source_boundaries(tmp_path, message, allowed):
    terminal = TerminalTool(workspace_root=tmp_path)
    calls = {
        "git": (GitTool(repo_root=tmp_path), "git_status", {}),
        "terminal": (terminal, "run_command", {"command": "pwd"}),
        "nested terminal": (terminal, "run_command", {"command": "git status", "cwd": "nested"}),
        "vault terminal": (terminal, "run_command", {"command": "git status", "cwd": "vault"}),
        "web": (WebTool(), "search_web", {"query": "documentation"}),
    }
    dispatched = []

    def broker(tool, operation, args):
        dispatched.append((tool, operation, args))
        return ToolResult.ok({})

    turn = KnowledgeTurn(broker)
    filesystem = FilesystemTool(PathResolver(project_root=tmp_path, knowledge_root=tmp_path / "vault"))
    executor = SimpleNamespace(agent=SimpleNamespace(tools={"FilesystemTool": filesystem}))
    turn.prepare(executor, message, "active", lambda: None, None)
    for name, call in calls.items():
        result = turn.call(*call)
        if name in allowed:
            assert result.success
        else:
            assert result.error_code == ErrorCode.ERR_UNAUTHORIZED
    assert dispatched == [call for name, call in calls.items() if name in allowed]
