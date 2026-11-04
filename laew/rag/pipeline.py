"""Main RAG pipeline orchestrating retrieval, reranking, and context injection."""

import logging
import math
from hashlib import sha256
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from laew.config.constants import CHARS_PER_TOKEN_DEFAULT, RAG_MAX_CONTEXT_TOKENS
from laew.rag.embedding import EmbeddingService, embedding_model_identity
from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
from laew.rag.vector_store import DocumentChunk, VectorStore


logger = logging.getLogger("laew.rag.pipeline")


def fragment_key(chunk: DocumentChunk) -> tuple[str, str, str, bytes]:
    """Identify an exact excerpt without retaining its text in turn state."""
    return (chunk.source, chunk.file_path, chunk.chunk_id,
            sha256(chunk.text.encode("utf-8")).digest())


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
        error: Optional error message if pipeline failed (e.g., embedding error)
    """

    chunks: List[Tuple[DocumentChunk, float]] = field(default_factory=list)
    context: str = ""
    total_tokens: int = 0
    sources: List[str] = field(default_factory=list)
    scope: KnowledgeScope = KnowledgeScope.PROJECT
    query: str = ""
    error: Optional[str] = None
    duplicates_omitted: int = 0
    candidates: Optional[int] = None
    budget_omitted: int = 0
    fragments: list[dict[str, Any]] = field(default_factory=list)
    retrieved_sources: list[str] = field(default_factory=list)
    index_status: Optional[str] = None

    def source_metadata(self) -> List[Dict[str, Any]]:
        """Expose note properties separately from the budgeted context."""
        notes = {}
        for chunk, _ in self.chunks:
            alias = "@knowledge" if chunk.source == "global" else "@project"
            path = chunk.file_path.replace(chr(92), "/")
            source = f"{alias}/{path}" if path else alias
            if source not in notes:
                notes[source] = {"source": source,
                                 "frontmatter": chunk.metadata.get("frontmatter", {}),
                                 "backlinks": chunk.metadata.get("backlinks", [])}
        return list(notes.values())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        result = {
            "context": self.context,
            "total_tokens": self.total_tokens,
            "token_count_is_estimated": True,
            "source_metadata": self.source_metadata(),
            "sources": self.sources,
            "scope": self.scope.value,
            "chunk_count": len(self.chunks),
        }
        if self.error:
            result["error"] = self.error
        return result


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
        max_context_tokens: int = RAG_MAX_CONTEXT_TOKENS,
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

    def retrieve(self, query: str, scope: KnowledgeScope = KnowledgeScope.PROJECT,
                 top_k: Optional[int] = None, *, max_context_tokens: Optional[int] = None,
                 exclude_fragments: frozenset = frozenset()) -> RAGResult:
        """Retrieve under the same scope locks used by synchronization."""
        locks = []
        if getattr(self, "require_freshness", False):
            from laew.rag.sync import acquire_fresh_scopes
            scopes = ("project", "global") if scope == KnowledgeScope.HYBRID else (scope.value,)
            locks, error = acquire_fresh_scopes(self.knowledge_base, scopes)
            if error:
                return RAGResult(context="", total_tokens=0, sources=[], scope=scope,
                                 query=query, error=error, index_status="freshness_check_failed")
        try:
            if locks:
                try:
                    for requested_scope in scopes:
                        self.knowledge_base.ensure_store(requested_scope)
                except Exception:
                    return RAGResult(context="", total_tokens=0, sources=[], scope=scope,
                                     query=query, index_status="unavailable",
                                     error="Persistent knowledge store is unavailable. Check ChromaDB and retry synchronization.")
            result = self._retrieve(query, scope, top_k, max_context_tokens, exclude_fragments)
            if locks:
                result.index_status = "freshness_verified"
            return result
        finally:
            for lock in reversed(locks):
                lock.release()

    def _retrieve(
        self,
        query: str,
        scope: KnowledgeScope = KnowledgeScope.PROJECT,
        top_k: Optional[int] = None,
        max_context_tokens: Optional[int] = None,
        exclude_fragments: frozenset = frozenset(),
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
        # Load only the requested source where possible. Global retrieval must
        # never depend on (or index) project memory, and vice versa.
        current_model_id = embedding_model_identity(self.embedding_service)
        if current_model_id != self.knowledge_base.embedding_model_id:
            return RAGResult(
                context="",
                total_tokens=0,
                sources=[],
                scope=scope,
                query=query,
                error=(
                    "Embedding model configuration changed after indexing; "
                    "rebuild the knowledge index before retrieval."
                ),
            )
        try:
            if scope == KnowledgeScope.PROJECT:
                self.knowledge_base.load_project()
            elif scope == KnowledgeScope.GLOBAL:
                self.knowledge_base.load_vault()
            else:
                self.knowledge_base.load_project()
                self.knowledge_base.load_vault()
        except Exception as e:
            logger.error("Knowledge source loading failed: %s", e, exc_info=True)
            return RAGResult(
                context="",
                total_tokens=0,
                sources=[],
                scope=scope,
                query=query,
                error=f"Knowledge source unavailable: {e}",
            )

        # Generate query embedding
        try:
            query_embedding = self.embedding_service.embed(query)
        except Exception as e:
            # Fail visibly instead of silently returning empty context: log the
            # failure and record it on the result so callers can distinguish
            # "no relevant information" from "retrieval is broken" (H5).
            logger.error("Query embedding failed: %s", e, exc_info=True)
            return RAGResult(
                context="",
                total_tokens=0,
                sources=[],
                scope=scope,
                query=query,
                error=str(e),
            )

        # Retrieve candidates based on scope
        candidates = self._retrieve_candidates(query_embedding, scope, top_k or self.top_k)

        # Rerank and filter
        reranked = self._rerank(candidates)

        unique = []
        seen = set(exclude_fragments)
        for chunk, score in reranked:
            key = fragment_key(chunk)
            if key not in seen:
                unique.append((chunk, score))
                seen.add(key)
        context, used_chunks, total_tokens = self._build_context(unique, max_context_tokens)

        # Return stable, logical-root paths so provenance remains meaningful
        # when the runtime serves more than one project.
        def logical_path(chunk):
            alias = "@knowledge" if chunk.source == "global" else "@project"
            relative_path = chunk.file_path.replace("\\", "/")
            return f"{alias}/{relative_path}" if relative_path else alias

        sources = list(dict.fromkeys(logical_path(chunk) for chunk, _ in used_chunks))
        original_text = {(chunk.source, chunk.file_path, chunk.chunk_id): chunk.text for chunk, _ in unique}
        return RAGResult(
            chunks=used_chunks,
            duplicates_omitted=len(reranked) - len(unique),
            candidates=len(candidates),
            budget_omitted=len(unique) - len(used_chunks),
            retrieved_sources=list(dict.fromkeys(logical_path(chunk) for chunk, _ in reranked))[:50],
            fragments=[
                {"id": chunk.chunk_id, "path": logical_path(chunk),
                 "truncated": chunk.text != original_text[(chunk.source, chunk.file_path, chunk.chunk_id)]}
                for chunk, _ in used_chunks
            ],
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
        max_context_tokens: Optional[int] = None,
    ) -> Tuple[str, List[Tuple[DocumentChunk, float]], int]:
        """
        Build context string within token budget.

        Args:
            chunks: Reranked chunks with scores

        Returns:
            Tuple of (context_string, used_chunks, total_tokens)
        """
        separator = "\n\n---\n\n"
        limit = self.max_context_tokens
        if max_context_tokens is not None:
            limit = min(limit, max_context_tokens)
        char_limit = max(0, int(limit * CHARS_PER_TOKEN_DEFAULT))
        parts = []
        used_chunks = []
        remaining = char_limit

        for chunk, score in chunks:
            header = chunk.metadata.get("section_header")
            tags = chunk.metadata.get("tags") or []
            backlinks = chunk.metadata.get("backlinks") or []
            frontmatter = chunk.metadata.get("frontmatter") or {}
            provenance = "GLOBAL KNOWLEDGE @knowledge" if chunk.source == "global" else "PROJECT MEMORY @project"
            labels = [f"{provenance}: {chunk.file_path}"]
            if header:
                labels.append(str(header))
            if tags:
                labels.append(", ".join(tags))
            if backlinks:
                labels.append("backlinks: " + ", ".join(backlinks))
            for key in ("type", "status"):
                if frontmatter.get(key):
                    labels.append(f"{key}: {frontmatter[key]}")
            attribution = "[" + " > ".join(labels) + "]\n"
            overhead = len(attribution) + (len(separator) if parts else 0)
            available = remaining - overhead
            if available <= 0 or not chunk.text:
                continue
            if len(chunk.text) > available:
                if parts or available <= 3:
                    continue
                excerpt = chunk.text[:available - 3]
                parts.append(attribution + excerpt + "...")
                used_chunks.append((replace(chunk, text=excerpt), score))
                break
            parts.append(attribution + chunk.text)
            used_chunks.append((chunk, score))
            remaining -= overhead + len(chunk.text)

        context = separator.join(parts)
        return context, used_chunks, math.ceil(len(context) / CHARS_PER_TOKEN_DEFAULT)

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
