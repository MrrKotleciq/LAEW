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

## Deferred M18 work

### Windows Backup Worker BW-07/BW-08

**Deferred due to insufficient RAM for Windows VM testing.** The Hyper-V guest booted with 4 GiB, but Windows Setup ran out of memory applying the image. Offline deployment reached first boot before the operator stopped the attempt. The guest, disks and ISO were removed. Qualification of unattended Windows operation remains open. [M18 qualification report](../reports/M18_BW08_QUALIFICATION_20261125.md#windows-follow-up)

**Resume when** an approved disposable Windows Hyper-V guest can be provisioned from verified installation media on a host with enough available RAM to complete setup and run the fixture with headroom. Confirm the guest can boot, reboot and run the tests with synthetic sources and a loopback SFTP endpoint. Use separate writer, worker, Core reader and legacy fixture identities. [M18 implementation plan](../reports/M18_BACKUP_WORKER_IMPLEMENTATION_PLAN_20261124.md)

- **BW-07 managed service adapter and writer exclusion.** Implement the fixed Windows service roster and protected restart gate. Prove containment before the first write, graceful shutdown, complete descendant exit and denial of unmanaged writes and restarts throughout capture. Refuse capture when the roster or exclusion cannot be established.
- **BW-07 OpenSSH and permission boundaries.** Implement the Windows trust adapter for the system OpenSSH client. Qualify the dedicated worker key under its noninteractive token while logged out and after reboot. Verify strict pinning, rejection of unavailable credentials and isolated recovery from the replicated copy. Confirm the Core reader can read status and settings projections but cannot modify, delete or replace them or their ancestors, or access private settings, keys or archives.
- **BW-08 scheduled capture and recovery.** Exercise the actual guest task in its noninteractive logon mode. Cover late and concurrent starts, stale or replayed cuts, reboot, and worker or controller crash. Require a terminal worker before explicit recovery resumes the originally active writers.
- **BW-08 power-loss publication safety.** Cut guest power around archive and receipt publication, then independently verify visible generations, reject incomplete generations and confirm the prior verified copy survives. Keep the writer gate closed on ambiguous state.
- **BW-08 legacy exclusion and final regression.** Verify that the retired 0.1.0 executable and account cannot create or modify managed media. Close managed admission before supervised rollback and verify archive compatibility and preservation. Rerun the full offline regression against the final Windows candidate and record the qualification evidence.

### ChromaDB HNSW reload after cache eviction

**Accepted external dependency limitation for M18 publication.** ChromaDB 1.5.9 can fail to reload a small, unsynchronized HNSW segment after cache eviction. The standalone Windows reproducer failed in 2 of 192 two-collection trials and in 75 of 134 reads after exceeding the default cache capacity. The full LAEW regression also recorded one RAG failure and found the same unpersisted segment state. Keep 1.5.9 and retain the existing tests and assertions. [ChromaDB issue #7946](https://github.com/chroma-core/chroma/issues/7946) · [Upstream live-index change #7765](https://github.com/chroma-core/chroma/pull/7765) · [M18 reproduction and regression evidence](../reports/M18_BW08_QUALIFICATION_20261125.md#chromadb-lifecycle-investigation)

**Resume when** a future stable ChromaDB release contains the relevant HNSW changes. With separate approval, qualify that release on Windows against the default-settings two-collection and cache-pressure reproducers, then run the unchanged recovery tests and full offline regression before adopting it. Use stable releases for qualification.
