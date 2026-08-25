# LAEW — Architecture Decisions

This file records decisions explicitly documented in the
LAEW architecture documentation.

## Model abstraction

The system should use model roles rather than hard-coding
one specific model.

## Knowledge separation

Knowledge remains outside the LLM.

## Obsidian

Obsidian is intended to store knowledge rather than source code.

## RAG

RAG should retrieve and rerank relevant information rather
than sending an entire knowledge base to the model.

## Context

Context should be budgeted.

## Instructions

The system should use layered instructions rather than one
giant prompt.

## Conflict handling

The agent should report conflicts between sources.

## Scaling

LAEW should scale by adding independent components.

## Security

Security restrictions should exist below the model layer.
