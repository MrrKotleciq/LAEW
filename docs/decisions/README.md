---
type: index
title: Architecture Decision Records
scope: architectural decisions
read_when:
  - implementing a feature that requires an architectural decision
  - reviewing a design change
  - understanding a system component
---

# Architecture Decision Records (ADRs)

ADRs are single-sentence decisions that record *why* a design was chosen, not just *what* was chosen. They serve as the project's long-term memory.

## How to Read This Index

Each ADR is a standalone document. Use the table below to find the relevant decision:

| ID | Title | Status | When to Read |
|----|-------|--------|--------------|
| [ADR-001](ADR-001-model-abstraction.md) | Model Abstraction and Roles | Accepted | When designing or modifying LLM provider integration |
| [ADR-002](ADR-002-obsidian-second-brain.md) | Obsidian Vault for Global Knowledge Storage | Accepted | When integrating the Obsidian vault or designing @knowledge retrieval |
| [ADR-003](ADR-003-rag-pipeline-reranking.md) | RAG Retrieval and Reranking Pipeline | Accepted | When designing RAG retrieval or reranking |
| [ADR-004](ADR-004-explicit-context-budgeting.md) | Explicit Context Budgeting | Accepted | When designing context management or budgeting |
| [ADR-005](ADR-005-layered-prompt-architecture.md) | Layered Modular Prompt Instructions | Accepted | When designing prompt architecture |
| [ADR-006](ADR-006-security-below-model-layer.md) | Programmatic Security Below Model Layer | Accepted | When designing security boundaries |
| [ADR-007](ADR-007-documentation-language-convention.md) | English Language for Repository Artifacts | Accepted | When choosing documentation language |
| [ADR-008](ADR-008-modular-tool-contracts.md) | Modular Tool Contracts Structure | Accepted | When designing tool interfaces |
| [ADR-009](ADR-009-documentation-as-long-term-memory.md) | Repository Documentation as Long-Term Memory | Accepted | When planning documentation strategy |
| [ADR-010](ADR-010-multi-root-workspace-and-path-aliasing.md) | Multi-Root Workspace Boundaries and Logical Path Aliasing | Accepted | When designing workspace boundaries |
| [ADR-011](ADR-011-project-memory-vs-global-knowledge-separation.md) | Separation of Project Memory and Global Knowledge | Accepted | When designing memory layer separation |
| [ADR-012](ADR-012-agent-memory-vs-current-state-separation.md) | Agent Memory vs Current State Separation | Accepted | When designing agent memory architecture |
| [ADR-013](ADR-013-sequential-deployment-stages.md) | Sequential Deployment Stages with Independent Verification | Accepted | When planning release strategy |
| [ADR-014](ADR-014-infrastructure-stability-over-feature-breadth.md) | Infrastructure Stability Over Feature Breadth | Accepted | When prioritizing feature work |
| [ADR-015](ADR-015-automation-with-manual-disabled-modes.md) | Automation with Manual and Disabled Fallback Modes | Accepted | When designing automation workflows |
| [ADR-016](ADR-016-structured-tool-invocation-logging.md) | Structured Tool Invocation Logging | Accepted | When designing logging and observability |
| [ADR-017](ADR-017-single-agent-stability-before-multi-agent.md) | Single-Agent Stability Before Multi-Agent | Accepted | When considering multi-agent scaling |
| [ADR-018](ADR-018-multi-agent-communication-protocol.md) | Multi-Agent Communication Protocol | Accepted | When designing multi-agent coordination |
| [ADR-019](ADR-019-provider-registry-and-factory.md) | Provider Registry and Factory | Accepted | When adding or changing model providers |

## ADR Process

1. **Propose** — Write a draft ADR describing the problem, options considered, and the proposed decision.
2. **Discuss** — Review with the team (or yourself, in solo development).
3. **Decide** — Mark as `Accepted` in the ADR.
4. **Implement** — Implement the decision in code.
5. **Document** — Update the ADR with implementation notes and consequences.

## When to Write an ADR

- When a decision has **architectural implications** (affects multiple components, future extensibility, or security).
- When a decision involves **trade-offs** between competing concerns (e.g., simplicity vs. flexibility).
- When a decision **affects the model interface** (keep the system model-agnostic).
- When a decision **affects security boundaries** (security below the model layer).

## When NOT to Write an ADR

- For minor implementation details (e.g., "use a list instead of a dict").
- For decisions that are purely aesthetic (e.g., code formatting).
- For decisions that are already obvious or have a single clear answer.
- For decisions that are purely infrastructural and don't affect the system model.

## See Also

- [Architecture Overview](../architecture/README.md)
- [Project Status](../PROJECT_STATUS.md)
- [Roadmap](../roadmap/README.md)
