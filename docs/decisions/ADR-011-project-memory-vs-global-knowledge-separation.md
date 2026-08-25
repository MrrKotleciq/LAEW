# ADR-011 — Separation of Project Memory and Global Knowledge

## Status
Accepted

## Context
Engineering agents need access to both repository-specific state (active tasks, local architectural records, contracts, immediate status) and cross-cutting domain knowledge (electronics datasheets, networking protocols, generic algorithms, AI research). 

Conflating these memory tiers causes repository clutter, redundant duplication of notes across projects, and ambiguous attribution of ground truth.

## Decision
Formally decouple project memory from global knowledge across storage, provenance, and retrieval scopes:

1. **Project Memory (`@project`)**:
   - Resides directly within the project Git repository (`docs/`, `manifests/`, `tools/`, `prompts/`, `tests/`).
   - Captures repository ground truth, architecture decisions (ADRs), status, and contracts specific to LAEW.
2. **Global Knowledge (`@knowledge`)**:
   - Resides in the single global Obsidian Vault (`~/Projects/knowledge/`).
   - Captures general engineering knowledge, research notes, hardware specs, and reusable templates.
3. **Retrieval & Attribution Scoping**:
   - Agents and RAG pipelines must explicitly scope queries: `project-scoped` for implementation tasks, `global-scoped` for conceptual research, or `hybrid-scoped` when combining domain patterns with local state.
   - All factual statements synthesized by the agent must cite their exact provenance (`Project Memory` vs `Global Knowledge`).

## Consequences
### Positive
- Clear separation of concerns: repositories remain lightweight while global knowledge accumulates over the long term.
- Context injection is scoped cleanly, reducing retrieval noise and token waste.
### Negative
- Agents must consciously select retrieval scope depending on whether a task is project-specific or domain-generic.
