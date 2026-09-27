---
type: index
title: Documentation
scope: architecture, decisions, roadmap, history, performance, security, source
read_when:
  - navigating the documentation tree
  - understanding the project structure
---

# LAEW Documentation

This directory contains the project's architecture, decisions, status, history, roadmap, performance data, security reviews, and reference material.

Start here before searching the documentation tree.

## Documentation Map

| Area | Path | Purpose |
|---|---|---|
| Project Context | `LAEW_CONTEXT.md` | Concise project scope, goals, and constraints |
| Project Status | `PROJECT_STATUS.md` | Current implemented state |
| Architecture | `architecture/` | Current architectural intent and principles |
| Decisions | `decisions/` | Recorded Architecture Decision Records |
| Roadmap | `roadmap/` | Planned milestones and future work |
| History | `history/` | Chronological development history |
| Performance | `performance/` | Measurements, benchmarks, and baselines |
| Security | `security/` | Security reviews and findings |
| Source | `source/` | Reference/source material |

## Source-of-Truth Hierarchy

1. Current source code and tests describe implemented behavior.
2. Accepted ADRs describe recorded architectural decisions.
3. `PROJECT_STATUS.md` summarizes current project state.
4. `LAEW_CONTEXT.md` defines project scope and high-level context.
5. `roadmap/` describes planned work.
6. `history/` records historical events.
7. `source/` contains reference material.

Plans and documentation must not be assumed to describe implemented behavior without verification.

## Navigation Rules

- Read this file first when the relevant documentation location is unknown.
- Search for relevant documents before reading large files.
- Read only the documents required for the current task.
- Use document metadata to determine relevance.
- Prefer a specific ADR or milestone document over scanning an entire directory.

## Common Queries

### Architecture
Start with `architecture/` and `decisions/`.

### Current implementation
Start with `PROJECT_STATUS.md`, then inspect source code and tests.

### Planned work
Start with `roadmap/`.

### Historical investigation
Start with `history/`.

### Security
Start with `security/` and relevant ADRs.

### Performance
Start with `performance/`.