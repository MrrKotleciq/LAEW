# Per-turn context and retrieval diagnostics

Workbench previously rendered routing, memory and tool activity from the latest stream. Conversation events recorded the dialogue and tool outcomes, but did not preserve the routing decision or whether prepared evidence reached the provider.

## Identity and lifecycle

SessionStore remains the source of truth. A conversation already has a stable ID, and its run ID identifies one user turn across provider requests and tool calls. The terminal run event also references the original user event and, for a completed answer, its assistant event. Existing tool call IDs correlate RagTool search summaries with tool outcomes. The browser cancellation handle remains a separate transport detail.

SessionStore stores diagnostic schema version 1 in the optional `diagnostics` field of a run event. It contains `routing`, `tools` and `requests`. The enclosing event supplies the identity and lifecycle status. Workbench and CLI chat using shared conversations write one initial context checkpoint when the executor starts the first provider attempt and commit the full snapshot with the existing terminal event. Both writes use the existing atomic JSON replacement and conversation locks. Live updates do not write to disk. A crash before the checkpoint can leave only the run and user events. A later crash preserves the checkpoint and any tool events already written by the existing conversation logger. Recovery marks an abandoned run failed under its exclusive lease. Named legacy CLI sessions keep their dialogue-only format.

The conversation format remains version 1. The read API treats a missing, unsupported or malformed diagnostic payload as unavailable. The snapshot grows with tool calls and provider attempts, which are bounded by the executor. The list of retrieved document paths is capped at 50 per search. In the four-turn acceptance fixture, the checkpoint and final diagnostic objects together occupied about 1.0–2.4 kB of compact JSON per turn. The conversation file also includes its existing JSON formatting and event metadata.

## What the record represents

- Routing records the original reason, elapsed time, requested scopes, Memory Recall selection and whether the requested project source was unavailable.
- Automatic Memory Recall records its own status and permitted scopes. When available, it records candidate and selection counts, omissions observed while checking the memory budget, selected IDs and an estimated context size. Semantic fallback has its own error category.
- Automatic prefetch records a start phase and its outcome. RagTool records whether the call reached the retrieval pipeline, the freshness check outcome when available, candidates, matching paths, excerpts prepared, omissions, truncation and excerpts supplied. Model-initiated calls and reused tool results remain separate from prefetch.
- Provider attempts record the iteration, attempt, duration, result and provider-reported token usage when available. Each attempt counts the seeded history messages retained and current-turn tool results available after executor budget enforcement. Automatic context and tool observations are marked supplied when the executor dispatches them to a provider adapter. This measures adapter input. A failure can still occur before the remote service receives the request. Retries inside a provider adapter are outside this boundary.
- Generic tools record the call ID, order, status and duration. A successful filesystem read is shown as a tool result. Document attribution for a read would require trustworthy path metadata from that tool.

At the run level, `running`, `completed`, `cancelled` and `failed` describe the execution lifecycle. Within preparation, `not_selected`, `selected`, `started`, `skipped` and `unavailable` describe the decision and progress. A RAG result can contain excerpts (`found`), return an empty result (`empty`), report exact duplicates (`already supplied`) or fail (`error`). The supplied count independently describes what reached the provider adapter. Estimated sizes use character-based estimates.

## Workbench

Use **View context** on an assistant response, or choose a turn from the Context or Run selector. The same selection applies across both tabs and stays pinned during a new run. **Follow live run** returns to current progress. After generation, **Follow latest turn** resumes following the conversation. Attempts without a completed assistant response appear in Run. Legacy turns display **Diagnostic data unavailable for this turn.** Existing tool result events can appear as separately labeled historical evidence.

Live Workbench diagnostics use the chat NDJSON stream, with a conversation ID and a persisted run ID. Historical diagnostics use the existing conversation read route. For a project conversation, the requested project and active project must match the stored owner, and that project must still be available. General Chat can read general conversations in its own scope. Diagnostic payloads store logical paths, identifiers, counts and error categories. Prompt text, retrieved bodies, private memory text and raw tool arguments stay outside the snapshot. This record can later support offline analysis of routing decisions, retrieval coverage and phase latency without requiring extra model calls.
