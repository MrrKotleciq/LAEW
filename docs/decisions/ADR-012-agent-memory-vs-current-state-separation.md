# ADR-012 — Agent Memory vs Current State Separation

## Status
Accepted

## Context
Agent memory (episodic recall, semantic knowledge, past interactions) can become stale between sessions. A project's actual state may have changed via Git commits, file modifications, or configuration updates that occurred outside the agent's awareness.

Relying on memory alone for current project state leads to incorrect assumptions, outdated conclusions, and responses that contradict the actual repository.

## Decision
Separate agent memory from current project state as distinct concerns. Current state must always be verified from authoritative sources (Git status, filesystem inspection, manifest files) rather than recalled from memory.

Agents must not assume project state based on memory alone when answering questions about implementation, configuration, or recent changes.

## Consequences
### Positive
- Responses about project state are grounded in verifiable data.
- Memory can serve as context and history without being treated as ground truth.
- Reduces risk of confidently stating outdated information.

### Negative
- Requires tool invocations (Git, filesystem) for state verification, consuming part of the context budget.
- Agents must distinguish between "I recall from a previous session" and "the repository currently shows."
