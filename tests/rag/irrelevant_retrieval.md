# Test Spec: RAG-02 — Irrelevant Document Filtering & Pruning

## 1. Test Metadata
- **ID**: `RAG-02`
- **Category**: `rag`
- **Component**: `RAG Subsystem`, `prompts/rag.md`
- **Target Policy**: Low-similarity threshold pruning and reranking

---

## 2. Scenario & Trigger
- **Preconditions**: Knowledge base contains vector embeddings for STM32 hardware and software design patterns.
- **Trigger Prompt**: "How do I configure FreeRTOS task priorities on STM32?"
- **Simulated Noise**: Vector search returns low-confidence matches about Python asynchronous event loops alongside embedded documents.

---

## 3. Assertions

### Pass Criteria
1. The reranking layer discards the irrelevant Python async documents.
2. Only STM32 / FreeRTOS relevant chunks are injected into the agent prompt context.
3. The response does not confuse Python concurrency models with embedded RTOS task scheduling.

### Fail Criteria
1. Irrelevant noise chunks consume context budget and lead to hallucinated or blended answers.
