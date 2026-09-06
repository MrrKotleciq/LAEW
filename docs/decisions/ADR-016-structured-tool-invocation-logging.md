# ADR-016 — Structured Tool Invocation Logging

## Status
Accepted

## Context
Tool calling failures are difficult to diagnose without visibility into what was called, with what arguments, and what result was returned. When an agent misuses a tool or a tool returns unexpected output, the absence of structured logs forces guesswork.

## Decision
All tool invocations must produce structured logs containing at minimum:
- **Timestamp**: When the invocation occurred.
- **Tool name**: Which tool was called.
- **Arguments**: What parameters were passed.
- **Result**: What output or error was returned.
- **Duration**: How long the invocation took.
- **Status**: Success, failure, or timeout.

Logs must be accessible for debugging and stored in a location separate from project source files.

## Consequences
### Positive
- Tool calling problems can be diagnosed by inspecting actual invocations.
- Performance bottlenecks are visible through duration tracking.
- Error patterns become identifiable across sessions.

### Negative
- Log storage consumes disk space over time.
- Requires log rotation or archival strategy for long-running systems.
- Sensitive arguments (paths, query content) must be handled carefully if logs are shared.
