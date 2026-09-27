---
type: index
title: Architecture
scope: current architectural intent and principles
read_when:
  - understanding the current architectural direction
  - evaluating new architectural changes
  - reviewing design principles
---

# Architecture

This directory contains documents describing LAEW's current architectural intent and design principles.

## Documents

| Document | Purpose |
|----------|---------|
| [Overview](#overview) | High-level architectural overview |
| [Model Abstraction](ADR-001-model-abstraction.md) | Model roles and provider abstraction |
| [Obsidian Second Brain](ADR-002-obsidian-second-brain.md) | Global knowledge vault design |
| [RAG Pipeline](ADR-003-rag-pipeline-reranking.md) | Retrieval and reranking pipeline |
| [Context Budgeting](ADR-004-explicit-context-budgeting.md) | Explicit context budgeting |
| [Layered Prompts](ADR-005-layered-prompt-architecture.md) | Modular prompt architecture |
| [Security Below Model](ADR-006-security-below-model-layer.md) | Security boundaries |
| [Tool Contracts](ADR-008-modular-tool-contracts.md) | Modular tool contract structure |
| [Documentation as Memory](ADR-009-documentation-as-long-term-memory.md) | Documentation as long-term memory |
| [Multi-Root Workspace](ADR-010-multi-root-workspace-and-path-aliasing.md) | Multi-root workspace and path aliasing |
| [Project vs Global Memory](ADR-011-project-memory-vs-global-knowledge-separation.md) | Project memory vs global knowledge separation |
| [Agent vs State](ADR-012-agent-memory-vs-current-state-separation.md) | Agent memory vs current state separation |
| [Sequential Deployment](ADR-013-sequential-deployment-stages.md) | Sequential deployment stages |
| [Stability Over Breadth](ADR-014-infrastructure-stability-over-feature-breadth.md) | Infrastructure stability over feature breadth |
| [Automation Modes](ADR-015-automation-with-manual-disabled-modes.md) | Automation with manual and disabled modes |
| [Structured Logging](ADR-016-structured-tool-invocation-logging.md) | Structured tool invocation logging |
| [Single-Agent First](ADR-017-single-agent-stability-before-multi-agent.md) | Single-agent stability before multi-agent |
| [Multi-Agent Protocol](ADR-018-multi-agent-communication-protocol.md) | Multi-agent communication protocol |
| [Provider Registry](ADR-019-provider-registry-and-factory.md) | Provider registry and factory |

## Principles

LAEW is built on several core principles:

- **Model Agnostic**: The model is only one component of the environment. LAEW never depends on one specific LLM or provider.
- **Security Below the Model**: Programmatic security boundaries exist below the model layer (ADR-006, Principle P8).
- **Explicit Context Budgeting**: Context is a limited resource; budgeting prevents overflow (ADR-004).
- **Layered Prompts**: One gigantic system prompt is rejected; layered instructions reduce bloat (ADR-005).
- **Documentation as Memory**: Repository documentation serves as long-term memory (ADR-009).
- **Stability First**: Infrastructure stability takes precedence over feature breadth (ADR-014).
- **Single-Agent First**: Single-agent stability is verified before multi-agent scaling (ADR-017).
- **Sequential Deployment**: Milestones are deployed sequentially with independent verification (ADR-013).
- **Automation with Fallback**: Automation operates with manual and disabled fallback modes (ADR-015).

## Milestone Alignment

Milestones map to architectural decisions:

- **M01** (Declarative Foundation): Established ADR-001 through ADR-009.
- **M02** (Tool Runtime Wrappers): Implemented security boundaries per ADR-006.
- **M03** (Chief Agent Runtime): Implemented layered prompts (ADR-005) and context budgeting (ADR-004).
- **M04** (Knowledge System): Implemented RAG pipeline (ADR-003) and global knowledge (ADR-002).
- **M05** (Documentation Synchronization): Formalized documentation as long-term memory (ADR-009).
- **M06** (Audit Remediation): Applied structured logging (ADR-016) and stability-first principles (ADR-014).
- **M07** (Technical Debt Refactoring): Refactored for maintainability under ADR-013.
- **M10** (Multi-Agent): Implemented hybrid message-passing + shared-context protocol (ADR-018).
- **M11** (Production Hardening): Provider registry (ADR-019), logging, packaging.
- **M15** (Multi-Model Routing): Provider registry and factory (ADR-019).

## Roadmap

The current roadmap is in [../roadmap/README.md](../roadmap/README.md).

## See Also

- [Decisions Index](../decisions/README.md)
- [Roadmap](../roadmap/README.md)
- [Project Status](../PROJECT_STATUS.md)
