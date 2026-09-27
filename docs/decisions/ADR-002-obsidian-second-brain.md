---
type: adr
id: ADR-002
title: Obsidian Vault for Global Knowledge Storage
status: Accepted
date: 2026-08-25
purpose: Design a single global Obsidian vault as the cross-project "Second Brain" knowledge store, kept outside individual project repositories and outside the model.
scope: global knowledge storage, Second Brain, @knowledge scope
read_when:
  - integrating the Obsidian vault into LAEW
  - designing @knowledge retrieval or scope separation
  - Milestone 17 (Second Brain & Global Knowledge Integration)
related:
  - ADR-003
  - ADR-011
---
# ADR-002 — Obsidian Vault for Global Knowledge Storage

## Status
Accepted

## Context
Engineering projects require structured, persistent knowledge bases spanning notes, research, hardware specifications, and cross-project decisions. Mixing unstructured knowledge notes directly into individual source code repositories creates noise, duplication, and obscures codebase boundaries.

Furthermore, knowledge must not be isolated into fragmented, project-specific vaults when concepts (e.g., Linux, Docker, STM32, embedded protocols, AI patterns) apply across multiple current and future engineering projects.

## Decision
Use exactly one single, global Obsidian markdown vault (`GLOBAL_KNOWLEDGE_ROOT`, aliased as `@knowledge`) as the shared Second Brain across all projects. 

Obsidian is intended to store interconnected cross-project knowledge and linked notes across domains, not raw project source code or repository-specific operational status.

## Consequences
### Positive
- Knowledge is centralized, interconnected through bidirectional links, and reusable across multiple independent projects.
- Source code and project-specific operational memory remain isolated in their respective Git repositories.
### Negative
- Requires agents and tools to maintain clear boundary distinctions between project-scoped memory and global knowledge.
