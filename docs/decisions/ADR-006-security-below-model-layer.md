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
