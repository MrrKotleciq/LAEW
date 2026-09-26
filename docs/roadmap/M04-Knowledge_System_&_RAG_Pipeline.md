## [2026-09-06] Milestone 4: Knowledge System & RAG Pipeline Completed

- **Context & Motivation**:
  Implement the persistent knowledge retrieval subsystem enabling project-scoped, global-scoped, and hybrid-scoped retrieval with vector embeddings, semantic search, cosine similarity reranking, and context injection respecting token budgets (ADR-002, ADR-003, ADR-011).
- **Key Achievements**:
  - Implemented `EmbeddingService` interface and `OllamaEmbedding` provider (`laew/rag/embedding.py`) supporting local embedding models (e.g. `nomic-embed-text:latest`).
  - Implemented in-memory `VectorStore` (`laew/rag/vector_store.py`) with cosine similarity search and scope-based filtering using numpy.
  - Implemented `KnowledgeBase` (`laew/rag/knowledge_base.py`) with automatic Markdown file discovery, section-aware splitting, chunking with overlap, and multi-scope separation (`@project` vs `@knowledge`).
  - Implemented `RAGPipeline` (`laew/rag/pipeline.py`) orchestrating candidate retrieval, similarity reranking, and context synthesis with source attribution within `max_context_tokens` budget.
  - Implemented `RagTool` (`laew/rag/rag_tool.py`) as an agent-callable tool for on-demand knowledge retrieval.
  - Updated `manifests/SYSTEM_MANIFEST.yaml` with explicit embedding model configuration (`nomic-embed-text:latest`, target dimension 768).
  - Created 20 unit and integration tests (`tests/unit/test_rag.py`) covering all RAG subsystem components.
- **Decisions & Consequences**:
  - Preserved clear separation between project memory (`@project`) and global Obsidian vault knowledge (`@knowledge`) per ADR-011.
  - Enforced structured source attribution (`[SOURCE: file_path > section_header]`) on all retrieved context.
  - Adhered to strict context budgeting constraints per ADR-004 during context assembly.