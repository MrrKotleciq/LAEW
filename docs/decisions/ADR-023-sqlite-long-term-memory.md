---
type: adr
id: ADR-023
title: SQLite Long-Term Memory with a Rebuildable Semantic Index
status: Accepted
date: 2026-11-02
scope: long-term memory, extraction, recall, settings
related: [ADR-006, ADR-011, ADR-012, ADR-019, ADR-022]
---
# ADR-023 — SQLite Long-Term Memory with a Rebuildable Semantic Index

## Context

Provider-neutral conversation history exists as versioned JSON in SessionStore.
Selected durable facts need a separate, reviewable lifecycle and retrieval across
conversations. Global Knowledge remains the curated Obsidian vault.

## Decision

Use SQLite as the source of truth for memories, sources, revisions, proposals,
extraction checkpoints, leased jobs, settings and a transactional index outbox.
Use a separate ChromaDB collection, `laew_long_term_memory`, as a disposable
semantic index with the existing embedding service. Validate every semantic hit
against the current SQLite version, status and authorized scope. Use SQLite FTS5
when semantic retrieval is unavailable.

One Python MemoryService serves Workbench and CLI. Chief Agent receives bounded
recall as a marked system-context block, never as fabricated conversation messages.
Extraction is a separate model request after completed turns, using durable jobs
and the existing provider abstraction, including native function output when
available. Review is the default; approval performs an optimistic version check.
Auto is conservative and leaves potential replacements and ambiguous cases for
review. The user can select a fixed extraction model; no paid fallback is chosen.

Settings reuses the existing navigation entry. Language and memory defaults have
per-project overrides. Appearance remains global. Permission mode stays on the
chat view and retains the existing PermissionBroker policy.

## Consequences

Conversation JSON and vault collections are not migrated. Index failure cannot
lose a committed memory. Index recovery is eventually consistent; SQLite checks
prevent stale or deleted index entries from reaching the model. Extraction is
model-dependent, bounded and retryable, not a second agent. See
[Long-Term Memory](../architecture/LONG_TERM_MEMORY.md) for the operational contract.
