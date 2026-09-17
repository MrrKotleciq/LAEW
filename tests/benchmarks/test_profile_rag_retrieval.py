"""Benchmark: in-memory ``VectorStore`` cosine retrieval over a synthetic corpus.

Offline baseline for the RAG hot path: index build + repeated top-k searches.
Embeddings are deterministic pseudo-random unit vectors so results are stable
across runs without any model dependency.

Tolerances are informational only — these tests record numbers for
``docs/performance/BASELINE.md``, they do not gate on wall clock.
"""

import math
import random
from typing import List

from laew.rag.vector_store import DocumentChunk, VectorStore

DIM = 256        # embedding dimension
CORPUS_SIZE = 500  # synthetic chunks indexed per benchmark


def _unit_vector(seed: int, dim: int) -> List[float]:
    """Deterministic pseudo-random unit vector for a given seed."""
    rng = random.Random(seed)
    vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _build_store(size: int) -> VectorStore:
    """Index ``size`` synthetic chunks with deterministic embeddings."""
    store = VectorStore()
    store.add_chunks(
        [
            DocumentChunk(
                chunk_id=f"c{i:04d}",
                text=f"Synthetic project documentation chunk number {i}.",
                embedding=_unit_vector(i, DIM),
                source="project",
                file_path=f"docs/chunk-{i}.md",
            )
            for i in range(size)
        ]
    )
    return store


def test_profile_rag_index_build(benchmark):
    """Wall clock of building the index over the synthetic corpus."""
    def build():
        store = VectorStore()
        store.add_chunks(
            [
                DocumentChunk(
                    chunk_id=f"b{i:04d}",
                    text=f"Build corpus document chunk {i}.",
                    embedding=_unit_vector(i, DIM),
                    source="project",
                )
                for i in range(CORPUS_SIZE)
            ]
        )
        return store

    store = benchmark(build)
    assert store.count() == CORPUS_SIZE


def test_profile_rag_topk_search(benchmark):
    """Wall clock of a single top-5 cosine search against the corpus."""
    store = _build_store(CORPUS_SIZE)
    query = _unit_vector(CORPUS_SIZE + 1, DIM)

    results = benchmark(lambda: store.search(query, top_k=5))
    assert 1 <= len(results) <= 5


def test_profile_rag_ten_searches(benchmark):
    """Wall clock of ten sequential searches (typical retrieval batch)."""
    store = _build_store(CORPUS_SIZE)
    queries = [_unit_vector(CORPUS_SIZE + 1 + i, DIM) for i in range(10)]

    def batch():
        for q in queries:
            store.search(q, top_k=5)

    benchmark(batch)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])