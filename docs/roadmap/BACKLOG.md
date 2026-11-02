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

- Academic RAG metadata filters (semester, subject, topic): current frontmatter fields remain file metadata, not query filters.
- PDF/text extraction with page provenance; OCR and multimodal retrieval need separate design and validation. Current ingestion is Markdown-only.
- Budgeted, approved Core User Context integration; retain detailed profile retrieval on demand and explicitly design privacy if a private scope is needed.
- Resolve runtime tool-contract hints independently of optional project content layouts, without requiring academic projects to copy LAEW's tools directory.

- Cloud-provider integration beyond routing (full OpenAI/Anthropic provider builders in the ADR-019 registry).
- Agent memory with learned, persistent cross-session knowledge (distinct from filesystem current-state, ADR-012).
- Semantics-aware RAG reranking upgrades beyond cosine similarity (nested/colBERT-style). Evaluate broad Polish ownership paraphrases against the production false negative recorded in [M17 verification](M17-Knowledge-Preparation-2026-10-29.md); focused topic retrieval already passes.
- Interactive plan editor / workflow authoring UI.
- Multi-agent autonomous mode with manual and disabled fallbacks (ADR-015) fully exercised.
