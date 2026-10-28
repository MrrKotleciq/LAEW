---
type: rule
title: Hooks
scope: deterministic checks and automation via hooks
read_when:
  - configuring or using hooks
---

# Hooks

Use hooks for deterministic checks and automation.

- PreToolUse: validate or restrict tool operations.
- PostToolUse: run focused formatting or validation when appropriate.
- Stop: run final verification when configured.

Do not use dangerously-skip-permissions or equivalent unsafe bypasses.

Hooks must be predictable, non-destructive, and limited to their intended scope.

Use progress tracking for genuinely multi-step tasks; do not create unnecessary bookkeeping.