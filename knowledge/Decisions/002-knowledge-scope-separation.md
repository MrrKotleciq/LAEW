---
title: Separate project memory from global knowledge
tags:
  - decision
  - scope
  - memory
backlinks:
  - 001-global-second-brain
---

# Decision: Separate project memory from global knowledge

## Context

Agents need both repository-specific state and cross-cutting domain knowledge.
Conflating the two clutters repositories and makes attribution ambiguous.

## Decision

Decouple the two stores by provenance and retrieval scope:

- **@project** — in-repo (`docs/`, `manifests/`, `tools/`, `prompts/`).
- **@knowledge** — the global Obsidian vault.

Retrieval is explicitly scoped, and synthesized statements cite their source.

## Consequences

Repositories stay focused on ground truth; global knowledge accumulates
independently over the long term.
