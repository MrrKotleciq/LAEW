---
type: adr
id: ADR-008
title: Modular Tool Contracts Structure
status: Accepted
date: 2026-08-25
purpose: Define each tool (filesystem, git, terminal, web) as an independent, modular contract with explicit operations, parameters, and a security policy.
scope: tool contracts, tools/ layout, tool wrappers
read_when:
  - adding a new tool
  - implementing or reviewing a tool wrapper
  - Milestone 2 (Tool Runtime Wrappers)
related:
  - ADR-006
  - ADR-016
  - ADR-019
---
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
