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
