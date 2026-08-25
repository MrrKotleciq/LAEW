# ADR-005 — Layered Modular Prompt Instructions

## Status
Accepted

## Context
A single monolithic system prompt containing all project guidelines, tool rules, and workflow logic becomes unmaintainable, consumes excessive baseline tokens, and limits specialization.

## Decision
Reject a single gigantic system prompt in favor of layered, modular instruction files located under `prompts/`. Agents load core rules alongside specialized workflow prompts (e.g., architecture, research, code review, debugging).

## Consequences
- Instructions are modular, version-controlled, and testable independently.
- Agents operate with minimal necessary prompt context for each specific task category.
