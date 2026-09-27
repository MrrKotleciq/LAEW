---
type: adr
id: ADR-003
title: RAG Retrieval and Reranking Pipeline
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

## Consequences
- Unnecessary context injection is minimized.
- Large context windows are not used as an excuse to dump unfiltered documents.
