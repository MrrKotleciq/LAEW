# LAEW Architecture Decision Records (ADRs)

This directory contains individual Architecture Decision Records (ADRs) for LAEW.
Each significant architectural decision is recorded in its own dedicated document adhering to the `ADR-NNN-<short-title>.md` convention.

---

## Decision Log

| ID | Title | Status | Date |
| :--- | :--- | :--- | :--- |
| [ADR-001](ADR-001-model-abstraction.md) | Model Abstraction and Roles | `Accepted` | 2026-08-25 |
| [ADR-002](ADR-002-obsidian-second-brain.md) | Obsidian Vault for Global Knowledge Storage | `Accepted` | 2026-08-25 |
| [ADR-003](ADR-003-rag-pipeline-reranking.md) | RAG Retrieval and Reranking Pipeline | `Accepted` | 2026-08-25 |
| [ADR-004](ADR-004-explicit-context-budgeting.md) | Explicit Context Budgeting | `Accepted` | 2026-08-25 |
| [ADR-005](ADR-005-layered-prompt-architecture.md) | Layered Modular Prompt Instructions | `Accepted` | 2026-08-25 |
| [ADR-006](ADR-006-security-below-model-layer.md) | Programmatic Security Below Model Layer | `Accepted` | 2026-08-25 |
| [ADR-007](ADR-007-documentation-language-convention.md) | English Language for Repository Artifacts | `Accepted` | 2026-08-25 |
| [ADR-008](ADR-008-modular-tool-contracts.md) | Modular Tool Contracts Structure | `Accepted` | 2026-08-25 |
| [ADR-009](ADR-009-documentation-as-long-term-memory.md) | Repository Documentation as Long-Term Memory and Project Sync | `Accepted` | 2026-08-25 |
| [ADR-010](ADR-010-multi-root-workspace-and-path-aliasing.md) | Multi-Root Workspace Boundaries and Logical Path Aliasing | `Accepted` | 2026-08-25 |
| [ADR-011](ADR-011-project-memory-vs-global-knowledge-separation.md) | Separation of Project Memory and Global Knowledge | `Accepted` | 2026-08-25 |

---

## ADR Guidelines

1. **One ADR = One File**: Do not aggregate multiple architectural decisions into a single file.
2. **Immutability & Superseding**: Do not overwrite the historical rationale of accepted ADRs. If a decision is superseded, mark its status as `Superseded by [ADR-YYYY](...)` and link the new ADR with `Supersedes [ADR-XXXX](...)`.
3. **Scope**: Record only decisions impacting architecture, component boundaries, security policies, memory structures, or core agent contracts. Minor implementation details belong in code and Git commits.
