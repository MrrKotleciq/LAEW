# ADR-008 — Modular Tool Contracts Structure

## Status
Accepted

## Context
Tool capabilities in LAEW will expand over time to include filesystem, version control, terminal, web, embedded systems, hardware debuggers, and container runners. A single monolithic specification file would become congested and hard to maintain.

## Decision
Organize tool contracts modularly by placing dedicated `CONTRACT.md` files within respective category subdirectories under `tools/` (e.g., `tools/filesystem/CONTRACT.md`, `tools/git/CONTRACT.md`).

## Consequences
- Each tool category is self-contained and independently versioned.
- Future tool wrapper implementations reside directly alongside their respective contract specifications.
