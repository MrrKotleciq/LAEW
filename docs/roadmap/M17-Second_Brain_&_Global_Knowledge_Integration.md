---
type: roadmap
id: M17
title: Second Brain & Global Knowledge Integration
status: completed
purpose: Make the Obsidian vault a real, curated knowledge source (ADR-002) with structured organization, link-aware chunking, and proper scope separation between @project and @knowledge.
read_when:
  - implementing Obsidian vault integration
  - Milestone 17 (Second Brain & Global Knowledge Integration)
---

### Milestone 17: Second Brain & Global Knowledge Integration
**Goal:** Make the Obsidian vault a real, curated knowledge source (ADR-002).
**Scope:** Stand up the `knowledge/` vault configured in the manifest; ingest and index the global vault into `@knowledge` RAG with structured organization (Knowledge, Decisions, Research, Templates) rather than a dumping ground; enforce project-specific docs stay in-repo, cross-project knowledge in the vault (ADR-011); link-aware chunking to preserve Obsidian backlinks.
**Dependencies:** None functional; Milestone 14 for retrieval latency.
**Tests:** Vault ingestion, scope separation (`@project` vs `@knowledge`), link preservation, source attribution in retrieved context.
**Definition of Done:** A populated Obsidian vault is indexed and retrievable as `@knowledge` context with correct scoping and sources.