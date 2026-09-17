# LAEW Development Roadmap

## Current State

- **Stage:** Milestones 1–14 complete (declarative foundation → performance & context-efficiency audit).
- **Implemented:** tools with programmatic security, LLM provider + registry (ADR-019), RAG (in-memory + optional ChromaDB), single-agent loop, workflow runtime, evaluation harness, multi-agent orchestration (ADR-018), PEP 621 packaging, app logging, bandit CI gate, interactive testing console (`laew console`), session memory & conversation persistence (ADR-012), offline benchmark baselines + calibrated token estimation + real token accounting with budget enforcement + streaming chat.
- **Test health:** 586 unit tests collected across 28 suites (including session store + session command suites).
- **Milestone history** lives in `docs/history/CHANGELOG.md`; architecture decisions in `docs/decisions/`.

## Roadmap Principles

- Stable foundations before features (ADR-014).
- Sequential deployment stages with independent verification (ADR-013).
- Security below the model layer (P8).
- Model-agnostic architecture (P1); components replaceable and testable (P9).
- Scale by composition — add components, not one giant system (P10).
- Every milestone ships with tests; do not weaken tests to pass.

## Near-Term (next)

### Milestone 12: Interactive Testing Console
**Goal:** Provide an interactive console to drive every implemented surface (tools, provider/config precedence, agent loop, RAG, workflow, multi-agent, evaluation, manifests) for manual/exploratory testing, in one persistent session.
**Scope:** Implement `laew console` subcommand with a REPL (cmd.Cmd) that exposes: system check/info/set, provider info/models/health/generate, tool operations with approval gates, agent run/chat with trace, rag query/embed/stats, workflow discover/show/run, multiagent discover/show/run, eval datasets/tasks/task/dataset, prompt list/show, budget estimation, and session history with !N replay. Refactor shared runtime helpers into `laew/runtime.py` for DRY between CLI and console. All handlers are pure functions (args, state) -> exit code for testability.
**Dependencies:** None (all implemented components are already in place).
**Tests:** ~50-60 unit tests across 7 test files covering session parsing, each command handler, approval gates, provider stubs, and CLI subcommand registration. Manual offline and online verification.
**Definition of Done:** `laew console` boots, all commands work offline (except provider/agent/RAG-embed which need a live model and show [!] when unreachable), approval gates can be toggled and tested, config precedence is demonstrable, and the full test suite (existing + new) is green.

### Milestone 13: Session Memory & Conversation Persistence — ✅ Completed
**Goal:** Make agent sessions durable and restorable instead of ephemeral.
**Result:** `laew console` gains `session save|load|list|show|delete` with `SessionStore` (atomic, hardened JSON under `runtime/sessions`); `laew chat` gains `--resume/--session/--no-persist`; conversation memory persisted per ADR-012 and re-verified from the filesystem on load. 67 new tests (session_store: 45, session commands: 18, CLI resume/chat: 4).

### Milestone 14: Performance & Context-Efficiency Audit — ✅ Completed
**Goal:** Optimize the runtime on a verified baseline (ADR-014 level 8).
**Result:** Four streams shipped. (A) `tests/benchmarks/` — offline pytest-benchmark fixtures for the agent executor, RAG retrieval, and workflow dispatch; baselines recorded in docs/performance/BASELINE.md; profiling surfaced and fixed a real O(k²) regression in `AgentExecutor._trim_to_budget` (rewritten as a single O(n) pass). (B) `TokenEstimator` override + `TokenCalibrator` + `calibrate_with_ollama()` via `/api/tokenize` (offline-skipped). (C) static system prompt memoized per executor, `ExecutionResult` token accounting from real provider counts, manifest-driven `ContextBudget` enforcement that trims oldest history turns under budget pressure. (D) streaming chat (`generate_stream`, NDJSON parse, terminal token counts) with `laew chat` streaming by default (`--no-stream` to escape). 586 unit tests + 7 benchmark hooks green.

### Milestone 15: Multi-Model Routing & Provider Fallback
**Goal:** Route model roles across multiple providers and fall back on failure — the step right before multi-agent scaling.
**Scope:** Implement the model router from the LAEW v1.0 architecture (model roles → `ollama_primary` / `ollama_fallback` / cloud API); role→provider mapping with availability checks and cost/priority policy; use the ADR-019 registry as the dispatch seam; extend the bounded provider-fallback retry budget (H1) to role routing.
**Dependencies:** Milestone 14; build on the two providers already declared in the manifest.
**Tests:** Router dispatch per role, unavailable-provider fallback, policy precedence, budget exhaustion handling.
**Definition of Done:** A model role can resolve to a different provider (local→cloud) when the primary is unavailable, without code changes and with explicit policy configuration.

### Milestone 16: Parallel Multi-Agent Execution & Semantic Conflict Detection
**Goal:** Complete the deferred ADR-018 items.
**Scope:** Execute independent subtasks concurrently (thread/async executor) with per-specialist isolation preserved; replace text-similarity conflict detection with embedding-based semantic comparison reusing the existing embedding stack.
**Dependencies:** Milestone 15 (routing gives specialists resilient provider access); stable single-agent baseline (ADR-017).
**Tests:** Deterministic parallel delegation, shared-context consistency under concurrency, semantic-conflict cases that text-similarity misses.
**Definition of Done:** Independent subtasks run concurrently with a verifiable speedup; semantic conflicts are surfaced to the chief and caller.

---

## Mid-Term

### Milestone 17: Second Brain & Global Knowledge Integration
**Goal:** Make the Obsidian vault a real, curated knowledge source (ADR-002).
**Scope:** Stand up the `knowledge/` vault configured in the manifest; ingest and index the global vault into `@knowledge` RAG with structured organization (Knowledge, Decisions, Research, Templates) rather than a dumping ground; enforce project-specific docs stay in-repo, cross-project knowledge in the vault (ADR-011); link-aware chunking to preserve Obsidian backlinks.
**Dependencies:** None functional; Milestone 14 for retrieval latency.
**Tests:** Vault ingestion, scope separation (`@project` vs `@knowledge`), link preservation, source attribution in retrieved context.
**Definition of Done:** A populated Obsidian vault is indexed and retrievable as `@knowledge` context with correct scoping and sources.

### Milestone 18: Monitoring, Telemetry & Backup
**Goal:** Surround the system with the observability and backup layers from the v1.0 architecture.
**Scope:** Structured run telemetry (agent/tool/LLM events) into the existing logging framework; health/status summary (`laew status`); crash-safe session and vault backup/restore paths; retention policy for logs and sessions.
**Dependencies:** Milestones 13 (sessions to back up) and 17 (vault to backup).
**Tests:** Telemetry event integrity, `laew status` accuracy, backup/restore round-trips, retention enforcement.
**Definition of Done:** Every run produces inspectable telemetry; sessions and vault can be backed up and restored; operators can answer "what happened on run X."

### Milestone 19: MCP Tools Layer
**Goal:** Open the tool layer to the tool ecosystem via the Model Context Protocol.
**Scope:** MCP client adapter so external MCP servers appear as LAEW tools, enforcing existing approval/boundary rules (P8); keep the base `Tool` contract as the adapter interface so no tool behavior is bypassed.
**Dependencies:** Milestone 18 (telemetry covers MCP tool calls).
**Tests:** MCP tool discovery/adapter mapping, boundary enforcement, approval propagation, error mapping.
**Definition of Done:** An external MCP server's tools are usable by agents behind the same security and logging controls as native tools.

### Milestone 20: Multi-Project Workspace
**Goal:** Scale to multiple projects from a single LAEW install (P10).
**Scope:** Per-project workspaces each with their own RAG scope and memory, sharing one global vault; workspace switching; `@projects` orchestration and cross-project queries with explicit boundaries.
**Dependencies:** Milestones 17 (shared vault) and 18 (per-project telemetry).
**Tests:** Project isolation, shared-vault reads, boundary enforcement across projects, workspace switch correctness.
**Definition of Done:** One LAEW runtime serves multiple projects with isolated project memory/RAG and a single shared global knowledge source.

---

## Long-Term

### Milestone 21: v1.0 Stabilization & Release
**Goal:** Ship LAEW v1.0 per the documented architecture.
**Scope:** Full-documentation reconciliation; coverage gate in CI (≥80% per testing rule) with a coverage baseline; end-to-end release verification against the LAEW_CONTEXT v1.0 architecture; release candidate build and install verification.
**Dependencies:** All prior milestones.
**Tests:** Comprehensive doc-validation suite; CI coverage gate; install/upgrade path tests.
**Definition of Done:** `pip install laew` cleanly installs a feature-complete, documented, monitored, backed-up system matching the LAEW v1.0 architecture; CI is fully green with the coverage gate.

---

## Future Candidates (not yet sequenced)

- Cloud-provider integration beyond routing (full OpenAI/Anthropic provider builders in the ADR-019 registry).
- Agent memory with learned, persistent cross-session knowledge (distinct from filesystem current-state, ADR-012).
- Semantics-aware RAG reranking upgrades beyond cosine similarity (nested/colBERT-style).
- Interactive plan editor / workflow authoring UI.
- Multi-agent autonomous mode with manual and disabled fallbacks (ADR-015) fully exercised.