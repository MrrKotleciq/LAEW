
import pytest
import uuid
import chromadb
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk

def test_chromadb_persistence():
    # Use an isolated collection so this integration test never clears or
    # changes an existing user collection.
    client = chromadb.HttpClient(host="localhost", port=8000)
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


def test_delete_by_file_paths_removes_only_exact_project_records():
    """Path cleanup preserves project knowledge, ADRs, and other scopes."""
    client = chromadb.HttpClient(host="localhost", port=8000)
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
