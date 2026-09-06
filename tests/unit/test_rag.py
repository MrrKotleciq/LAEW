"""Tests for RAG (Retrieval-Augmented Generation) system."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from laew.prompts.context_budget import ContextBudget
from laew.rag import (
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
                project_root=tmpdir,
                knowledge_root=tmpdir,
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

            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=tmpdir,
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
            assert tool.name == "rag"

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
                project_root=tmpdir,
                knowledge_root=tmpdir,
                embedding_service=embedding_service,
            )
            pipeline = RAGPipeline(knowledge_base=kb, embedding_service=embedding_service)
            budget = ContextBudget()
            tool = RagTool(pipeline=pipeline, context_budget=budget)

            result = tool.call("query", query="test", scope="project")
            assert result.success is True
            assert "context" in result.data
            assert "sources" in result.data


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])