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
