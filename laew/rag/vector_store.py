"""In-memory vector store with similarity search."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class DocumentChunk:
    """
    A chunk of a document with its embedding and metadata.

    Attributes:
        chunk_id: Unique identifier for this chunk
        text: The text content of the chunk
        embedding: Vector embedding of the text
        source: Source type (project or global)
        file_path: Path to the source file
        metadata: Additional metadata (section header, etc.)
    """

    chunk_id: str
    text: str
    embedding: Optional[List[float]] = None
    source: str = "project"  # "project" or "global"
    file_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "source": self.source,
            "file_path": self.file_path,
            "metadata": self.metadata,
        }


class VectorStore:
    """
    In-memory vector store using numpy for cosine similarity.

    Stores document chunks with their embeddings and provides
    similarity search functionality.
    """

    def __init__(self):
        """Initialize empty vector store."""
        self._chunks: Dict[str, DocumentChunk] = {}
        self._embedding_matrix: Optional[np.ndarray] = None
        self._chunk_ids: List[str] = []

    def add_chunk(self, chunk: DocumentChunk) -> None:
        """
        Add a document chunk to the store.

        Args:
            chunk: DocumentChunk to add
        """
        if chunk.embedding is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        self._chunks[chunk.chunk_id] = chunk
        self._rebuild_index()

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Add multiple chunks to the store.

        Args:
            chunks: List of DocumentChunks to add
        """
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")
            self._chunks[chunk.chunk_id] = chunk

        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the embedding matrix index."""
        if not self._chunks:
            self._embedding_matrix = None
            self._chunk_ids = []
            return

        self._chunk_ids = list(self._chunks.keys())
        embeddings = [self._chunks[cid].embedding for cid in self._chunk_ids]
        self._embedding_matrix = np.array(embeddings, dtype=np.float32)

        # Normalize for cosine similarity
        norms = np.linalg.norm(self._embedding_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        self._embedding_matrix = self._embedding_matrix / norms

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        source_filter: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks using cosine similarity.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            source_filter: Optional filter by source ("project" or "global")

        Returns:
            List of (chunk, similarity_score) tuples
        """
        if self._embedding_matrix is None or len(self._chunk_ids) == 0:
            return []

        # Normalize query vector
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec = query_vec / query_norm

        # Compute cosine similarities
        similarities = np.dot(self._embedding_matrix, query_vec)

        # Filter by source if specified
        if source_filter:
            filtered_indices = [
                i
                for i, cid in enumerate(self._chunk_ids)
                if self._chunks[cid].source == source_filter
            ]
            if not filtered_indices:
                return []
            similarities = similarities[filtered_indices]
            chunk_ids = [self._chunk_ids[i] for i in filtered_indices]
        else:
            chunk_ids = self._chunk_ids

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            chunk_id = chunk_ids[idx]
            score = float(similarities[idx])
            results.append((self._chunks[chunk_id], score))

        return results

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        """
        Get a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            DocumentChunk or None if not found
        """
        return self._chunks.get(chunk_id)

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deleted, False if not found
        """
        if chunk_id in self._chunks:
            del self._chunks[chunk_id]
            self._rebuild_index()
            return True
        return False

    def clear(self) -> None:
        """Clear all chunks from the store."""
        self._chunks.clear()
        self._embedding_matrix = None
        self._chunk_ids = []

    def count(self, source: Optional[str] = None) -> int:
        """
        Count chunks in the store.

        Args:
            source: Optional source filter

        Returns:
            Number of chunks
        """
        if source is None:
            return len(self._chunks)
        return sum(1 for c in self._chunks.values() if c.source == source)


class ChromaVectorStore:
    """
    Persistent vector store backed by a remote ChromaDB instance.

    Mirrors the VectorStore interface (add_chunks, search, get_chunk, delete,
    clear, count) but persists data in a ChromaDB collection, typically hosted
    via Docker. Embeddings are normalized before storage so that ChromaDB's
    cosine distance maps to the same similarity measure used by VectorStore.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        collection_name: str = "laew_vectors",
        source: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize ChromaVectorStore.

        Args:
            host: ChromaDB server host
            port: ChromaDB server port
            collection_name: ChromaDB collection name
            source: Optional default source scope ("project" or "global")
            timeout: Connection timeout in seconds

        Raises:
            ValueError: If chromadb is not installed
            ConnectionError: If ChromaDB is unreachable
        """
        try:
            import chromadb
        except ImportError as e:
            raise ValueError(
                "chromadb is not installed. Install it with: pip install chromadb"
            ) from e

        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.source = source

        # Build the client, supporting both the modern HttpClient and the
        # settings-based client used by older chromadb versions.
        self._client = _build_chroma_client(chromadb, host, port, timeout)

        try:
            self._collection = self._client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to reach ChromaDB at {host}:{port}: {e}"
            ) from e

    def add_chunk(self, chunk: DocumentChunk) -> None:
        """
        Add a document chunk to the store.

        Args:
            chunk: DocumentChunk to add

        Raises:
            ValueError: If chunk has no embedding
        """
        if chunk.embedding is None:
            raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        embedding = self._normalize(chunk.embedding)
        metadata = {
            "text": chunk.text,
            "source": chunk.source,
            "file_path": chunk.file_path,
        }
        # Merge additional chunk metadata (JSON-serializable values only).
        for key, value in chunk.metadata.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                metadata[key] = str(value)
            else:
                metadata[key] = str(value)

        self._collection.add(
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[chunk.chunk_id],
        )

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        """
        Add multiple document chunks to the store.

        Args:
            chunks: List of DocumentChunks to add

        Raises:
            ValueError: If any chunk has no embedding
        """
        for chunk in chunks:
            if chunk.embedding is None:
                raise ValueError(f"Chunk {chunk.chunk_id} has no embedding")

        for chunk in chunks:
            self.add_chunk(chunk)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        source_filter: Optional[str] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Search for similar chunks using cosine distance.

        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            source_filter: Optional filter by source ("project" or "global")

        Returns:
            List of (chunk, similarity_score) tuples
        """
        normalized = self._normalize(query_embedding)

        if source_filter:
            try:
                results = self._collection.query(
                    query_embeddings=[normalized],
                    n_results=top_k,
                    where={"source": source_filter},
                )
            except Exception:
                results = self._collection.query(
                    query_embeddings=[normalized],
                    n_results=top_k,
                )
        else:
            results = self._collection.query(
                query_embeddings=[normalized],
                n_results=top_k,
            )

        stored_ids = results.get("ids", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        chunks = []
        for chunk_id, metadata, distance in zip(stored_ids, metadatas, distances):
            if metadata is None:
                continue
            similarity = 1.0 - float(distance) / 2.0
            chunk = DocumentChunk(
                chunk_id=chunk_id,
                text=metadata.get("text", ""),
                embedding=None,  # Do not reload embeddings on search
                source=metadata.get("source", self.source or "project"),
                file_path=metadata.get("file_path", ""),
                metadata={
                    k: v
                    for k, v in metadata.items()
                    if k not in ("text", "source", "file_path")
                },
            )
            chunks.append((chunk, similarity))

        return chunks

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        """
        Get a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            DocumentChunk or None if not found
        """
        try:
            result = self._collection.get(ids=[chunk_id])
        except Exception:
            return None

        if not result.get("ids"):
            return None

        metadata = result["metadatas"][0]
        return DocumentChunk(
            chunk_id=chunk_id,
            text=metadata.get("text", ""),
            embedding=None,
            source=metadata.get("source", self.source or "project"),
            file_path=metadata.get("file_path", ""),
            metadata={
                k: v
                for k, v in metadata.items()
                if k not in ("text", "source", "file_path")
            },
        )

    def delete_chunk(self, chunk_id: str) -> bool:
        """
        Delete a chunk by ID.

        Args:
            chunk_id: Chunk identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            result = self._collection.get(ids=[chunk_id])
            if not result.get("ids"):
                return False
            self._collection.delete(ids=[chunk_id])
            return True
        except Exception:
            return False

    def clear(self) -> None:
        """Clear all chunks from the store."""
        try:
            self._client.delete_collection(self.collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception:
            pass

    def count(self, source: Optional[str] = None) -> int:
        """
        Count chunks in the store.

        Args:
            source: Optional source filter

        Returns:
            Number of chunks
        """
        try:
            result = self._collection.get()
            if source:
                return sum(
                    1
                    for metadata in result.get("metadatas", [])
                    if metadata and metadata.get("source") == source
                )
            return len(result.get("ids", []))
        except Exception:
            return 0

    @staticmethod
    def _normalize(vector: List[float]) -> List[float]:
        """
        Normalize a vector to unit length for cosine search.

        Args:
            vector: Input vector

        Returns:
            Normalized vector
        """
        arr = np.array(vector, dtype=np.float32)
        norm = np.linalg.norm(arr)
        if norm == 0:
            return arr.tolist()
        return (arr / norm).tolist()


def _build_chroma_client(chromadb, host: str, port: int, timeout: int):
    """Build a ChromaDB client, supporting multiple version APIs."""
    for attrs in (
        ("HttpClient", None),
        ("Client", None),
    ):
        try:
            client_cls = getattr(chromadb, attrs[0])
        except AttributeError:
            continue
        try:
            if attrs[0] == "HttpClient":
                return client_cls(host=host, port=port)
            # Settings-based client
            from chromadb.config import Settings
            return client_cls(Settings(
                chroma_server_host=host,
                chroma_server_http_port=port,
            ))
        except TypeError:
            pass
    raise ConnectionError(
        f"Unable to create a ChromaDB client for {host}:{port}. "
        "Check that chromadb is installed and the server is running."
    )
