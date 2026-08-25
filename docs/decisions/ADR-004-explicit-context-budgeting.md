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
