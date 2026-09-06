# ADR-017 — Single-Agent Stability Before Multi-Agent

## Status
Accepted

## Context
Multi-agent architectures (specialized agents for research, coding, documentation, planning) introduce coordination complexity, inter-agent communication overhead, and increased failure modes. Deploying multi-agent before single-agent stability is proven leads to unreliable systems where failures cascade across agents.

## Decision
Multi-agent capability is a post-v1.0 extension. Single-agent stability is a prerequisite. A single agent must demonstrate:
- Reliable tool calling.
- Stable session handling.
- Correct context management.
- Consistent behavior over extended operation.

Only after these criteria are met should multi-agent architectures be considered.

## Consequences
### Positive
- Debugging is simpler with a single agent execution path.
- Infrastructure is validated before adding orchestration complexity.
- Multi-agent design can incorporate lessons learned from single-agent operation.

### Negative
- Advanced workflows requiring agent specialization are deferred.
- Some tasks may be less efficient without specialized agents.
