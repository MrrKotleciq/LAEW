# Test Spec: RAG-01 — Precision Retrieval & Synthesis

## 1. Test Metadata
- **ID**: `RAG-01`
- **Category**: `rag`
- **Component**: `RAG Subsystem`, `prompts/rag.md`
- **Target Policy**: Precise semantic retrieval within context budget (Principle P6)

---

## 2. Scenario & Trigger
- **Preconditions**: Knowledge base contains multiple documents across engineering domains.
- **Trigger Prompt**: "What are the rules for Obsidian Second Brain vault structuring in LAEW?"

---

## 3. Assertions

### Pass Criteria
1. RAG query isolates relevant sections from `docs/LAEW_CONTEXT.md` (specifically Section 4: Second Brain).
2. The agent synthesizes the response mentioning structured areas (Knowledge, Decisions, Research, Templates) and bi-directional linking.
3. Every factual statement includes source attribution (`docs/LAEW_CONTEXT.md`).
4. Total injected context remains strictly within the 8,000 token RAG budget.

### Fail Criteria
1. Entire document vault is dumped into the context window.
2. Injected context omits the relevant section or hallucinates unrelated note-taking philosophies.
