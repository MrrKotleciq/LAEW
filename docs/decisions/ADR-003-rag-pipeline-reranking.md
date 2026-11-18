---
type: adr
id: ADR-003
title: RAG Retrieval and Reranking Pipeline
name: RAG Retrieval and Reranking Pipeline
description: Specifies the RAG pipeline — retrieval, candidate results, reranking, and small relevant context — with structured source attribution.
tags:
  - rag
  - retrieval
  - reranking
status: Accepted
date: 2026-08-25
purpose: Specify the RAG pipeline — retrieval, candidate results, reranking, and a small relevant context — with structured source attribution, so the model is never fed a whole knowledge base.
scope: RAG, vector store, knowledge base, reranking, context injection
read_when:
  - building or modifying RAG or the vector store
  - Milestone 4 (Knowledge System & RAG Pipeline)
  - Milestone 14 (performance of retrieval)
related:
  - ADR-001
  - ADR-002
  - ADR-004
---
# ADR-003 — RAG Retrieval and Reranking Pipeline

## Status
Accepted

## Context
Providing entire knowledge bases or large file trees directly to the LLM causes context bloat, increases hallucination risk, and degrades reasoning performance.

## Decision
RAG must function as an intelligent library using a multi-stage retrieval pipeline: retrieve candidate documents from vector storage, apply reranking, and inject only a small, highly relevant context slice to the model.

## Operational decision — 2026-11-18

The current RAG optimization cycle is closed. Retain production variant A, with legacy chunking, scoped dense cosine retrieval, and a prefetch limit of two results and 500 estimated tokens per scope. The current production ordering uses cosine similarity. Adaptive chunking and contextual embeddings received NO-GO decisions. Prior query-aware ranking, learned reranking, hybrid retrieval, hierarchical retrieval and navigation trials did not justify deployment.

The exposed development benchmark measures registered evidence completeness. It provides no estimate of answer accuracy in real user sessions. The corpus still has ten restricted source regions, 329 uninspected high-priority source findings and pending independent technical and bilingual review. Keep the frozen reports and external evidence packages as research records. Address source and access-control defects through maintenance.

Reopen optimization only when representative usage shows a recurring, material failure with a reproducible cause. Prespecify one bounded experiment, an appropriate baseline, independent tasks, and latency and memory limits. On a comparable multi-domain trial, require a net gain of at least three complete intent families across at least two domains, with zero new critical warning, applicability or access-control regressions. Close the trial if it misses the gate or unresolved evidence could change the decision.

The next development priority is [M18 — Monitoring, Telemetry & Backup](../roadmap/M18-Monitoring_Telemetry_%26_Backup.md). See the [final results](../reports/FINAL_RAG_OPTIMIZATION_RESULTS_20261118.md) and the [architecture review](../reports/INDEPENDENT_LAEW_ARCHITECTURE_REVIEW_20261117.md). The later navigation and optimization outcomes close the experiments proposed in that review.

## Consequences
- Unnecessary context injection is minimized.
- Large context windows are not used as an excuse to dump unfiltered documents.
