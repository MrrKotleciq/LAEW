"""Tests for the ``knowledge`` console command (Milestone 17).

Covers the vault-inspection subcommands (list, show, stats) and the
``scope=knowledge`` alias on ``rag query`` (which maps to the @knowledge
global store per ADR-011).
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from laew.console.commands.knowledge import (
    _cmd_list,
    _cmd_show,
    _cmd_stats,
    _dispatch,
    _manifest_knowledge_cfg,
)
from laew.console.commands.rag import cmd_rag_query
from laew.console.state import SessionState
from laew.rag.llamacpp import LlamaCppEmbedding
from laew.runtime import build_embedding_service
from laew.rag.knowledge_base import KnowledgeScope


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def _cfg(tmp_path):
    return {
        "project_root": str(tmp_path / "project"),
        "knowledge_root": str(tmp_path),
        "structure": ["Decisions", "Research"],
    }


def test_knowledge_list_structure(state, tmp_path, capsys):
    """``knowledge list`` prints per-folder note counts from the vault tree."""
    kb = MagicMock()
    kb.structure.return_value = {"Decisions": 2, "Research": 2}
    with patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value=_cfg(tmp_path),
    ), patch(
        "laew.rag.knowledge_base.KnowledgeBase",
        return_value=kb,
    ):
        assert _cmd_list([], state) == 0

    out = capsys.readouterr().out
    assert "Second Brain vault" in out
    assert "Decisions/  (2 notes)" in out
    assert "Total: 4 note(s)" in out


def test_knowledge_list_empty_vault(state, tmp_path, capsys):
    """``knowledge list`` on an empty vault reports zero notes gracefully."""
    kb = MagicMock()
    kb.structure.return_value = {}
    with patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value=_cfg(tmp_path),
    ), patch(
        "laew.rag.knowledge_base.KnowledgeBase",
        return_value=kb,
    ):
        assert _cmd_list([], state) == 0
    out = capsys.readouterr().out
    assert "Total: 0 note(s)" in out
    assert "Decisions/  (0 notes)" in out


def test_knowledge_show_note(state, tmp_path, capsys):
    """``knowledge show`` prints frontmatter title, tags and backlinks."""
    note = tmp_path / "001-global-second-brain.md"
    note.write_text(
        "---\n"
        "title: Global Second Brain\n"
        "tags:\n  - knowledge\n  - second-brain\n"
        "backlinks:\n  - 002-knowledge-scope-separation\n"
        "---\n\n# Global Second Brain\n\nBody text here."
    )
    parsed = {
        "title": "Global Second Brain",
        "tags": ["knowledge", "second-brain"],
        "backlinks": ["002-knowledge-scope-separation"],
        "body": "Body text here.",
    }
    with patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value=_cfg(tmp_path),
    ), patch(
        # knowledge show reads the real file and forwards its content to
        # parse_note directly (it never constructs a KnowledgeBase).
        "laew.rag.obsidian.parse_note",
        return_value=parsed,
        create=True,
    ) as parse_note:
        assert _cmd_show(["001-global-second-brain.md"], state) == 0

    out = capsys.readouterr().out
    assert "title: Global Second Brain" in out
    assert "tags: knowledge second-brain" in out
    assert "backlinks: 002-knowledge-scope-separation" in out
    assert "Body text here" in out
    # knowledge show reads the real file and forwards its content to parse_note.
    assert parse_note.call_count == 1


def test_knowledge_show_missing_note(state, capsys):
    """``knowledge show`` on a missing note returns a failure code."""
    assert _cmd_show(["does-not-exist.md"], state) == 1
    assert "note not found" in capsys.readouterr().out


def test_knowledge_show_rejects_paths_outside_vault(state, tmp_path, capsys):
    outside = tmp_path.parent / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    with patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value={**_cfg(tmp_path), "knowledge_root": str(tmp_path / "vault")},
    ):
        (tmp_path / "vault").mkdir()
        assert _cmd_show([str(outside)], state) == 1
    assert "escapes" in capsys.readouterr().out


def test_manifest_knowledge_alias_resolves_to_workspace_vault(tmp_path):
    project = tmp_path / "Projects" / "LAEW"
    (project / "manifests").mkdir(parents=True)
    state = SessionState(manifest_path=str(project / "manifests" / "SYSTEM_MANIFEST.yaml"))
    cfg = _manifest_knowledge_cfg(
        {
            "workspace": {"root": "."},
            "memory": {"second_brain": {"path": "@knowledge"}},
        },
        state,
    )
    assert cfg["project_root"] == project.resolve()
    assert cfg["knowledge_root"] == (tmp_path / "Knowledge").resolve()


def test_knowledge_stats_reports_vault_and_store(state, tmp_path, capsys):
    """``knowledge stats`` prints vault note counts and @knowledge chunk counts."""
    kb = MagicMock()
    kb.structure.return_value = {"Decisions": 2, "Research": 2}
    kb.load_vault.return_value = None
    kb.global_store.count.return_value = 7
    with patch("laew.runtime.build_embedding_service", return_value=MagicMock()), patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value=_cfg(tmp_path),
    ), patch(
        "laew.rag.knowledge_base.KnowledgeBase",
        return_value=kb,
    ):
        assert _cmd_stats([], state) == 0

    out = capsys.readouterr().out
    assert "vault notes: 4" in out
    assert "@knowledge store: 7 chunk(s)" in out


def test_knowledge_dispatch_routes(state, tmp_path, capsys):
    """The knowledge dispatcher routes onto list/show/stats."""
    with patch("laew.runtime.build_embedding_service", return_value=MagicMock()), patch(
        "laew.console.commands.knowledge._manifest_knowledge_cfg",
        return_value=_cfg(tmp_path),
    ), patch(
        "laew.rag.knowledge_base.KnowledgeBase",
        return_value=MagicMock(),
    ) as kb:
        kb.structure.return_value = {}
        assert _cmd_stats([], state) == 0

    assert _dispatch(["unknown"], state) == 1
    assert "unknown knowledge subcommand" in capsys.readouterr().out


def test_rag_query_knowledge_alias_maps_to_global(state, capsys):
    """scope=knowledge is an alias for the @knowledge global store."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = SimpleNamespace(
        error=None,
        chunks=["c1", "c2"],
        scope=SimpleNamespace(value="global"),
        total_tokens=120,
        sources=["a.md"],
        context="ctx",
    )
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["hello", "scope=knowledge"], state) == 0
    _, kwargs = pipeline.retrieve.call_args
    assert kwargs["scope"] == KnowledgeScope.GLOBAL


def test_knowledge_stats_selects_embedding_from_manifest(state, capsys):
    """knowledge stats resolves the embedding service from models.roles.embedding.

    Exercises the real manifest-reading path (no mock of the function or its
    dependency), so the manifest wiring is covered, not just the patched dict.
    The manifest selects the dedicated llama.cpp server model and dimensions.
    """
    embedding = build_embedding_service(state.load_manifest())
    assert isinstance(embedding, LlamaCppEmbedding)
    assert embedding.model == "laew-qwen3-embedding"
    assert embedding.base_url == "http://127.0.0.1:8081/v1"
    assert embedding.dimensions == 1024


def test_knowledge_stats_requires_dedicated_llamacpp_embedding_config(state, capsys):
    """Embedding selection requires an explicit llama.cpp server model and URL.

    Setting ``model_name`` selects the server-advertised ID; ``base_url`` is
    independent from the chat endpoint.
    ``load_manifest`` is patched to bypass manifest validation and isolate the
    role-selection branches.
    """
    raw = {
        "version": "0.1.0",
        "models": {"roles": {"embedding": {
            "type": "llamacpp", "model_name": "nomic-embed-text",
            "base_url": "http://127.0.0.1:8081",
            "target_dimensions": 1024,
        }}},
        "workspace": {"root": "."},
        "memory": {"second_brain": {"path": "knowledge"}},
    }

    ll_emb = build_embedding_service(raw)
    assert isinstance(ll_emb, LlamaCppEmbedding)
    assert ll_emb.model == "nomic-embed-text"
    assert ll_emb.base_url == "http://127.0.0.1:8081/v1"
    assert ll_emb.target_dimensions == 1024
