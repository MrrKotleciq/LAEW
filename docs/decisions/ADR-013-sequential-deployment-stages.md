# ADR-013 — Sequential Deployment Stages with Independent Verification

## Status
Accepted

## Context
Installing all LAEW components simultaneously (Ollama, Odysseus, Obsidian, ChromaDB, RAG, Git hooks, agents, automation, monitoring) creates a fragile deployment where failures are difficult to isolate. When something breaks, the root cause is obscured by interdependent components that were never individually validated.

This "big bang" approach contradicts engineering best practices and makes debugging exponentially harder.

## Decision
Deploy LAEW components in sequential stages. Each stage must:
1. Work independently.
2. Be tested and verified in isolation.
3. Be documented as operational.
4. Only then serve as the foundation for the next stage.

The deployment sequence follows the architectural dependency order: foundation → model backend → agent orchestration → tools → knowledge systems → RAG → automation → monitoring → optimization → advanced features.

## Consequences
### Positive
- Failures are isolated to the most recently added component.
- Each stage provides a known-good baseline for debugging.
- Infrastructure quality is validated before adding complexity.

### Negative
- Slower initial deployment compared to parallel installation.
- Requires discipline to avoid skipping stages or deferring verification.
