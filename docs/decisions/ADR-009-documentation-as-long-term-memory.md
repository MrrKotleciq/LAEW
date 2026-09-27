---
type: adr
id: ADR-009
title: Repository Documentation as Long-Term Memory and Project Sync
status: Accepted
date: 2026-08-25
purpose: Treat in-repository documentation as the project's long-term memory and keep it synchronized with the code and its state.
scope: documentation, project-sync, docs/ maintenance
read_when:
  - creating or updating project documentation
  - running or extending project-sync
  - deciding where a decision belongs
related:
  - ADR-007
  - ADR-012
  - ADR-013
---
# ADR-009 — Repository Documentation as Long-Term Memory and Project Sync

## Status
Accepted

## Context
AI assistant sessions are ephemeral. Long-term engineering continuity across sessions requires that architectural decisions, technical constraints, and implementation status persist in version-controlled project memory rather than chat session logs.

## Decision
Treat repository documentation as LAEW's long-term memory. The `project-sync` workflow synchronizes verified decisions, status updates, and milestones from active sessions into documentation without ending the session or automatically executing Git commits.

## Consequences
- Project state and rationale remain accessible to future agents and human engineers.
- Session management is decoupled from documentation synchronization.
