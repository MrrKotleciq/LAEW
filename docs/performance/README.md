---
type: index
title: Performance Measurements and Baselines
scope: performance data, benchmarks, and measurements
read_when:
  - evaluating a performance change
  - comparing implementations
  - troubleshooting performance issues
---

# Performance Measurements

This directory contains performance measurements, benchmarks, and baselines for LAEW.

## Documents

| Document | Purpose |
|----------|---------|
| [BASELINE.md](BASELINE.md) | Recorded benchmark numbers from a clean local run |

## Baseline Summary

The baseline was recorded on Windows 11 Pro with Python 3.14.7, using in-memory stubs (no network, no models).

| Benchmark | Mean | Notes |
|-----------|------|-------|
| RAG top-k search (dim 256, 500 chunks) | ~40 µs | single cosine retrieval |
| RAG ten searches | ~376 µs | 10 retrievals + rerank + context build |
| RAG index build (500 chunks) | ~39.8 ms | vectorization + index insert |
| Agent full run (4 tool steps + answer) | ~133 µs | scripted stub provider |
| Agent cached prompt, 10 single-step runs | ~217 µs | ~22 µs/run |
| Workflow 20-step sequential plan | ~1.43 ms | no-op tool steps |
| Workflow 60-step sequential plan | ~4.33 ms | linear growth |

## Methodology

All benchmarks are **offline** — no model is invoked and no socket is opened. Numbers represent **LAEW runtime overhead only**.

## See Also

- [Architecture](../architecture/README.md)
- [Decisions](../decisions/README.md)
