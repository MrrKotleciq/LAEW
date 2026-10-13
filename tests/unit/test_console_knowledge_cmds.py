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
from laew.rag.knowledge_base import KnowledgeScope


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def _cfg(tmp_path):
    return {
        "project_root": str(tmp_path / "project"),
        "knowledge_root": str(tmp_path),
        "structure": ["Decisions", "Research"],
        "embedding_model": "nomic-embed-text",
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
    assert "Total: 0 note(s)" in capsys.readouterr().out


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


def test_knowledge_stats_reports_vault_and_store(state, tmp_path, capsys):
    """``knowledge stats`` prints vault note counts and @knowledge chunk counts."""
    kb = MagicMock()
    kb.structure.return_value = {"Decisions": 2, "Research": 2}
    kb.load_vault.return_value = None
    kb.global_store.count.return_value = 7
    with patch(
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
    with patch(
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


def test_manifest_knowledge_cfg_parses_real_manifest(state, capsys):
    """_manifest_knowledge_cfg reads the real manifest's Second Brain config.

    Exercises the real manifest-reading path (no mock of the function or its
    dependency), so the manifest wiring is covered, not just the patched dict.
    """
    cfg = _manifest_knowledge_cfg(state)
    assert cfg["project_root"] == "."
    assert cfg["knowledge_root"] == "knowledge"
    assert cfg["structure"] == ["Knowledge", "Decisions", "Research", "Templates"]
    assert cfg["embedding_model"] == "bge-m3:latest"


def test_manifest_knowledge_cfg_fallback_default_embedding(state, capsys):
    """A manifest with an embedding role but no model_name falls back to a default.

    The embedding model is read from ``models.roles.embedding.model_name`` when
    the manifest declares one; when the role omits ``model_name`` the function
    falls back to the hardcoded ``"nomic-embed-text"`` default (a valid fallback
    per the session resolution order). ``load_manifest`` is patched to bypass
    manifest validation and isolate this branch.
    """
    raw = {
        "version": "0.1.0",
        "models": {"roles": {"embedding": {}}},
        "workspace": {"root": "."},
        "memory": {"second_brain": {"path": "knowledge"}},
    }
    with patch.object(SessionState, "load_manifest", return_value=raw):
        cfg = _manifest_knowledge_cfg(state)
    assert cfg["embedding_model"] == "nomic-embed-text"
    assert cfg["knowledge_root"] == "knowledge"
