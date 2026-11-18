---
name: Documentation Index
description: Navigation entry point to LAEW's architecture, decisions, roadmap, history, performance, security, and source material.
type: index
title: Documentation
scope: project
status: active
read_when:
  - navigating the documentation tree
  - understanding the project structure
---

# LAEW Documentation

This directory contains the project's architecture, decisions, status, history, roadmap, performance data, security reviews, and reference material.

Start here before searching the documentation tree.

## Documentation Map

| Area | Path | Purpose |
|---|---|---|
| Project Context | `LAEW_CONTEXT.md` | Concise project scope, goals, and constraints |
| Project Status | `PROJECT_STATUS.md` | Current implemented state |
| Architecture | `architecture/` | Current architectural intent and principles |
| Decisions | `decisions/` | Recorded Architecture Decision Records |
| Roadmap | `roadmap/` | Planned milestones and future work |
| History | `history/` | Chronological development history |
| Performance | `performance/` | Measurements, benchmarks, and baselines |
| Security | `security/` | Security reviews and findings |
| Source | `source/` | Reference/source material |

## Source-of-Truth Hierarchy

1. Current source code and tests describe implemented behavior.
2. Accepted ADRs describe recorded architectural decisions.
3. `PROJECT_STATUS.md` summarizes current project state.
4. `LAEW_CONTEXT.md` defines project scope and high-level context.
5. `roadmap/` describes planned work.
6. `history/` records historical events.
7. `source/` contains reference material.

Plans and documentation must not be assumed to describe implemented behavior without verification.

## Navigation Rules

- Read this file first when the relevant documentation location is unknown.
- Search for relevant documents before reading large files.
- Read only the documents required for the current task.
- Use document metadata to determine relevance.
- Prefer a specific ADR or milestone document over scanning an entire directory.

## Common Queries

### Architecture

- [Long-Term Memory](architecture/LONG_TERM_MEMORY.md): SQLite, semantic index, extraction, recall, Settings and recovery.
- [Global Knowledge Curation](architecture/GLOBAL_KNOWLEDGE_CURATION.md)
- [Global RAG and Ingestion Audit](reports/GLOBAL_RAG_AUDIT.md)
- [Global RAG Correctness and Retrieval Baseline](reports/GLOBAL_RAG_BASELINE.md)
- [Knowledge Source Routing and Automatic RAG Activation](reports/KNOWLEDGE_SOURCE_ROUTING.md)
Start with `architecture/` and `decisions/`.

### Current implementation
Start with `PROJECT_STATUS.md`, then inspect source code and tests.

### Planned work
Start with `roadmap/`.

### Historical investigation
Start with `history/`.

### Security
Start with `security/` and relevant ADRs.

### Performance
Start with `performance/`.

- [Stage 2B.2 adaptive evidence selection](reports/STAGE_2B2_ADAPTIVE_EVIDENCE_SELECTION_20261110.md): isolated model-free selectors, context cost, regression and scaling evaluation; production unchanged.
- [Stage 2B.2 lexical retrieval — Task 1](reports/STAGE_2B2_LEXICAL_RETRIEVAL_20261110.md): FTS5/BM25S versus dense candidates, synchronization costs and backend recommendation; no hybrid integration.
- [Stage 2B.2 hybrid retrieval with RRF — Task 2](reports/STAGE_2B2_HYBRID_RRF_20261110.md): fair candidate limits, ranked_fill, regressions and latency; dense-only retained pending Task 3 review.
- [Stage 2B.2 advanced dense retrieval review — Task 3A](reports/STAGE_2B2_ADVANCED_DENSE_REVIEW_20261111.md): s14 diagnosis, established structural retrieval methods and proposed isolated Task 3B; no retrieval implementation.
- [Stage 2B.2 hierarchical dense retrieval — Task 3B](reports/STAGE_2B2_HIERARCHICAL_DENSE_20261111.md): fixed three-document drill-down, actual Chroma filtering, grouped stress control, regressions and resource cost; revise before rollout.
- [Stage 2B.2 real-world dataset and retrieval comparison](reports/STAGE_2B2_REAL_WORLD_DATASET_AND_RETRIEVAL_20261113.md): frozen pilot/sealed drafts, isolated A/B/C results, source restrictions and outstanding human review; no answer generation or production deployment.
- [Stage 2B.2 post-result evidence audit](reports/STAGE_2B2_EVIDENCE_AUDIT_20261114.md): all 20 families, original versus diagnostic metrics, correction proposals and unresolved human review.
- [Stage 3C.3 frozen-context answer protocol](reports/STAGE_3C3_ANSWER_EVALUATION_PROTOCOL_20261114.md): prepared 36-attempt Luna pilot, exact offline payloads, manual rubric and runtime prerequisites; no live execution.
- [Stage 2B.2 scoring calibration v2.1](reports/STAGE_2B2_SCORING_CALIBRATION_20261114.md): essential/conditional/optional/alternative requirements for all 20 families, source-proof diagnostics and reviewer-assisted answer scoring; no retrieval or live-answer changes.
- [Stage 2B.2 compact-attribution delivery experiment](reports/STAGE_2B2_CONTEXT_DELIVERY_20261114.md): frozen-candidate pilot comparison, metadata-budget gains and warning regressions; D1 rejected and original A/B/C fixtures retained.
- [Stage 3C.3 Luna live answer pilot](reports/STAGE_3C3_LUNA_LIVE_ANSWER_EVALUATION_20261115.md): 36 completed original A/B/C attempts, durable dispatch guard, provisional v2.1 answer review, usage and paired comparison; no deployment.
- [Stage 3C.3 offline scorer repair and adjudication](reports/STAGE_3C3_SCORER_REPAIR_AND_ADJUDICATION_20261115.md): resolved conditional-applicability conflicts, immutable 36-answer replay, disclosed post-result corrections and remaining human-review requirements; no new model work.
- [Stage 2B.2 source-faithful extraction feasibility](reports/STAGE_2B2_SOURCE_FAITHFUL_EXTRACTION_FEASIBILITY_20261116.md): three separate reference-informed passage libraries, coherent token-cost bounds, all-question safety ledgers and architectural comparison; no production extractor.
- [Stage 2B.2 query decomposition feasibility](reports/STAGE_2B2_QUERY_DECOMPOSITION_FEASIBILITY_20261116.md): authorized 41-query embedding job, full fair-budget candidate comparisons, combined extraction bounds and rejection of the frozen decomposition; production unchanged.
- [Architecture review](reports/INDEPENDENT_LAEW_ARCHITECTURE_REVIEW_20261117.md) and [evidence navigation](reports/STAGE_3C4_EVIDENCE_NAVIGATION_20261117.md) cover the document-locality audit and the closed navigation trial.
- [Final RAG optimization results](reports/FINAL_RAG_OPTIMIZATION_RESULTS_20261118.md) record both NO-GO decisions. [ADR-003](decisions/ADR-003-rag-pipeline-reranking.md#operational-decision--2026-11-18) records closure and the reopening criteria.

Stage 2B.2 code, protocols, synthetic regression fixtures and result summaries are versioned. Large corpus/vector/trace exports and machine-local Git audit logs are ignored; public source snapshots, real-world questions/labels and indexes remain in the external versioned workspaces referenced by the reports.

For offline replay, configure the original sealed package paths using
`LAEW_RETRIEVAL_BUDGET_ROOT`, `LAEW_FINE_EVIDENCE_ROOT`,
`LAEW_FIXED_BODY_ROOT` and `LAEW_S0_S1_PREVIOUS_ROOT` as applicable. Historical
reports retain the original artifact references. Verifying original checkout
preservation requires the original checkout and sealed runner snapshot.

Cloud provider configuration and troubleshooting: [Unified model providers](CLOUD_CHAT.md).
