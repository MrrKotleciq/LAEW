---
type: roadmap
id: M20
title: Multi-Project Workspace
status: completed
purpose: Scale LAEW to multiple projects from a single install with per-project RAG scope, shared global vault, and workspace switching.
read_when:
  - implementing multi-project workspace support
  - Milestone 20 (Multi-Project Workspace)
---

### Milestone 20: Multi-Project Workspace
**Goal:** Scale to multiple projects from a single LAEW install (P10).
**Scope:** Per-project workspaces each with their own RAG scope and memory, sharing one global vault; workspace switching; `@projects` orchestration and cross-project queries with explicit boundaries.
**Dependencies:** Milestones 17 (shared vault) and 18 (per-project telemetry).
**Tests:** Project isolation, shared-vault reads, boundary enforcement across projects, workspace switch correctness.
**Definition of Done:** One LAEW runtime serves multiple projects with isolated project memory/RAG and a single shared global knowledge source.