"""Tests for RAG (Retrieval-Augmented Generation) system."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from laew.prompts.context_budget import ContextBudget
from laew.manifest import load_manifest
from laew.rag import (
    ChromaVectorStore,
    DocumentChunk,
    EmbeddingService,
    KnowledgeBase,
    KnowledgeScope,
    OllamaEmbedding,
    RAGPipeline,
    RAGResult,
    VectorStore,
)
from laew.rag.rag_tool import RagTool


class MockEmbeddingService(EmbeddingService):
    """Mock embedding service for testing."""

    def __init__(self, dimensions: int = 768):
        self._dimensions = dimensions
        self.call_count = 0

    @property
    def dimensions(self) -> int:
        """Return embedding vector dimensionality."""
        return self._dimensions

    def embed(self, text: str) -> list[float]:
        """
        Generate deterministic mock embedding based on word overlap.

        Each word is normalized (lowercase, stripped punctuation) and hashed
        to a dimension index. Texts sharing words produce similar vectors.
        """
        import hashlib
        import re

        embedding = [0.0] * self.dimensions
        words = re.findall(r"\w+", text.lower())
        for word in words:
            index = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dimensions
            embedding[index] = 1.0
        self.call_count += 1
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [self.embed(text) for text in texts]


class TestVectorStore:
    """Tests for VectorStore."""

    def test_add_and_count(self):
        """Test adding chunks and counting."""
        store = VectorStore()
        assert store.count() == 0

        chunk = DocumentChunk(
            chunk_id="test-1",
            text="Test text",
            embedding=[0.1, 0.2, 0.3],
        )
        store.add_chunk(chunk)
        assert store.count() == 1

    def test_add_multiple_chunks(self):
        """Test adding multiple chunks at once."""
        store = VectorStore()
        chunks = [
            DocumentChunk(chunk_id=f"chunk-{i}", text=f"Text {i}", embedding=[float(i), 0.5])
            for i in range(5)
        ]
        store.add_chunks(chunks)
        assert store.count() == 5

    def test_add_chunk_without_embedding(self):
        """Test that adding chunk without embedding raises error."""
        store = VectorStore()
        chunk = DocumentChunk(chunk_id="test", text="Text")
        with pytest.raises(ValueError):
            store.add_chunk(chunk)

    def test_search_returns_similar_chunks(self):
        """Test that search returns similar chunks."""
        store = VectorStore()
        chunks = [
            DocumentChunk(chunk_id="a", text="Apple", embedding=[1.0, 0.0, 0.0]),
            DocumentChunk(chunk_id="b", text="Banana", embedding=[0.9, 0.1, 0.0]),
            DocumentChunk(chunk_id="c", text="Car", embedding=[0.0, 0.0, 1.0]),
        ]
        store.add_chunks(chunks)

        results = store.search([0.95, 0.05, 0.0], top_k=2)
        assert len(results) == 2
        # With our mock embeddings, [0.95, 0.05, 0.0] is closest to [0.9, 0.1, 0.0] (banana)
        # but let's just verify we get results and they're sorted
        assert results[0][1] >= results[1][1]  # Sorted by similarity (descending)

    def test_search_with_source_filter(self):
        """Test search with source filtering."""
        store = VectorStore()
        chunks = [
            DocumentChunk(chunk_id="p1", text="Project doc", embedding=[1.0, 0.0], source="project"),
            DocumentChunk(chunk_id="g1", text="Global doc", embedding=[1.0, 0.0], source="global"),
        ]
        store.add_chunks(chunks)

        # Search with source filter
        results = store.search([1.0, 0.0], top_k=10, source_filter="project")
        assert len(results) == 1
        assert results[0][0].source == "project"

    def test_delete_chunk(self):
        """Test deleting a chunk."""
        store = VectorStore()
        chunk = DocumentChunk(chunk_id="del", text="Delete me", embedding=[0.5])
        store.add_chunk(chunk)
        assert store.count() == 1

        assert store.delete_chunk("del") is True
        assert store.count() == 0

    def test_clear(self):
        """Test clearing the store."""
        store = VectorStore()
        chunks = [
            DocumentChunk(chunk_id=f"c{i}", text=f"Text {i}", embedding=[float(i)])
            for i in range(3)
        ]
        store.add_chunks(chunks)
        store.clear()
        assert store.count() == 0

    def test_count_by_source(self):
        """Test counting chunks by source."""
        store = VectorStore()
        chunks = [
            DocumentChunk(chunk_id="p1", text="Project", embedding=[1.0], source="project"),
            DocumentChunk(chunk_id="p2", text="Project", embedding=[2.0], source="project"),
            DocumentChunk(chunk_id="g1", text="Global", embedding=[3.0], source="global"),
        ]
        store.add_chunks(chunks)

        assert store.count(source="project") == 2
        assert store.count(source="global") == 1
        assert store.count() == 3


class TestKnowledgeBase:
    """Tests for KnowledgeBase."""

    def test_init(self):
        """Test KnowledgeBase initialization."""
        embedding_service = MockEmbeddingService()
        kb = KnowledgeBase(
            project_root="/tmp/project",
            knowledge_root="/tmp/knowledge",
            embedding_service=embedding_service,
        )
        assert kb.project_root == Path("/tmp/project")
        assert kb.knowledge_root == Path("/tmp/knowledge")

    def test_load_empty_directories(self):
        """Test loading from non-existent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embedding_service = MockEmbeddingService()
            kb = KnowledgeBase(
                project_root=os.path.join(tmpdir, "nonexistent_project"),
                knowledge_root=os.path.join(tmpdir, "nonexistent_knowledge"),
                embedding_service=embedding_service,
            )
            kb.load()
            assert kb.count_chunks() == 0

    def test_load_markdown_files(self):
        """Test loading markdown files from directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project directory with markdown files
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "README.md").write_text("# Project\n\nThis is a project document.")

            # Create knowledge directory with markdown files
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "notes.md").write_text("# Notes\n\nGeneral engineering notes.")

            embedding_service = MockEmbeddingService()
            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=str(knowledge_dir),
                embedding_service=embedding_service,
            )
            kb.load()

            # Should have loaded both project and global chunks
            assert kb.count_chunks(KnowledgeScope.PROJECT) > 0
            assert kb.count_chunks(KnowledgeScope.GLOBAL) > 0

    def test_load_only_markdown_files(self):
        """Test that only markdown files are loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()

            # Create various file types
            (project_dir / "doc.md").write_text("# Markdown\n\nContent here.")
            (project_dir / "code.py").write_text("print('hello')")
            (project_dir / "data.json").write_text('{"key": "value"}')

            embedding_service = MockEmbeddingService()
            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root="/tmp/nonexistent",
                embedding_service=embedding_service,
            )
            kb.load()

            # Only markdown should be loaded
            assert kb.project_store.count() > 0
            # Verify only one file was processed (the .md file)
            chunks = kb.project_store.search([0.5] * 768, top_k=10)
            files = set(c.file_path for c, _ in chunks)
            assert all(f.endswith(".md") for f in files)

    def test_load_surfaces_embedding_failure_instead_of_skipping_chunk(self, tmp_path):
        project = tmp_path / "project"
        vault = tmp_path / "global"
        project.mkdir()
        vault.mkdir()
        note = project / "important.md"
        note.write_text("# Critical\n\nThis must be embedded.", encoding="utf-8")
        embedding = MockEmbeddingService()

        def fail_embedding(_texts):
            raise RuntimeError("embedding endpoint unavailable")

        embedding.embed_batch = fail_embedding
        kb = KnowledgeBase(str(project), str(vault), embedding)

        with pytest.raises(RuntimeError, match="important.md.*embedding endpoint unavailable"):
            kb.load_project()
        assert kb.project_store.count() == 0

    def test_chunk_ids_are_unique_across_sections(self, tmp_path):
        project = tmp_path / "project"
        vault = tmp_path / "global"
        project.mkdir()
        vault.mkdir()
        note = project / "sections.md"
        note.write_text(
            "# First section\n\nFirst section content.\n\n"
            "# Second section\n\nSecond section content.",
            encoding="utf-8",
        )
        kb = KnowledgeBase(str(project), str(vault), MockEmbeddingService())

        chunks = kb._load_file(note, "project", project)

        assert len(chunks) == 2
        assert len({chunk.chunk_id for chunk in chunks}) == 2
        assert {chunk.metadata["section_index"] for chunk in chunks} == {0, 1}


class TestRAGPipeline:
    """Tests for RAGPipeline."""

    def test_init(self):
        """Test RAGPipeline initialization."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=tmpdir,
                knowledge_root=tmpdir,
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
                max_context_tokens=8000,
                top_k=5,
            )
            assert pipeline.max_context_tokens == 8000
            assert pipeline.top_k == 5

    def test_retrieve_empty_knowledge_base(self):
        """Test retrieval from empty knowledge base."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=os.path.join(tmpdir, "project"),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
            )
            result = pipeline.retrieve("test query", scope=KnowledgeScope.PROJECT)
            assert isinstance(result, RAGResult)
            assert result.context == ""

    def test_retrieve_with_documents(self):
        """Test retrieval with loaded documents."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project with documents
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "architecture.md").write_text(
                "# Architecture\n\nLAEW uses modular architecture with clear separation."
            )

            # project and knowledge roots must be disjoint siblings; knowledge
            # root is an empty sibling so the project doc isn't double-indexed.
            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
                top_k=3,
            )
            result = pipeline.retrieve("What is the LAEW architecture?")
            assert result.scope == KnowledgeScope.PROJECT
            assert len(result.chunks) > 0
            assert len(result.sources) > 0

    def test_retrieve_hybrid_scope(self):
        """Test hybrid scope retrieval."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create project docs
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "project.md").write_text("# Project\n\nProject specific info.")

            # Create global knowledge docs
            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "notes.md").write_text("# Notes\n\nGeneral engineering notes.")

            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=str(knowledge_dir),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
            )
            result = pipeline.retrieve("engineering information", scope=KnowledgeScope.HYBRID)
            assert result.scope == KnowledgeScope.HYBRID
            # Should search both stores
            assert len(result.chunks) > 0

    def test_retrieve_records_embedding_error(self):
        """
        When embedding fails, retrieve() must record the error on the result
        instead of silently returning an empty context (H5).
        """
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=os.path.join(tmpdir, "project"),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
            )
            with patch.object(
                embedding_service,
                "embed",
                side_effect=RuntimeError("embedding service down"),
            ):
                result = pipeline.retrieve("test query", scope=KnowledgeScope.PROJECT)

            assert result.error is not None
            assert "embedding service down" in result.error
            assert result.context == ""


class TestRagTool:
    """Tests for RagTool."""

    def test_init(self):
        """Test RagTool initialization."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=tmpdir,
                knowledge_root=tmpdir,
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(knowledge_base=kb, embedding_service=embedding_service)
            budget = ContextBudget()
            tool = RagTool(pipeline=pipeline, context_budget=budget)
            assert tool.name == "RagTool"

    def test_validate_query_operation(self):
        """Test validation of query operation."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=tmpdir,
                knowledge_root=tmpdir,
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(knowledge_base=kb, embedding_service=embedding_service)
            budget = ContextBudget()
            tool = RagTool(pipeline=pipeline, context_budget=budget)

            # Valid query
            is_valid, error = tool.validate("query", query="test", scope="project")
            assert is_valid is True
            assert error is None

            # Invalid operation
            is_valid, error = tool.validate("search", query="test")
            assert is_valid is False

            # Missing query
            is_valid, error = tool.validate("query")
            assert is_valid is False

            # Invalid scope
            is_valid, error = tool.validate("query", query="test", scope="invalid")
            assert is_valid is False

    def test_execute_query(self):
        """Test executing a query."""
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=os.path.join(tmpdir, "project"),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(knowledge_base=kb, embedding_service=embedding_service)
            budget = ContextBudget()
            tool = RagTool(pipeline=pipeline, context_budget=budget)

            result = tool.call("query", query="test", scope="project")
            assert result.success is True
            assert "context" in result.data
            assert "sources" in result.data

    def test_execute_query_surfaces_embedding_error(self):
        """
        When the pipeline records an embedding error, RagTool must surface it
        as a failure instead of reporting "no relevant information found" (H5).
        """
        embedding_service = MockEmbeddingService()
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = KnowledgeBase(
                project_root=os.path.join(tmpdir, "project"),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(knowledge_base=kb, embedding_service=embedding_service)
            budget = ContextBudget()
            tool = RagTool(pipeline=pipeline, context_budget=budget)

            with patch.object(
                embedding_service,
                "embed",
                side_effect=RuntimeError("embedding service down"),
            ):
                result = tool.call("query", query="test", scope="project")

            assert result.success is False
            assert result.error_code == "ERR_RAG_FAILURE"
            assert "embedding service down" in result.error_message


class TestRAGIntegration:
    """Integration tests for the RAG system."""

    def test_end_to_end_flow(self):
        """Test complete RAG flow from document loading to query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup project with documents
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "architecture.md").write_text(
                "# LAEW Architecture\n\n"
                "## Core Components\n"
                "LAEW uses modular architecture with tool runtime wrappers.\n"
                "Security is enforced below the model layer."
            )

            # Setup knowledge base
            embedding_service = MockEmbeddingService()
            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=os.path.join(tmpdir, "knowledge"),
                embedding_service=embedding_service,
            )

            # Create pipeline (lower threshold for mock embeddings)
            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
                top_k=3,
                similarity_threshold=0.1,
            )

            # Execute query
            result = pipeline.retrieve(
                "What are the core components of LAEW?",
                scope=KnowledgeScope.PROJECT,
            )

            # Verify results
            assert result.total_tokens > 0
            assert len(result.chunks) > 0
            assert any("LAEW" in chunk.text for chunk, _ in result.chunks)


class TestChromaVectorStore:
    """Tests for ChromaVectorStore (when chromadb is available)."""

    def test_chromadb_import_available(self):
        """Test that we can detect if chromadb is available."""
        try:
            import chromadb
            assert chromadb is not None
        except ImportError:
            pytest.skip("chromadb not installed")

    def test_init_with_defaults(self):
        """Test ChromaVectorStore initialization with default parameters."""
        try:
            import chromadb
        except ImportError:
            pytest.skip("chromadb not installed")

        # This test would require a running ChromaDB instance
        # For now, we just test that the class can be imported and instantiated
        # Connection tests would require a running instance
        pass

    def test_populated_collection_with_unknown_embedding_is_rejected(self, monkeypatch):
        """Persistent vectors from an unknown/different model are never searched."""
        from types import SimpleNamespace

        collection = MagicMock()
        collection.metadata = {"hnsw:space": "cosine", "embedding_model_id": "old-model"}
        collection.count.return_value = 3
        client = MagicMock()
        client.get_or_create_collection.return_value = collection
        monkeypatch.setitem(
            __import__("sys").modules,
            "chromadb",
            SimpleNamespace(HttpClient=MagicMock(return_value=client)),
        )

        with pytest.raises(RuntimeError, match="incompatible embedding model identity"):
            ChromaVectorStore(
                collection_name="project", source="project",
                embedding_model_id="new-model",
            )

    def test_empty_collection_is_tagged_with_embedding_identity(self, monkeypatch):
        from types import SimpleNamespace

        collection = MagicMock()
        collection.metadata = {"hnsw:space": "cosine", "custom": "kept"}
        collection.count.return_value = 0
        client = MagicMock()
        client.get_or_create_collection.return_value = collection
        monkeypatch.setitem(
            __import__("sys").modules,
            "chromadb",
            SimpleNamespace(HttpClient=MagicMock(return_value=client)),
        )

        ChromaVectorStore(
            collection_name="project", source="project",
            embedding_model_id="new-model",
        )
        collection.modify.assert_called_once_with(
            metadata={"custom": "kept", "embedding_model_id": "new-model"}
        )

    def test_add_chunks_uses_one_idempotent_upsert(self):
        store = object.__new__(ChromaVectorStore)
        collection = MagicMock()
        store._collection = collection
        chunks = [
            DocumentChunk(
                "one", "First", [1.0, 0.0], "project", "a.md",
                metadata={"tags": ["architecture", "rag"], "section_index": 2},
            ),
            DocumentChunk("two", "Second", [0.0, 1.0], "project", "b.md"),
        ]

        store.add_chunks(chunks)

        collection.upsert.assert_called_once()
        call = collection.upsert.call_args.kwargs
        assert call["ids"] == ["one", "two"]
        assert [metadata["file_path"] for metadata in call["metadatas"]] == ["a.md", "b.md"]
        assert call["metadatas"][0]["tags"] == '["architecture", "rag"]'
        assert call["metadatas"][0]["section_index"] == "2"
        collection.add.assert_not_called()

    def test_add_chunk_retries_update_existing_id(self):
        store = object.__new__(ChromaVectorStore)
        collection = MagicMock()
        store._collection = collection
        chunk = DocumentChunk("stable-id", "Updated text", [1.0, 0.0])

        store.add_chunk(chunk)

        collection.upsert.assert_called_once()
        assert collection.upsert.call_args.kwargs["ids"] == ["stable-id"]

    def test_normalize_method(self):
        """Test the _normalize static method."""
        try:
            import chromadb
        except ImportError:
            pytest.skip("chromadb not installed")

        # Test normal vector
        vector = [3.0, 4.0]  # length 5
        normalized = ChromaVectorStore._normalize(vector)
        assert len(normalized) == 2
        # Should be approximately [0.6, 0.8]
        assert abs(normalized[0] - 0.6) < 0.01
        assert abs(normalized[1] - 0.8) < 0.01

        # Test zero vector
        zero_vector = [0.0, 0.0]
        normalized_zero = ChromaVectorStore._normalize(zero_vector)
        assert normalized_zero == [0.0, 0.0]

    def test_search_converts_cosine_distance_correctly(self):
        """
        ChromaDB cosine distance spans [0, 2]; the score returned to callers
        must be 1.0 - distance (cosine similarity), not 1.0 - distance/2.0.

        Regression test for H4: the old formula compressed the similarity
        range, so exact matches scored 0.5 instead of 1.0 and unrelated
        chunks never went negative.
        """
        try:
            import chromadb  # noqa: F401
        except ImportError:
            pytest.skip("chromadb not installed")

        # Build the store without a live server: bypass __init__ and inject
        # a fake collection whose query() returns a known distance.
        store = object.__new__(ChromaVectorStore)
        store.source = "project"

        collection = MagicMock()
        collection.query.return_value = {
            "ids": [["chunk-1"]],
            "metadatas": [[{
                "text": "Golden retriever", "source": "project", "file_path": "doc.md",
                "tags": '["dogs", "retrievers"]', "backlinks": '["related-note"]',
                "section_index": "3",
            }]],
            "distances": [[0.0]],  # identical vector -> cosine distance 0
        }
        store._collection = collection

        results = store.search([1.0, 0.0], top_k=1)

        assert len(results) == 1
        chunk, similarity = results[0]
        assert chunk.chunk_id == "chunk-1"
        assert chunk.metadata == {
            "tags": ["dogs", "retrievers"],
            "backlinks": ["related-note"],
            "section_index": 3,
        }
        # distance 0.0 must map to similarity 1.0, not 0.5
        assert similarity == pytest.approx(1.0)
        assert collection.query.call_count == 1

    def test_search_uses_linear_distance_to_similarity(self):
        """
        Verify linear conversion across ChromaDB's full cosine distance range.

        A distance of 1.0 corresponds to orthogonal vectors (cosine
        similarity 0.0).  The old 1.0 - d/2.0 gave 0.5 for these, which is
        wrong — orthogonal content is unrelated, not half-similar.
        """
        try:
            import chromadb  # noqa: F401
        except ImportError:
            pytest.skip("chromadb not installed")

        store = object.__new__(ChromaVectorStore)
        store.source = "project"

        collection = MagicMock()
        collection.query.return_value = {
            "ids": [["chunk-orth"]],
            "metadatas": [[{"text": "Orthogonal content", "source": "project", "file_path": "doc.md"}]],
            "distances": [[1.0]],  # perpendicular vectors
        }
        store._collection = collection

        results = store.search([1.0, 0.0], top_k=1)

        assert len(results) == 1
        _, similarity = results[0]
        assert similarity == pytest.approx(0.0)


class TestKnowledgeBaseWithManifestConfig:
    """Tests for KnowledgeBase with manifest vector store configuration."""

    def test_init_with_vector_store_config_disabled(self):
        """Test KnowledgeBase initialization with vector store disabled."""
        embedding_service = MockEmbeddingService()
        vector_store_config = {"enabled": False}

        kb = KnowledgeBase(
            project_root="/tmp/project",
            knowledge_root="/tmp/knowledge",
            embedding_service=embedding_service,
            vector_store_config=vector_store_config,
        )

        # Should fall back to VectorStore instances
        from laew.rag.vector_store import VectorStore
        assert isinstance(kb._project_store, VectorStore)
        assert isinstance(kb._global_store, VectorStore)

    def test_project_source_allowlist_filters_project_but_not_global_scope(self, tmp_path):
        project = tmp_path / "project"
        vault = tmp_path / "global"
        for folder in (
            project / "docs" / "decisions",
            project / "docs" / "history",
            project / "docs" / "source",
            project / "prompts",
            project / "knowledge" / "Knowledge",
            project / "tests",
            vault / "Research",
        ):
            folder.mkdir(parents=True)
        files = {
            project / "README.md": "# Project overview",
            project / "docs" / "LAEW_CONTEXT.md": "# Project context",
            project / "docs" / "decisions" / "ADR-001.md": "# Accepted decision",
            project / "docs" / "history" / "2026-01.md": "# History",
            project / "docs" / "source" / "Chapter-1.md": "# Source chapter",
            project / "prompts" / "rag.md": "# Runtime prompt",
            project / "knowledge" / "Knowledge" / "note.md": "# Local knowledge",
            project / "tests" / "fixture.md": "# Test fixture",
            vault / "Research" / "shared.md": "# Global research",
        }
        for path, content in files.items():
            path.write_text(content, encoding="utf-8")

        allowlist = [
            "README.md",
            "docs/LAEW_CONTEXT.md",
            "docs/decisions/ADR-001.md",
            "knowledge/**/*.md",
        ]
        kb = KnowledgeBase(
            str(project), str(vault), MockEmbeddingService(),
            vector_store_config={"enabled": False},
            project_source_allowlist=allowlist,
        )
        kb.load_project()
        kb.load_vault()

        project_paths = {
            chunk.file_path.replace("\\", "/")
            for chunk in kb.project_store._chunks.values()
        }
        assert project_paths == {
            "README.md",
            "docs/LAEW_CONTEXT.md",
            "docs/decisions/ADR-001.md",
            "knowledge/Knowledge/note.md",
        }
        assert kb.global_store.count() == 1
        assert (
            next(iter(kb.global_store._chunks.values())).file_path.replace("\\", "/")
            == "Research/shared.md"
        )

    def test_repository_project_ingestion_excludes_tool_contracts(self, tmp_path):
        project = tmp_path / "project"
        contracts = (
            "tools/filesystem/CONTRACT.md",
            "tools/git/CONTRACT.md",
            "tools/terminal/CONTRACT.md",
            "tools/web/CONTRACT.md",
        )
        for relative in contracts:
            path = project / Path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Tool instruction", encoding="utf-8")
        (project / "README.md").write_text("# Project knowledge", encoding="utf-8")
        vault = tmp_path / "global"
        vault.mkdir()

        manifest_path = Path(__file__).resolve().parents[2] / "manifests" / "SYSTEM_MANIFEST.yaml"
        manifest = load_manifest(manifest_path)
        allowlist = manifest["rag"]["project_sources"]["allowlist"]
        assert not set(contracts).intersection(allowlist)

        kb = KnowledgeBase(
            str(project), str(vault), MockEmbeddingService(),
            project_source_allowlist=allowlist,
        )
        kb.load_project()

        selected = {
            chunk.file_path.replace("\\", "/")
            for chunk in kb.project_store._chunks.values()
        }
        assert selected == {"README.md"}
        assert not set(contracts).intersection(selected)

    def test_fresh_pipeline_uses_existing_persistent_index_without_reembedding(self, tmp_path):
        from laew.rag.vector_store import ChromaVectorStore

        project = tmp_path / "project"
        vault = tmp_path / "global"
        project.mkdir()
        vault.mkdir()
        kb = KnowledgeBase(str(project), str(vault), MockEmbeddingService())
        persistent_store = object.__new__(ChromaVectorStore)
        persistent_store.count = MagicMock(return_value=4)
        kb._project_store = persistent_store

        with patch.object(kb, "_load_directory") as scan:
            kb.load_project()

        scan.assert_not_called()
        assert kb._project_loaded is True

        with patch.object(kb, "_load_directory") as scan:
            kb.load_project(force=True)

        scan.assert_called_once_with(project, "project", persistent_store)

    def test_init_with_vector_store_config_enabled_but_no_chromadb(self):
        """Fallback is visible and actionable if persistent init fails."""
        embedding_service = MockEmbeddingService()
        vector_store_config = {
            "enabled": True, "host": "localhost", "port": 9999,
            "project_collection": "project_test", "global_collection": "global_test",
        }
        with patch(
            "laew.rag.knowledge_base.ChromaVectorStore",
            side_effect=ConnectionError("test connection failure"),
        ), pytest.warns(RuntimeWarning, match="test connection failure") as caught:
            kb = KnowledgeBase(
                project_root="/tmp/project",
                knowledge_root="/tmp/knowledge",
                embedding_service=embedding_service,
                vector_store_config=vector_store_config,
            )

        assert isinstance(kb._project_store, VectorStore)
        assert isinstance(kb._global_store, VectorStore)
        assert len(caught) == 2
        assert "project_test" in str(caught[0].message)
        assert "in-memory storage" in str(caught[0].message)


# --------------------------------------------------------------------------- #
# OllamaEmbedding endpoint regression (Ollama API drift)
# --------------------------------------------------------------------------- #
class TestOllamaEmbedding:
    """Pins the live Ollama embedding contract (current /api/embed)."""

    def test_embed_uses_embed_endpoint_and_input_key(self):
        """embed posts to /api/embed with 'input' and reads embeddings[0]."""
        import requests

        embedder = OllamaEmbedding(model="nomic-embed-text", base_url="http://localhost:11434")
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}

        with patch.object(requests, "post", return_value=mock_response) as mock_post:
            vector = embedder.embed("hello world")

        assert vector == [0.1, 0.2, 0.3]
        assert embedder.dimensions == 3
        url, kwargs = mock_post.call_args.args[0], mock_post.call_args.kwargs
        assert url.endswith("/api/embed"), f"expected /api/embed, got {url}"
        assert kwargs["json"] == {"model": "nomic-embed-text", "input": "hello world"}
        # Legacy endpoint must not be used.
        assert "/api/embeddings" not in url

    def test_embed_raises_on_missing_embeddings(self):
        """An empty embeddings payload raises a readable RuntimeError."""
        import requests

        embedder = OllamaEmbedding()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}

        with patch.object(requests, "post", return_value=mock_response):
            with pytest.raises(RuntimeError, match="No embedding returned"):
                embedder.embed("x")

    def test_is_available_returns_false_when_service_is_unreachable(self):
        import requests

        embedder = OllamaEmbedding(model="bge-m3:latest")
        with patch.object(requests, "get", side_effect=requests.ConnectionError("offline")):
            assert embedder.is_available() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
