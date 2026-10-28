"""Tests for the ``rag`` console command (query, embed, stats).

Pipeline behaviour itself is covered by tests/unit/test_rag.py; here we verify
the console wiring: scope/k parsing, the offline error net, and stats output.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from laew.console.commands.rag import (
    _build_pipeline,
    cmd_rag_query,
    cmd_rag_embed,
    cmd_rag_stats,
    _dispatch,
)
from laew.console.state import SessionState


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


def _retrieval(error=None, chunks=None, scope="project", tokens=120, sources=("a.md",)):
    if chunks is None:
        chunks = ["c1", "c2", "c3"]
    return SimpleNamespace(
        error=error,
        chunks=chunks,
        scope=SimpleNamespace(value=scope),
        total_tokens=tokens,
        sources=list(sources),
        context="retrieved context text",
    )


def test_build_pipeline_resolves_manifest_knowledge_alias_to_shared_root(tmp_path):
    project = tmp_path / "Projects" / "LAEW"
    (project / "manifests").mkdir(parents=True)
    state = SessionState(manifest_path=str(project / "manifests" / "SYSTEM_MANIFEST.yaml"))
    manifest = {
        "workspace": {"root": "."},
        "memory": {"second_brain": {"path": "@knowledge"}},
        "rag": {"pipeline": {"top_k": 4, "max_context_tokens": 500}},
    }
    embedding = MagicMock()
    with patch.object(state, "load_manifest", return_value=manifest), patch(
        "laew.runtime.build_embedding_service", return_value=embedding
    ), patch("laew.console.commands.rag.KnowledgeBase") as knowledge_base:
        _build_pipeline(state)

    _, kwargs = knowledge_base.call_args
    assert Path(kwargs["project_root"]) == project.resolve()
    assert Path(kwargs["knowledge_root"]) == (tmp_path / "Knowledge").resolve()
    knowledge_base.assert_called_once()


def test_rag_query_success(state, capsys):
    """A successful retrieval prints sources and context."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = _retrieval()
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["show", "me", "docs"], state) == 0
    out = capsys.readouterr().out
    assert "[OK] 3 chunk(s)" in out
    assert "a.md" in out
    assert "retrieved context text" in out


def test_rag_query_scope_and_k_parsing(state, capsys):
    """scope= and k= args are parsed and forwarded to the pipeline."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = _retrieval()
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["hello", "scope=global", "k=7"], state) == 0
    _, kwargs = pipeline.retrieve.call_args
    assert kwargs["scope"].name == "GLOBAL"
    assert kwargs["top_k"] == 7


def test_rag_query_invalid_scope(state, capsys):
    """An unknown scope alias is rejected without reaching the pipeline."""
    pipeline = MagicMock()
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["hi", "scope=mesa"], state) == 1
    assert "unknown scope" in capsys.readouterr().out
    pipeline.retrieve.assert_not_called()


def test_rag_query_invalid_k(state, capsys):
    """A non-numeric k= value is rejected."""
    pipeline = MagicMock()
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["hi", "k=abc"], state) == 1
    assert "invalid k value" in capsys.readouterr().out


def test_rag_query_missing_query(state, capsys):
    """No query text yields a usage error."""
    assert cmd_rag_query(["scope=project"], state) == 1
    assert "usage:" in capsys.readouterr().out


def test_rag_query_offline_error_net(state, capsys):
    """A dead embedding endpoint surfaces a readable [!] instead of crashing."""
    with patch(
        "laew.console.commands.rag._build_pipeline",
        side_effect=ConnectionError("could not reach ollama"),
    ):
        assert cmd_rag_query(["hello"], state) == 1
    out = capsys.readouterr().out
    assert "RAG query failed" in out and "ollama" in out


def test_rag_query_retrieval_error_reported(state, capsys):
    """A retrieval error recorded on the result is printed and returns 1."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = _retrieval(error="embedding service down")
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_query(["hello"], state) == 1
    out = capsys.readouterr().out
    assert "retrieval error: embedding service down" in out


def test_rag_embed_loads_knowledge(state, capsys):
    """rag embed loads the knowledge base and reports chunk counts."""
    pipeline = MagicMock()
    pipeline.knowledge_base.count_chunks.return_value = 42
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_embed([], state) == 0
    pipeline.knowledge_base.synchronize.assert_called_once_with(force=False)
    assert "42 chunks" in capsys.readouterr().out


def test_rag_embed_force_flag(state, capsys):
    """rag embed force passes force=True to the loader."""
    pipeline = MagicMock()
    pipeline.knowledge_base.count_chunks.return_value = 0
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_embed(["force"], state) == 0
    pipeline.knowledge_base.synchronize.assert_called_once_with(force=True)


def test_rag_stats_reports_counts_and_backend(state, capsys):
    """rag stats prints pipeline params and per-store chunk counts."""
    pipeline = MagicMock()
    pipeline.get_stats.return_value = {
        "top_k": 5,
        "max_context_tokens": 8000,
        "similarity_threshold": 0.35,
        "project_chunks": 10,
        "global_chunks": 3,
    }
    from laew.rag.vector_store import VectorStore
    pipeline.knowledge_base.project_store = VectorStore()
    pipeline.knowledge_base.global_store = VectorStore()
    pipeline.knowledge_base._vector_store_config = {"enabled": True}
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert cmd_rag_stats([], state) == 0
    out = capsys.readouterr().out
    assert "top_k: 5" in out
    assert "project store: 10 chunk(s)" in out
    assert "global store: 3 chunk(s)" in out
    assert "backend: VectorStore (persistent: False)" in out


def test_manifest_project_source_allowlist_keeps_scopes_separate(state):
    from fnmatch import fnmatchcase
    from laew.console.commands.rag import _manifest_rag_config

    config = _manifest_rag_config(state.load_manifest(), state)
    allowlist = config["project_source_allowlist"]
    assert Path(config["project_root"]).resolve() == Path.cwd().resolve()
    assert Path(config["knowledge_root"]).resolve() == Path(r"C:\ROOT\Knowledge")
    assert "README.md" in allowlist
    assert "docs/decisions/ADR-011-project-memory-vs-global-knowledge-separation.md" in allowlist
    assert "knowledge/**/*.md" in allowlist
    assert not any("docs/history" in path for path in allowlist)
    assert not any(path.startswith("prompts/") or path.startswith("tests/") for path in allowlist)

    root = Path(config["project_root"]).resolve()
    selected = set()
    for markdown in root.rglob("*.md"):
        relative = markdown.relative_to(root).as_posix()
        if not any(fnmatchcase(relative, pattern) for pattern in allowlist):
            continue
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__", "venv")
            for part in Path(relative).parts
        ):
            continue
        try:
            markdown.resolve(strict=True).relative_to(root)
        except (OSError, ValueError):
            continue
        selected.add(relative)

    assert len(selected) == 44
    assert "README.md" in selected
    assert "knowledge/Knowledge/02-Database-Indexing.md" in selected
    assert not any(path.startswith(("docs/history/", "docs/source/", "prompts/", "tests/")) for path in selected)
    assert not any(path.startswith("tools/") and path.endswith("/CONTRACT.md") for path in selected)


def test_rag_dispatch_routes_subcommands(state, capsys):
    """The rag dispatcher routes onto query/embed/stats."""
    pipeline = MagicMock()
    pipeline.retrieve.return_value = _retrieval()
    with patch("laew.console.commands.rag._build_pipeline", return_value=pipeline):
        assert _dispatch(["query", "hi"], state) == 0
        assert "[OK]" in capsys.readouterr().out

    assert _dispatch(["nonsense"], state) == 1
    assert "unknown rag subcommand" in capsys.readouterr().out

    # Default (no args) is stats.
    stats = MagicMock()
    stats.get_stats.return_value = {
        "top_k": 5, "max_context_tokens": 8000, "similarity_threshold": 0.35,
        "project_chunks": 1, "global_chunks": 1,
    }
    stats.knowledge_base.project_store = MagicMock()
    stats.knowledge_base.global_store = MagicMock()
    stats.knowledge_base._vector_store_config = {}
    with patch("laew.console.commands.rag._build_pipeline", return_value=stats):
        assert _dispatch([], state) == 0
        assert "top_k" in capsys.readouterr().out
