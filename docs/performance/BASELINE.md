# LAEW Performance Baseline — Milestone 14

Reference numbers recorded by `tests/benchmarks/` (pytest-benchmark) on a clean
local run. Tolerances and suites are **informational** — the job of the
benchmark suite is to *record*, not to gate CI on wall clock.

## Environment

| Item | Value |
|------|-------|
| OS | Windows 11 Pro (10.0.26200) |
| Python | 3.14.7 |
| pytest | 9.1.1 |
| pytest-benchmark | >=4.0.0 |
| Backend | In-memory stubs (no network, no models) |
| Date | 2026-09-16 |

All four benchmark hooks are fully offline: no model is invoked and no socket is
opened, so numbers are **LAEW runtime overhead only**.

## Test Matrix

| Suite | Measures |
|-------|----------|
| `test_profile_rag_retrieval.py` | `VectorStore` cosine search, ten-search batch, index build |
| `test_profile_agent_executor.py` | Full `AgentExecutor.run()` (4 tool steps + answer); cached system-prompt path |
| `test_profile_workflow_dispatch.py` | `WorkflowEngine` sequential no-op plans (20 / 60 steps) |

## Recorded Numbers (mean, from one local run)

| Benchmark | Mean | Note |
|-----------|------|------|
| rag top-k search (dim 256, 500 chunks) | ~40 µs | single `cosine` retrieval |
| rag ten searches | ~376 µs | 10 retrievals + rerank + context build |
| rag index build (500 chunks) | ~39.8 ms | `add_chunks` vectorization + index insert |
| agent full run (4 tool steps + answer) | ~133 µs | scripted stub provider; measured with `pedantic(setup=...)` per round |
| agent cached prompt, 10 single-step runs | ~217 µs | ≈22 µs/run — system prompt built once per executor |
| workflow 20-step sequential plan | ~1.43 ms | no-op tool steps |
| workflow 60-step sequential plan | ~4.33 ms | linear growth vs. 20-step confirmed |

## Methodology Notes

- **Agent benchmark restructured (M14 fix):** each measured round uses a *fresh*
  executor via `benchmark.pedantic(..., setup=_setup_executor)`. pytest-benchmark
  invokes `setup` once per round outside the timing window. An earlier draft
  reused one executor across rounds, so per-call cost compounded with history
  (inline 0.3 ms → 850 ms by 3.5k turns) and the run appeared to hang.
- **Production fix surfaced by the same investigation:** `_trim_to_budget` in
  `laew/agent/executor.py` was O(k²) (re-joined the whole message list after
  each dropped turn). Rewritten as a single O(n) char-length pass — verified with
  a 5000-call growth script (worst single call 61.6 ms at 10 010 turns, no
  blow-up). Real sessions stay well below that history depth, where per-call
  trim cost is a few hundred microseconds.
- Residual per-call cost is still proportional to conversation length (the
  estimator scans the message list once per step) — bounded above by the true
  cost of serializing those messages for the provider.

## Regression Guide

- RAG top-k mean should stay ~µs-scale; an order-of-magnitude jump signals a
  vector-store regression.
- Agent full-run mean should stay sub-millisecond; a jump toward seconds means
  per-call work is being done once per conversation turn instead of once per
  executor.
- Workflow 60-step should stay roughly 2–3× the 20-step cost (sequential plan,
  per-step overhead constant).