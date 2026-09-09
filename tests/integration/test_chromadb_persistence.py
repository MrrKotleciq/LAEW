
import pytest
import time
import chromadb
from laew.rag.vector_store import ChromaVectorStore, DocumentChunk

def test_chromadb_persistence():
    # Arrange: Initialize client to connect to the Docker container
    # The ChromaVectorStore uses localhost:8000 by default
    try:
        store = ChromaVectorStore(host="localhost", port=8000, collection_name="test_persistence")
        # Reachability probe: raises when the ChromaDB daemon is not running.
        store.count()
    except Exception as e:
        pytest.skip(f"ChromaDB not available: {e}")
        return

    chunk_id = "test_chunk_1"
    chunk = DocumentChunk(
        chunk_id=chunk_id,
        text="Hello, persistence!",
        embedding=[0.1, 0.2, 0.3],
        source="project",
        file_path="test.txt"
    )

    # Act 1: Add chunk
    store.add_chunk(chunk)

    # Act 2: Retrieve chunk
    retrieved = store.get_chunk(chunk_id)

    # Assert 1: Verify data is accessible
    assert retrieved is not None
    assert retrieved.text == "Hello, persistence!"
    assert retrieved.chunk_id == chunk_id

    # Verify count
    assert store.count() == 1

    # Act 3: Clear
    store.clear()
    assert store.count() == 0
