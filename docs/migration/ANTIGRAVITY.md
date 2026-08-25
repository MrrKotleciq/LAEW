# LAEW — Antigravity Migration

## Purpose

Antigravity/Gemini is being introduced as an engineering
agent used to develop and evaluate LAEW.

It is not the LAEW runtime.

## Migration principle

Do not move the architecture into the model's memory.

Instead provide the agent with version-controlled project
context and instructions.

## Current state

Migration started.

Antigravity CLI is authenticated and running from the LAEW
workspace.

## Required validation

Before allowing implementation work, verify that the agent:

1. understands what LAEW is,
2. understands that the model is replaceable,
3. distinguishes architecture from implementation,
4. checks repository state,
5. respects user control,
6. does not modify files without approval,
7. recognizes source conflicts,
8. understands the intended RAG / memory / tool architecture.

## Migration test

The first meaningful task should be read-only.

The agent should inspect the repository and explain:

- what currently exists,
- what the architecture says should exist,
- what is not implemented yet,
- where uncertainty remains.

No files should be modified during this test.
