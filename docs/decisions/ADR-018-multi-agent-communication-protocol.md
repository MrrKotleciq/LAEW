# ADR-018 — Multi-Agent Communication Protocol

## Status
Accepted

## Context
Milestone 10 requires specialized agents (researcher, architect, reviewer, debugger, documenter, coder) to collaborate under chief-agent coordination. ADR-017 established single-agent stability as a prerequisite; that condition is met (Milestones 7–9, including the workflow automation runtime and evaluation harness).

Coordination requires a defined way for agents to exchange messages, share findings, and agree (or disagree) on a final answer. Two archetypes were considered:
- **Shared memory only** — all agents read/write a common store with no explicit messages.
- **Message passing + shared context** — agents exchange typed messages (task/result/error/synthesis) AND publish findings to a shared journal.

A pure shared-memory design offers no audit trail of who delegated what, no correlation of a result back to its task, and no typed error channel.

## Decision
Adopt a hybrid protocol combining typed message passing with an append-only shared context journal:

1. **Message envelope** (`laew/multiagent/message.py`): a single immutable `AgentMessage` with `kind` (TASK, RESULT, CONTEXT, ERROR, SYNTHESIS, QUERY), `sender`, optional `recipient` (broadcast), `correlation_id`, `parent_id`, and `metadata`. `to_dict`/`from_dict` make it serialization-safe (JSON).
2. **Shared context journal** (`laew/multiagent/context.py`): an append-only store where any agent posts findings as `(key, content, source)` items with timestamps. The chief reads it back to build the final synthesis; specialists see prior findings before running.
3. **Plans as the delegation contract** (`laew/multiagent/plan.py`): a YAML plan defines subtasks, each bound to a single `SpecialistRole`, with a `deliverable` key that becomes the shared-context key.
4. **Failure isolation**: each delegation runs through a fresh `AgentExecutor`; a failing specialist is recorded (ERROR message + context entry) without aborting the run.
5. **Conflict detection**: outputs posted under the same deliverable key by different roles are compared on normalized text; disagreements are surfaced to the chief and the caller.

## Consequences
### Positive
- Delegations are traceable: every result carries its `correlation_id` back to a subtask.
- Specialist failures are contained, so one bad agent cannot abort the whole plan.
- The chief can synthesize from structured, attributed context rather than free-form reply text.
- Conflicts between specialists are explicitly visible instead of silently resolved.
- Model-agnostic: the protocol is plain data, provider-independent (P1).

### Negative
- Two coordination mechanisms (messages + shared context) must be kept consistent — the coordinator currently posts a context entry for every delegation, so messages and context stay in lockstep by construction.
- Conflict detection is text-similarity–based; it does not detect semantically different-but-not-textually-different outputs. A semantic conflict resolver is deferred.
- Plans are evaluated sequentially; parallel execution of independent subtasks is deferred to a later iteration.