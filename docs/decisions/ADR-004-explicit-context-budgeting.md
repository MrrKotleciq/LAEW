---
type: adr
id: ADR-004
title: Explicit Context Budgeting
status: Accepted
date: 2026-08-25
purpose: Treat context as a limited resource and budget it explicitly (system prompt, conversation, RAG, tool results), reserving room for reasoning and the response.
scope: prompt sizing, token budgeting, context enforcement
read_when:
  - tuning prompt or context budgets
  - token calibration or estimation
  - Milestone 3 (Chief Agent Runtime) and Milestone 14 (Performance & Context-Efficiency Audit)
related:
  - ADR-001
  - ADR-003
  - ADR-005
---
# ADR-004 — Explicit Context Budgeting

## Status
Accepted

## Context
LLM context windows are limited computational resources. Without explicit budgeting, uncontrolled tool outputs, chat history, and retrieval documents exhaust the window, leaving insufficient headroom for model reasoning and output generation.

## Decision
Explicitly budget context across distinct operational segments (system prompts, active conversation, RAG context, and tool results) rather than consuming all available tokens.

## Consequences
- Prevents context bloat and preserves room for response generation and intermediate reasoning.
- Forces retrieval and tool wrappers to return dense, concise outputs.
