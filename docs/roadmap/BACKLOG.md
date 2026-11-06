---
type: roadmap
id: backlog
title: Backlog
name: Backlog
description: List of candidate milestones not yet sequenced into the roadmap.
scope: project
tags:
  - backlog
  - candidates
status: backlog
purpose: List of candidate milestones not yet sequenced into the roadmap
read_when:
  - planning new work
  - evaluating feature candidates
---

## Future Candidates (not yet sequenced)

- **Memory-to-RAG Sufficiency Calibration:** reduce unnecessary fallback when memories suffice and measure missed-source risk. An opt-in model assessment and conservative fallback are implemented. The [isolated 24-case Ornith evaluation](../reports/MEMORY_SUFFICIENCY_ORNITH_20261106.md) recorded two source-routing misses and 14 invalid model responses in each configuration. Horizon remains advisory. Measure false-sufficient decisions, cost and latency on independently reviewed cases before production use.
- **Knowledge Routing follow-up** — the four known routing regressions are covered in the [offline comparison](../reports/KNOWLEDGE_ROUTING_RELIABILITY.md). The [Stage 2 intent evaluation](../retrieval-reliability-evaluation.md#stage-2-first-person-and-intent-routing) covers bilingual profile lookup, advice, and public and private dates on a separate fixture. Validate the same distinctions on independently reviewed traffic-like questions, especially ambiguous event ownership and technical how-tos. Track unnecessary Global searches from inconclusive Memory assessment separately from initial source selection.
- **Real-Model Retrieval Evaluation:** assess grounded answers, tool effectiveness and costs using real models.
- **Full Regression Environment Verification:** investigate previous WinError 10013 and intermittent isolated ChromaDB failures. The Stage 2B.2 full offline run reproduced `Error creating hnsw segment reader: Nothing found on disk` in the Chief scope test; isolated rerun passed, root cause remains unverified.
- **Advanced Conversation Awareness:** improve references to older topics and natural formulations.
- **No-Answer Retrieval Quality:** reduce irrelevant results when the index lacks an answer.
- **RAG Infrastructure Hardening:** pin ChromaDB versions, enforce timeouts, improve synchronization resilience and freshness monitoring.
- **Chief Agent Prompt Maintainability:** assess runtime prompt structure and unused `prompts/chief-agent.md` when later measurements justify refactoring.

- Academic RAG metadata filters (semester, subject, topic): current frontmatter fields remain file metadata, not query filters.
- PDF/text extraction with page provenance; OCR and multimodal retrieval need separate design and validation. Current ingestion is Markdown-only.
- Budgeted, approved Core User Context integration; retain detailed profile retrieval on demand and explicitly design privacy if a private scope is needed.
- Resolve runtime tool-contract hints independently of optional project content layouts, without requiring academic projects to copy LAEW's tools directory.

- Cloud-provider integration beyond routing (full OpenAI/Anthropic provider builders in the ADR-019 registry).
- Agent memory with learned, persistent cross-session knowledge (distinct from filesystem current-state, ADR-012).
- Semantics-aware RAG reranking upgrades beyond cosine similarity (nested/colBERT-style). Evaluate broad Polish ownership paraphrases against the production false negative recorded in [M17 verification](M17-Knowledge-Preparation-2026-10-29.md); focused topic retrieval already passes.
- Interactive plan editor / workflow authoring UI.
- Multi-agent autonomous mode with manual and disabled fallbacks (ADR-015) fully exercised.
