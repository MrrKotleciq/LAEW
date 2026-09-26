# Hooks

Use hooks for deterministic checks and automation.

- PreToolUse: validate or restrict tool operations.
- PostToolUse: run focused formatting or validation when appropriate.
- Stop: run final verification when configured.

Do not use dangerously-skip-permissions or equivalent unsafe bypasses.

Hooks must be predictable, non-destructive, and limited to their intended scope.

Use progress tracking for genuinely multi-step tasks; do not create unnecessary bookkeeping.

FILE: .claude/rules/ecc/common/patterns.md

# Patterns

Prefer existing LAEW architecture and conventions over introducing generic patterns.

## General Rules

- Search the repository before creating a new abstraction.
- Reuse existing interfaces and services when they already fit.
- Introduce patterns only when they solve a real recurring problem.
- Avoid pattern-driven design and speculative abstraction.

## Interfaces

Use explicit interfaces/protocols at real boundaries such as:

- storage
- external services
- tool implementations
- replaceable infrastructure

Keep implementations simple when no abstraction boundary is needed.