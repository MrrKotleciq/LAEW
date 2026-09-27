---
type: roadmap
id: M14
title: Performance & Context-Efficiency Audit
status: completed
purpose: Optimize runtime on a verified baseline: O(n) context trimming, token calibration, streaming chat, pytest-benchmark baselines, and context-budget enforcement.
read_when:
  - optimizing performance or context usage
  - Milestone 14 (Performance & Context-Efficiency Audit)
---

### Milestone 14: Performance & Context-Efficiency Audit — ✅ Completed
**Goal:** Optimize the runtime on a verified baseline (ADR-014 level 8).
**Result:** Four streams shipped. (A) `tests/benchmarks/` — offline pytest-benchmark fixtures for the agent executor, RAG retrieval, and workflow dispatch; baselines recorded in docs/performance/BASELINE.md; profiling surfaced and fixed a real O(k²) regression in `AgentExecutor._trim_to_budget` (rewritten as a single O(n) pass). (B) `TokenEstimator` override + `TokenCalibrator` + `calibrate_with_ollama()` via `/api/tokenize` (offline-skipped). (C) static system prompt memoized per executor, `ExecutionResult` token accounting from real provider counts, manifest-driven `ContextBudget` enforcement that trims oldest history turns under budget pressure. (D) streaming chat (`generate_stream`, NDJSON parse, terminal token counts) with `laew chat` streaming by default (`--no-stream` to escape). 586 unit tests + 7 benchmark hooks green.