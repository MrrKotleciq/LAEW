---
type: adr
id: ADR-016
title: Structured Tool Invocation Logging
name: Structured Tool Invocation Logging
description: Logs tool invocations in a structured, diagnostic format so every agent action is traceable for debugging and audit.
tags:
  - logging
  - diagnostics
  - tools
status: Accepted
date: 2026-09-03
purpose: Log tool invocations in a structured, diagnostic format so every agent action is traceable for debugging and audit.
scope: tool logging, diagnostics, invocation records
read_when:
  - debugging tool calls or agent behavior
  - implementing structured logging (laew/tools)
  - Milestone 18 (Monitoring, Telemetry & Backup)
related:
  - ADR-006
  - ADR-008
  - ADR-019
---
# ADR-016 — Structured Tool Invocation Logging

## Status
Accepted

## Context
Tool calling failures are difficult to diagnose without visibility into what was called, with what arguments, and what result was returned. When an agent misuses a tool or a tool returns unexpected output, the absence of structured logs forces guesswork.

## Decision
All tool invocations must produce structured audit logs containing the timestamp, approved tool and operation labels, argument shape, duration and outcome. The M18 privacy decision retains the existing top-level JSONL fields. `arguments` records bounded top-level type counts. Unknown tool and operation labels become `UNKNOWN`. `error_code` contains an approved code or null, and `error_message` is null. `status` and `success` distinguish completion from failure, with timeout identified by its approved error code. The subsequent operator CLI removed the direct `laew tool --log` command. The format remains applicable to existing exports and the tool audit logger.

The audit record excludes argument names and values, result contents and exception text. The invoking tool caller retains its existing response under the current access rules. Keep audit files in operator-controlled storage separate from project source files. Retained run telemetry requires explicit opt-in. See the [M18 decision register](../reports/M18_IMPLEMENTATION_READINESS_AND_PLAN_20261118.md#p01-progress-and-decision-register).

## Consequences
### Positive
- Tool calling problems can be diagnosed using the recorded operation, outcome and argument types.
- Performance bottlenecks are visible through duration tracking.
- Error patterns become identifiable across sessions.

### Negative
- Log storage consumes disk space over time.
- Requires log rotation or archival strategy for long-running systems.
- Older audit files may contain sensitive content and remain private.
