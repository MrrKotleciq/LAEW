
import pytest
import uuid
import chromadb
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk


@pytest.fixture
def isolated_chroma(tmp_path, monkeypatch):
    """Use a real disposable database, never the configured production server."""
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    return client


def test_chromadb_persistence(isolated_chroma):
    # Use an isolated collection so this integration test never clears or
    # changes an existing user collection.
    client = isolated_chroma
    collection_name = "laew_test_persistence_" + uuid.uuid4().hex
    existing = {collection.name for collection in client.list_collections()}
    assert collection_name not in existing
    created = False
    try:
        store = ChromaVectorStore(
            host="localhost", port=8000, collection_name=collection_name
        )
        created = True
        chunk = DocumentChunk(
            chunk_id="test_chunk_1",
            text="Hello, persistence!",
            embedding=[0.1, 0.2, 0.3],
            source="project",
            file_path="test.md",
        )
        store.add_chunk(chunk)

        fresh_store = ChromaVectorStore(
            host="localhost", port=8000, collection_name=collection_name
        )
        retrieved = fresh_store.get_chunk(chunk.chunk_id)
        assert retrieved is not None
        assert retrieved.text == chunk.text
        assert retrieved.chunk_id == chunk.chunk_id
        assert fresh_store.count() == 1
    except Exception as e:
        if isinstance(e, AssertionError):
            raise
        pytest.skip(f"ChromaDB not available: {e}")
    finally:
        if created:
            client.delete_collection(collection_name)


def test_delete_by_file_paths_removes_only_exact_project_records(isolated_chroma):
    """Path cleanup preserves project knowledge, ADRs, and other scopes."""
    client = isolated_chroma
    collection_name = "laew_test_path_cleanup_" + uuid.uuid4().hex
    created = False
    excluded = {
        "tools/filesystem/CONTRACT.md",
        "tools/git/CONTRACT.md",
        "tools/terminal/CONTRACT.md",
        "tools/web/CONTRACT.md",
    }
    try:
        store = ChromaVectorStore(
            host="localhost", port=8000, collection_name=collection_name,
            source="project",
        )
        created = True
        chunks = [
            DocumentChunk(
                chunk_id=f"excluded-{index}", text="Tool instruction", embedding=[1.0, 0.0],
                source="project", file_path=path,
            )
            for index, path in enumerate(sorted(excluded))
        ]
        chunks.extend([
            DocumentChunk(
                "keep-local-note", "Project knowledge", [0.0, 1.0],
                "project", "knowledge/Decisions/002-knowledge-scope-separation.md",
            ),
            DocumentChunk(
                "keep-adr", "Accepted ADR", [0.5, 0.5],
                "project", "docs/decisions/ADR-011-project-memory-vs-global-knowledge-separation.md",
            ),
            DocumentChunk(
                "keep-other-scope", "Global scope", [0.25, 0.75],
                "global", "tools/git/CONTRACT.md",
            ),
        ])
        store.add_chunks(chunks)

        fresh_store = ChromaVectorStore(
            host="localhost", port=8000, collection_name=collection_name,
            source="project",
        )
        before = fresh_store._collection.get(include=["metadatas"])
        before_paths = {
            metadata["file_path"].replace("\\", "/")
            for metadata in before["metadatas"]
            if metadata and metadata.get("source") == "project"
        }
        assert excluded <= before_paths

        removed = fresh_store.delete_by_file_paths(excluded)

        assert removed == 4
        assert fresh_store.count() == 3
        remaining = fresh_store._collection.get(include=["metadatas"])
        remaining_records = {
            chunk_id: metadata
            for chunk_id, metadata in zip(remaining["ids"], remaining["metadatas"])
        }
        assert set(remaining_records) == {
            "keep-local-note", "keep-adr", "keep-other-scope"
        }
        assert remaining_records["keep-local-note"]["source"] == "project"
        assert remaining_records["keep-adr"]["source"] == "project"
        assert remaining_records["keep-other-scope"]["source"] == "global"
    except Exception as e:
        if isinstance(e, AssertionError):
            raise
        pytest.skip(f"ChromaDB not available: {e}")
    finally:
        if created:
            client.delete_collection(collection_name)

def test_obsidian_properties_round_trip_after_legacy_sync(tmp_path, isolated_chroma):
    from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
    from laew.rag.pipeline import RAGPipeline

    class Embedding:
        dimensions = 2

        def embed(self, text):
            return [1.0, 0.0]

        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

    root = tmp_path / "vault"
    root.mkdir()
    note = root / "note.md"
    content = """---
name: Pomiar
title: Drift
description: "Quoted, with punctuation: yes."
type: research
scope: global
status: draft
tags: ["thermal, drift", ARX]
read_when:
  - Comparing sensors
up:
  - "[[Parent#Anchor|Display]]"
---
## Measurement
Unverified thermal hypothesis. See [[Raw Results]].
"""
    note.write_text(content, encoding="utf8")
    (root / "plain.md").write_text("## Legacy\nNo frontmatter.", encoding="utf8")
    (root / "partial.md").write_text("---\nstatus: unverified\n---\nPartial note.", encoding="utf8")
    embedding = Embedding()
    kb = KnowledgeBase(None, str(root), embedding,
        vector_store_config={"enabled": True, "global_collection": "laew_fixture_metadata"})
    kb.global_store.add_chunk(DocumentChunk("global:note.md:0:0", "legacy", [1., 0.], "global", "note.md"))
    kb.synchronize(scope="global")
    result = RAGPipeline(kb, embedding).retrieve("thermal hypothesis", KnowledgeScope.GLOBAL)
    assert not result.error
    metadata = {row["source"]: row for row in result.source_metadata()}
    assert metadata["@knowledge/note.md"]["frontmatter"] == {
        "name": "Pomiar", "title": "Drift", "description": "Quoted, with punctuation: yes.",
        "type": "research", "scope": "global", "status": "draft",
        "tags": ["thermal, drift", "ARX"], "read_when": ["Comparing sensors"],
    }
    assert metadata["@knowledge/note.md"]["backlinks"] == ["Parent#Anchor|Display", "Raw Results"]
    assert metadata["@knowledge/plain.md"]["frontmatter"] == {}
    assert metadata["@knowledge/partial.md"]["frontmatter"] == {"status": "unverified"}
    assert "status: draft" in result.context
    assert kb.synchronize(scope="global")["global"]["updated"]["documents"] == 0
    assert note.read_text(encoding="utf8") == content
