---
type: roadmap
id: M17
title: Second Brain & Global Knowledge Integration
name: Second Brain & Global Knowledge Integration
description: Make the Obsidian vault a real, curated knowledge source (ADR-002) with structured organization, link-aware chunking, and proper scope separation between @project and @knowledge.
scope: project
tags:
  - knowledge
  - obsidian
  - second-brain
  - global-knowledge
status: in-progress
purpose: Make the Obsidian vault a real, curated knowledge source (ADR-002) with structured organization, link-aware chunking, and proper scope separation between @project and @knowledge.
read_when:
  - implementing Obsidian vault integration
  - Milestone 17 (Second Brain & Global Knowledge Integration)
implements:
  - ADR-002
---

### Milestone 17: Second Brain & Global Knowledge Integration
**Goal:** Make the Obsidian vault a real, curated knowledge source (ADR-002).
**Scope:** Stand up the `knowledge/` vault configured in the manifest; ingest and index the global vault into `@knowledge` RAG with structured organization (Knowledge, Decisions, Research, Templates) rather than a dumping ground; enforce project-specific docs stay in-repo, cross-project knowledge in the vault (ADR-011); link-aware chunking to preserve Obsidian backlinks.
**Dependencies:** None functional; Milestone 14 for retrieval latency.
**Tests:** Vault ingestion, scope separation (`@project` vs `@knowledge`), link preservation, source attribution in retrieved context.
**Definition of Done:** A populated Obsidian vault is indexed and retrievable as `@knowledge` context with correct scoping and sources.

### Implementation Status — 2026-10-26

- The Obsidian parser, link-aware chunk metadata, scoped stores, reranking, and budgeted source attribution are implemented in `laew/rag/`.
- The Chief Agent runtime now registers the read-only `RagTool`; project and global roots are resolved through the trusted workspace aliases, and project/global retrieval loads only the requested source (or both for hybrid scope).
- The manifest points the Second Brain path to `@knowledge`. Console vault inspection and RAG commands resolve that alias and reject paths outside the trusted vault.
- Automated verification covers fixture ingestion, source separation, alias/traversal validation, embedding failures, and retrieval through the actual `AgentExecutor` tool loop.
- `C:\\ROOT\\Projects\\LAEW\\Knowledge` is LAEW-local content indexed under `@project`; `C:\\ROOT\\Knowledge` is the global vault resolved by `@knowledge`.
- Embeddings use the OpenAI-compatible llama.cpp `/v1/embeddings` client on a separately configured server. Set `models.roles.embedding.model_name` to the ID exposed by that dedicated server; the repository does not select or assume an embedding model file.
- The global vault currently has no visible Markdown notes. The configured embedding endpoint/model could not be verified as available in this environment. Mocked retrieval tests pass, but live embedding and retrieval from populated global content remain unverified; M17 stays **in progress**.
