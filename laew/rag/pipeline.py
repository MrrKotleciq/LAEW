"""Main RAG pipeline orchestrating retrieval, reranking, and context injection."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from laew.rag.embedding import EmbeddingService
from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
from laew.rag.vector_store import DocumentChunk, VectorStore


@dataclass
class RAGResult:
    """
    Result from RAG pipeline execution.

    Attributes:
        chunks: Retrieved document chunks with scores
        context: Assembled context string
        total_tokens: Estimated token count
        sources: List of source file paths
        scope: Knowledge scope used
        query: Original query
    """

    chunks: List[Tuple[DocumentChunk, float]] = field(default_factory=list)
    context: str = ""
    total_tokens: int = 0
    sources: List[str] = field(default_factory=list)
    scope: KnowledgeScope = KnowledgeScope.PROJECT
    query: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "context": self.context,
            "total_tokens": self.total_tokens,
            "sources": self.sources,
            "scope": self.scope.value,
            "chunk_count": len(self.chunks),
        }


class RAGPipeline:
    """
    RAG pipeline implementing multi-stage retrieval and reranking.

    Pipeline flow per ADR-003:
    1. Generate query embedding
    2. Retrieve candidate chunks from vector store
    3. Apply reranking based on similarity scores
    4. Build context within token budget
    5. Return attributed results
    """

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        embedding_service: EmbeddingService,
        max_context_tokens: int = 8000,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
    ):
        """
        Initialize RAG pipeline.

        Args:
            knowledge_base: Knowledge base with loaded documents
            embedding_service: Service for generating embeddings
            max_context_tokens: Maximum tokens for context (from manifest)
            top_k: Number of top results to return
            similarity_threshold: Minimum similarity score to include
        """
        self.knowledge_base = knowledge_base
        self.embedding_service = embedding_service
        self.max_context_tokens = max_context_tokens
        self.top_k = top_k
        self.similarity_threshold = similarity_threshold

    def retrieve(
        self,
        query: str,
        scope: KnowledgeScope = KnowledgeScope.PROJECT,
        top_k: Optional[int] = None,
    ) -> RAGResult:
        """
        Execute RAG pipeline for a query.

        Args:
            query: User query string
            scope: Knowledge retrieval scope
            top_k: Override default top_k

        Returns:
            RAGResult with retrieved chunks and assembled context
        """
        # Load knowledge if not already loaded
        self.knowledge_base.load()

        # Generate query embedding
        try:
            query_embedding = self.embedding_service.embed(query)
        except Exception as e:
            return RAGResult(
                context="",
                total_tokens=0,
                sources=[],
                scope=scope,
                query=query,
            )

        # Retrieve candidates based on scope
        candidates = self._retrieve_candidates(query_embedding, scope, top_k or self.top_k)

        # Rerank and filter
        reranked = self._rerank(candidates)

        # Build context within token budget
        context, used_chunks, total_tokens = self._build_context(reranked)

        # Collect unique sources
        sources = list(set(chunk.file_path for chunk, _ in used_chunks))

        return RAGResult(
            chunks=used_chunks,
            context=context,
            total_tokens=total_tokens,
            sources=sources,
            scope=scope,
            query=query,
        )

    def _retrieve_candidates(
        self,
        query_embedding: List[float],
        scope: KnowledgeScope,
        top_k: int,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Retrieve candidate chunks from appropriate vector store(s).

        Args:
            query_embedding: Query vector
            scope: Knowledge scope
            top_k: Number of candidates to retrieve

        Returns:
            List of (chunk, score) tuples
        """
        candidates = []

        if scope == KnowledgeScope.PROJECT:
            candidates = self.knowledge_base.project_store.search(
                query_embedding, top_k=top_k
            )
        elif scope == KnowledgeScope.GLOBAL:
            candidates = self.knowledge_base.global_store.search(
                query_embedding, top_k=top_k
            )
        else:
            # Hybrid: search both stores and merge
            project_results = self.knowledge_base.project_store.search(
                query_embedding, top_k=top_k
            )
            global_results = self.knowledge_base.global_store.search(
                query_embedding, top_k=top_k
            )
            candidates = project_results + global_results

        return candidates

    def _rerank(
        self,
        candidates: List[Tuple[DocumentChunk, float]],
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Rerank candidates based on similarity scores.

        Args:
            candidates: Raw candidate chunks

        Returns:
            Reranked and filtered chunks
        """
        # Filter by similarity threshold
        filtered = [
            (chunk, score)
            for chunk, score in candidates
            if score >= self.similarity_threshold
        ]

        # Sort by score (highest first)
        reranked = sorted(filtered, key=lambda x: x[1], reverse=True)

        return reranked

    def _build_context(
        self,
        chunks: List[Tuple[DocumentChunk, float]],
    ) -> Tuple[str, List[Tuple[DocumentChunk, float]], int]:
        """
        Build context string within token budget.

        Args:
            chunks: Reranked chunks with scores

        Returns:
            Tuple of (context_string, used_chunks, total_tokens)
        """
        context_parts = []
        used_chunks = []
        total_tokens = 0

        # Estimate tokens per character (~4 chars per token)
        CHARS_PER_TOKEN = 4

        for chunk, score in chunks:
            # Estimate tokens for this chunk
            chunk_tokens = len(chunk.text) // CHARS_PER_TOKEN + 1

            # Check if adding this chunk would exceed budget
            if total_tokens + chunk_tokens > self.max_context_tokens:
                # Try to fit a partial chunk if we haven't added any yet
                if not used_chunks:
                    # Calculate how much we can fit
                    remaining_chars = (self.max_context_tokens - total_tokens) * CHARS_PER_TOKEN
                    if remaining_chars > 100:
                        partial_text = chunk.text[:remaining_chars]
                        context_parts.append(
                            f"[{chunk.source.upper()}: {chunk.file_path}]\n{partial_text}..."
                        )
                        used_chunks.append((chunk, score))
                        total_tokens += remaining_chars // CHARS_PER_TOKEN
                break

            # Add chunk with source attribution
            header = chunk.metadata.get("section_header", "")
            header_str = f" > {header}" if header else ""
            attribution = f"[{chunk.source.upper()}: {chunk.file_path}{header_str}]"

            context_parts.append(f"{attribution}\n{chunk.text}")
            used_chunks.append((chunk, score))
            total_tokens += chunk_tokens

        context = "\n\n---\n\n".join(context_parts)
        return context, used_chunks, total_tokens

    def get_stats(self) -> Dict[str, Any]:
        """
        Get pipeline statistics.

        Returns:
            Dictionary with pipeline stats
        """
        return {
            "project_chunks": self.knowledge_base.project_store.count(),
            "global_chunks": self.knowledge_base.global_store.count(),
            "max_context_tokens": self.max_context_tokens,
            "top_k": self.top_k,
            "similarity_threshold": self.similarity_threshold,
        }
