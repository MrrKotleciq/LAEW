---
type: adr
id: ADR-015
title: Automation with Manual and Disabled Modes
status: Accepted
date: 2026-09-03
purpose: Allow LAEW to automate repetitive tasks while preserving manual and fully-disabled fallback modes, so automation never removes user control.
scope: workflow runtime, automation, approval gates
read_when:
  - designing or changing workflow/automation behavior
  - Milestone 9 (Automation & Workflow Runtime)
  - implementing manual/disabled fallback modes
related:
  - ADR-006
  - ADR-013
  - ADR-019
---
# ADR-015 — Automation with Manual and Disabled Modes

## Status
Accepted

## Context
Automated processes (RAG index updates, Git hooks, knowledge synchronization) can fail, produce incorrect results, or interfere with debugging. When automation is mandatory and opaque, diagnosing problems becomes significantly harder because the user cannot isolate whether an issue stems from automation logic or the underlying component.

## Decision
Every automated process in LAEW must support three operational modes:
1. **Automatic**: The process runs without user intervention.
2. **Manual**: The process runs only when explicitly triggered by the user.
3. **Disabled**: The process is inactive and does not execute.

No automation may be designed as mandatory. The default mode for new automations is "manual" until proven reliable.

## Consequences
### Positive
- Failures can be isolated by disabling automation and running steps manually.
- Users retain full control over when background processes execute.
- Debugging is straightforward: disable automation, verify manually, re-enable.

### Negative
- Requires additional configuration surface for mode selection.
- Users must understand when to switch modes for troubleshooting.
