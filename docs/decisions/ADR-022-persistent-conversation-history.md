---
type: adr
id: ADR-022
title: Shared Persistent Conversation History
name: Shared Persistent Conversation History
description: Extends the shared session store with scoped, provider-neutral conversation events.
tags: [history, storage, scope, security]
status: Accepted
date: 2026-11-02
purpose: Persist independent conversations and their tool execution history across application surfaces.
scope: conversation history, execution events, recovery and isolation
related: [ADR-006, ADR-011, ADR-012, ADR-019, ADR-020]
---
# ADR-022 — Shared Persistent Conversation History

## Context

The existing JSON SessionStore atomically persists named console sessions, but its legacy format contains only user and final assistant text. Workbench conversations were process-local. Continuation across restarts needs independent, scoped conversations and the tool-call/result protocol, including interrupted execution.

## Decision

Extend SessionStore with versioned, per-conversation JSON records in its configured directory. Workbench and CLI use the same implementation and directory. Preserve legacy files without automatic migration. A conversation has an immutable scope and ordered provider-neutral events with stable IDs. Persist tool requests before execution and results afterwards. Serialize mutations with host-local file locks, hold an exclusive run lease, and use flush plus atomic replace for each update. On recovery, retain interrupted events and represent missing tool outcomes as unknown rather than re-executing calls.

The store redacts recognizable credentials and excludes raw provider payloads except bounded, scoped Gemini continuation signatures. Treat redaction as a defense in depth, not a guarantee that arbitrary secret text can be detected.

## Consequences

The format is compatible with existing local storage and needs no database migration. Each event rewrites its conversation file, so very large transcripts incur increasing I/O; no cross-host locking is promised. Legacy sessions retain their original limited detail. History is not Long-Term Memory and cannot establish current project state without verification. See [conversation history](../architecture/CONVERSATION_HISTORY.md) for the operational contract.
