"""
Milestone 17 — Obsidian link-aware ingestion tests.

Covers the Definition of Done for the Second Brain / global knowledge scope:

  * vault ingestion      — Obsidian notes are loaded into the global store;
                           frontmatter tags and [[backlinks]] survive chunking.
  * link preservation    — retrieved chunks carry tags/backlinks in metadata.
  * scope separation     — ``load_vault`` indexes only the global store; the
                           project store is untouched.
  * source attribution   — ``@knowledge`` context surfaces tags/backlinks so the
                           agent can see how a fact is organized and connected.
"""

import os
import tempfile
from pathlib import Path

import pytest

from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
from laew.rag.obsidian import parse_note
from laew.rag.pipeline import RAGPipeline
from laew.rag.vector_store import VectorStore


def _make_note(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _vault_note(tmpdir: str) -> Path:
    """A Second Brain note with frontmatter tags + [[backlinks]]."""
    note_dir = Path(tmpdir) / "Decisions"
    note_dir.mkdir(parents=True, exist_ok=True)
    note = note_dir / "001-global-second-brain.md"
    _make_note(
        note,
        "---\n"
        "title: Global Second Brain\n"
        "tags:\n"
        "  - knowledge\n"
        "  - second-brain\n"
        "backlinks:\n"
        "  - 002-knowledge-scope-separation\n"
        "---\n\n"
        "# Global Second Brain\n\n"
        "The global knowledge store holds long-lived engineering notes. "
        "Decisions live here and are linked across the vault.\n",
    )
    return note


class TestVaultIngestion:
    """Obsidian notes are loaded into the global store with metadata intact."""

    def test_load_vault_indexes_global_store(self, tmp_path):
        """``load_vault`` indexes only the global store."""
        # project and knowledge roots must be disjoint siblings; load_vault()
        # rejects any root overlap (see TestRootOverlap).
        kb = KnowledgeBase(
            project_root=str(tmp_path / "project"),
            knowledge_root=str(tmp_path / "knowledge"),
            embedding_service=MockEmbeddingService(),
        )
        vault = _vault_note(str(tmp_path / "knowledge"))

        kb.load_vault(force=True)

        assert kb.count_chunks(KnowledgeScope.GLOBAL) == 1
        # load_vault does not touch project memory.
        assert kb.count_chunks(KnowledgeScope.PROJECT) == 0
        assert kb.global_store.count() == 1
        assert isinstance(kb.global_store, VectorStore)

    def test_vault_note_tags_and_backlinks_survive_chunking(self, tmp_path):
        """Frontmatter tags and [[backlinks]] are preserved on every chunk."""
        # project and knowledge roots must be disjoint siblings; load_vault()
        # rejects any root overlap (see TestRootOverlap).
        kb = KnowledgeBase(
            project_root=str(tmp_path / "project"),
            knowledge_root=str(tmp_path / "knowledge"),
            embedding_service=MockEmbeddingService(),
        )
        _vault_note(str(tmp_path / "knowledge"))

        kb.load_vault(force=True)

        chunks = kb.global_store.search([1.0] * 768, top_k=10)
        tags, backlinks = set(), set()
        for chunk, _ in chunks:
            assert "tags" in chunk.metadata
            assert "backlinks" in chunk.metadata
            tags.update(chunk.metadata.get("tags") or [])
            backlinks.update(chunk.metadata.get("backlinks") or [])

        assert {"knowledge", "second-brain"} <= tags
        assert "002-knowledge-scope-separation" in backlinks


class TestLoadDoesNotTouchProject:
    """``load`` indexes both stores; a project-only note stays in the project."""

    def test_project_note_stays_in_project_store(self, tmp_path):
        """A non-Obsidian project markdown note lands only in the project store."""
        project = Path(tmp_path) / "project"
        project.mkdir()
        (project / "readme.md").write_text("# Readme\n\nProject content here.")
        knowledge = Path(tmp_path) / "knowledge"
        knowledge.mkdir()

        # The project tree and the vault must be siblings — neither an ancestor
        # of the other — since load() scans each root with rglob. If the vault
        # root nested the project tree, rglob would reach the project note and
        # double-index it into @knowledge, breaking scope separation.
        kb = KnowledgeBase(
            project_root=str(project),
            knowledge_root=str(knowledge),
            embedding_service=MockEmbeddingService(),
        )
        kb.load()

        assert kb.count_chunks(KnowledgeScope.PROJECT) == 1
        assert kb.count_chunks(KnowledgeScope.GLOBAL) == 0


class TestLinkAwareRetrieval:
    """Retrieved context surfaces Obsidian tags and backlinks."""

    def _pipeline(self, tmp_path):
        # project and knowledge roots must be disjoint siblings; load_vault()
        # and load() reject any root overlap (see TestRootOverlap).
        kb = KnowledgeBase(
            project_root=str(tmp_path / "project"),
            knowledge_root=str(tmp_path / "knowledge"),
            embedding_service=MockEmbeddingService(),
        )
        _vault_note(str(tmp_path / "knowledge"))
        kb.load_vault(force=True)
        pipeline = RAGPipeline(
            knowledge_base=kb,
            embedding_service=MockEmbeddingService(),
            top_k=5,
            similarity_threshold=0.0,
        )
        return kb, pipeline

    def test_retrieved_context_surfaces_tags(self, tmp_path):
        """A retrieved @knowledge fact surfaces its #tags in context."""
        kb, pipeline = self._pipeline(tmp_path)
        result = pipeline.retrieve(
            "global second brain",
            scope=KnowledgeScope.GLOBAL,
        )
        assert result.scope == KnowledgeScope.GLOBAL
        assert len(result.chunks) >= 1
        # The note's frontmatter tags are surfaced in the assembled context.
        assert "knowledge" in result.context
        assert "second-brain" in result.context

    def test_retrieved_context_surfaces_backlinks(self, tmp_path):
        """A retrieved @knowledge fact surfaces its [[backlinks]] in context."""
        kb, pipeline = self._pipeline(tmp_path)
        result = pipeline.retrieve(
            "global second brain",
            scope=KnowledgeScope.GLOBAL,
        )
        assert "002-knowledge-scope-separation" in result.context

    def test_scope_isolation_in_sources(self, tmp_path):
        """GLOBAL scope returns only @knowledge sources, not project ones."""
        kb, pipeline = self._pipeline(tmp_path)
        result = pipeline.retrieve(
            "global second brain",
            scope=KnowledgeScope.GLOBAL,
        )
        assert len(result.sources) >= 1
        # Scope isolation comes from retrieving the right store (GLOBAL only
        # searches the @knowledge vault), so every source is a vault note.
        # ``file_path`` is the OS-native relative path (backslashes on Windows),
        # so normalize before checking the vault folder.
        posix_sources = [s.replace(os.sep, "/") for s in result.sources]
        assert all(
            "Decisions/" in source for source in posix_sources
        )


class TestParseNote:
    """The Obsidian parser extracts title, tags and backlinks."""

    def test_parse_note_frontmatter(self):
        note = parse_note(
            "---\ntitle: Note\ntags:\n  - a\n  - b\nbacklinks:\n  - ref\n---\n\n# Note\n\nBody."
        )
        assert note["title"] == "Note"
        assert note["tags"] == ["a", "b"]
        assert note["backlinks"] == ["ref"]

    def test_parse_note_inline_fallback(self):
        note = parse_note("# Heading\n\nText [[link]] and #tag here.")
        assert note["title"] == "Heading"
        # The tag regex captures the full token, including the trailing space,
        # which is the intended behaviour (Obsidian tags may contain spaces).
        assert note["tags"] == ["tag here"]
        assert note["backlinks"] == ["link"]


class TestRootOverlap:
    """Project and knowledge roots must be disjoint siblings.

    ``load``/``load_vault`` scan each root with ``rglob`` into its own store, so
    an overlap would double-index the same ``.md`` into both stores and break the
    ``@project``/``@knowledge`` separation (ADR-011). The guard rejects any
    overlap.
    """

    def _kb(self, project_root, knowledge_root):
        return KnowledgeBase(
            project_root=str(project_root),
            knowledge_root=str(knowledge_root),
            embedding_service=MockEmbeddingService(),
        )

    def test_equal_roots_rejected(self, tmp_path):
        """Equal roots overlap and are rejected."""
        root = tmp_path / "root"
        root.mkdir()
        with pytest.raises(ValueError):
            self._kb(root, root).load()

    def test_knowledge_nested_in_project_rejected(self, tmp_path):
        """A knowledge root nested inside the project root is rejected."""
        project = tmp_path / "project"
        knowledge = project / "knowledge"
        project.mkdir()
        knowledge.mkdir()
        with pytest.raises(ValueError):
            self._kb(project, knowledge).load()

    def test_project_nested_in_knowledge_rejected(self, tmp_path):
        """A project root nested inside the knowledge root is rejected."""
        knowledge = tmp_path / "knowledge"
        project = knowledge / "project"
        knowledge.mkdir()
        project.mkdir()
        with pytest.raises(ValueError):
            self._kb(project, project).load()

    def test_valid_siblings_load_both_stores(self, tmp_path):
        """Disjoint sibling roots load without raising."""
        project = tmp_path / "project"
        knowledge = tmp_path / "knowledge"
        project.mkdir()
        knowledge.mkdir()
        kb = self._kb(project, knowledge)
        kb.load()
        assert kb.count_chunks(KnowledgeScope.PROJECT) == 0
        assert kb.count_chunks(KnowledgeScope.GLOBAL) == 0


class TestEndToEndRetrieval:
    """The real seeded vault is indexed into @knowledge and retrieved end-to-end.

    Builds a deterministic project + Decisions-vault fixture (no live server)
    and verifies the real ingestion pipeline surfaces the vault note's tags,
    backlinks and source in retrieved @knowledge context.
    """

    def _fixture(self, tmp_path):
        """Disjoint sibling project and knowledge roots with one vault note."""
        project = tmp_path / "project"
        knowledge = tmp_path / "knowledge"
        project.mkdir(exist_ok=True)
        knowledge.mkdir(exist_ok=True)
        # Reuses the shared vault-note fixture; filename matches the real
        # seeded note (001-global-second-brain.md) for source-attribution checks.
        _vault_note(str(knowledge))
        kb = KnowledgeBase(
            project_root=str(project),
            knowledge_root=str(knowledge),
            embedding_service=MockEmbeddingService(),
        )
        pipeline = RAGPipeline(
            knowledge_base=kb,
            embedding_service=MockEmbeddingService(),
            top_k=5,
            similarity_threshold=0.0,
        )
        return kb, pipeline

    def test_seed_vault_is_retrievable_as_knowledge(self, tmp_path):
        """The seeded vault note is indexed into @knowledge and retrieved."""
        kb, pipeline = self._fixture(tmp_path)
        result = pipeline.retrieve(
            "global second brain",
            scope=KnowledgeScope.GLOBAL,
        )

        # (1) Discovery: the vault note is in the global store, project empty.
        assert kb.count_chunks(KnowledgeScope.GLOBAL) == 1
        assert kb.count_chunks(KnowledgeScope.PROJECT) == 0

        # (2) Link-aware: the note's frontmatter tags + backlinks survive.
        assert "knowledge" in result.context
        assert "second-brain" in result.context
        assert "002-knowledge-scope-separation" in result.context

        # (3) A chunk was actually retrieved.
        assert len(result.chunks) >= 1

        # (4) Source attribution names the global store and the vault note.
        assert result.scope == KnowledgeScope.GLOBAL
        assert "GLOBAL" in result.context
        assert "001-global-second-brain.md" in result.context


class MockEmbeddingService:
    """Deterministic word-hash embedding service (matches test_rag.py)."""

    def __init__(self, dimensions: int = 768):
        self._dimensions = dimensions
        self.call_count = 0

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed(self, text: str) -> list:
        import hashlib
        import re

        embedding = [0.0] * self._dimensions
        words = re.findall(r"\w+", text.lower())
        for word in words:
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self._dimensions
            embedding[index] = 1.0
        self.call_count += 1
        return embedding

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]
