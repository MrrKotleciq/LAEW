"""LAEW RAG (Retrieval-Augmented Generation) system."""

from importlib import import_module

_EXPORTS = {
    'EmbeddingService': 'embedding', 'OllamaEmbedding': 'embedding',
    'LlamaCppEmbedding': 'llamacpp', 'VectorStore': 'vector_store',
    'ChromaVectorStore': 'vector_store', 'DocumentChunk': 'vector_store',
    'KnowledgeBase': 'knowledge_base', 'KnowledgeScope': 'knowledge_base',
    'RAGPipeline': 'pipeline', 'RAGResult': 'pipeline',
}

__all__ = [
    "EmbeddingService",
    "OllamaEmbedding",
    "LlamaCppEmbedding",
    "VectorStore",
    "ChromaVectorStore",
    "DocumentChunk",
    "KnowledgeBase",
    "KnowledgeScope",
    "RAGPipeline",
    "RAGResult",
]


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(name)
    return getattr(import_module(f'{__name__}.{_EXPORTS[name]}'), name)
