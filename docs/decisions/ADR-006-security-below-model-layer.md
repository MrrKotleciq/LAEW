---
type: adr
id: ADR-006
title: Programmatic Security Below Model Layer
status: Accepted
date: 2026-08-25
purpose: Enforce security (allowlists, approval gates, path boundaries, blocked operations) in code below the model layer, never by relying on model behavior.
scope: tool security, approval gates, path traversal, command execution
read_when:
  - adding or changing any tool
  - reviewing or implementing security boundaries
  - Milestone 2 (Tool Runtime Wrappers) and Milestone 19 (MCP tool layer)
related:
  - ADR-008
  - ADR-010
  - ADR-015
---
# ADR-006 — Programmatic Security Below Model Layer

## Status
Accepted

## Context
Relying solely on LLM prompt compliance or system prompt instructions for security is insufficient to protect files, environments, and secrets from prompt injection or unintended commands.

## Decision
Enforce security restrictions, path traversal sandboxing, safe command allowlists, and destructive operation blocks programmatically in tool wrappers below the model layer.

## Consequences
- Unapproved write operations, access to restricted paths (`.git`, `secrets`), and blacklisted shell commands are rejected by the execution engine regardless of LLM output.
- Safety boundaries are deterministic and independently testable.
