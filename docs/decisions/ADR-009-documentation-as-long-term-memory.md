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
