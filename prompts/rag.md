# LAEW RAG & Context Retrieval Instructions

## 1. Purpose
Guide knowledge base query generation, vector retrieval filtering, context reranking, and evidence synthesis within the LAEW RAG subsystem.

---

## 2. Core Operational Rules
1. **Intelligent Library Model**: Treat RAG as a precision retrieval engine, not a bulk document dump.
2. **Context Budget Enforcement**: Restrict injected retrieval context strictly within the configured budget (max ~8,000 tokens).
3. **Relevance & Reranking**: Prioritize dense, highly specific chunks over broad introductory sections. Discard low-relevance results.
4. **Mandatory Source Attribution**: Every synthesized claim derived from RAG MUST cite the exact source document and section.
5. **Handling Absence & Conflicts**:
   - If retrieved chunks do not answer the prompt, explicitly state that knowledge is absent.
   - If retrieved documents conflict with current repository code, prioritize the repository state and highlight the discrepancy.

---

## 3. Query & Synthesis Workflow
1. **Query Decomposition**: Break complex engineering prompts into targeted semantic search queries.
2. **Retrieve & Filter**: Fetch top candidates from vector storage and apply similarity thresholds.
3. **Rerank & Prune**: Select the top-k highest scoring chunks fitting within the token budget.
4. **Synthesize**: Answer the query relying strictly on the retrieved context combined with ground truth repository state.

---

## 4. Retrieval Scoping (ADR-011)

RAG must not treat the entire workspace as one undifferentiated knowledge base. Queries must be explicitly scoped:

1. **`project_scoped`**: Search within the current project repository (`@project`). Use for implementation tasks, debugging, architecture review, and project-specific questions.
2. **`global_scoped`**: Search within the global Obsidian knowledge vault (`@knowledge`). Use for cross-project domain knowledge, research notes, hardware specifications, and general engineering concepts.
3. **`hybrid_scoped`**: Combine results from both project memory and global knowledge. Use when a task requires domain patterns applied to local project state.

All synthesized claims must cite their provenance (`Project Memory` or `Global Knowledge`).
