# ADR-002 — Obsidian Vault for Knowledge Storage

## Status
Accepted

## Context
Engineering projects require structured, persistent knowledge bases spanning notes, research, hardware specifications, and decisions. Mixing unstructured knowledge notes directly into source code repositories creates noise and obscures codebase boundaries.

## Decision
Use an Obsidian markdown vault as the structured Second Brain knowledge store. Obsidian is intended to store interconnected knowledge and linked notes across domains, not raw project source code.

## Consequences
- Knowledge is connected through bidirectional links rather than rigid folder hierarchies alone.
- Source code remains in Git repositories while domain knowledge resides in the knowledge base.
