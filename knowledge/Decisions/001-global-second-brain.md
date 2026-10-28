---
title: Maintain a global Second Brain vault
tags:
  - decision
  - second-brain
  - knowledge
backlinks:
  - 002-knowledge-scope-separation
  - 03-Design-Patterns
---

# Decision: Maintain a global Second Brain vault

## Context

Engineering knowledge spans many projects — Linux, Docker, STM32, AI patterns.
Storing it inside each project repository duplicates it and buries it in code.

## Decision

Keep cross-project knowledge in a single global Obsidian vault outside the
project repositories. Project-specific memory stays in-repo.

## Consequences

Knowledge is centralized and interconnected through links. Source code stays
lightweight, and the same note serves every future project that needs it.
