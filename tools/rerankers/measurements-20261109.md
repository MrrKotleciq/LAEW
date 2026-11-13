# Reranker functional smoke results — 2026-11-09

Sequential CPU-only tests on Ryzen 7 3700X / 16 GiB Windows 11. Docker Desktop 4.93.0 exposed 16 CPUs and 7.72 GiB RAM. ChromaDB and SearXNG remained running; the user stopped Horizon before inference tests. No global resource settings or production integration changed.

All three services passed real inference, explicit truncation and offline cache restart. Each final container is stopped with **exit 0, OOMKilled=false**. The existing Compose project remains `laew`.

## Latency and memory

Each short case contained 3–4 candidates. Values below are ranges over the five public multilingual/technical cases, including the first request. They are functional measurements with cold-start and host contention effects, not comparative quality or throughput results.

| Model | Loaded RAM (Docker stats) | RAM after short requests | Observed cgroup peak (1) | Total request ms | Native inference ms (2) | CPU % (3) | Offline restart s |
|---|---|---|---|---|---|---|---|
| gte | 1.426GiB | 1.427GiB | 1.562 GiB | 484.5–806.9 | 157.0–446.0 | 150.0–166.5 | 15.912 |
| bge | 2.988GiB | 2.992–2.998 GiB | 4.000 GiB | 1198.8–1698.9 | 373.0–569.0 | 169.1–177.9 | 35.046 |
| mxbai | 2.256GiB | 2.298–2.323 GiB | 2.397 GiB | 5350.2–17173.4 | 5289.2–17141.0 | 183.6–195.5 | 26.753 |

(1) Cgroup peak includes file cache and startup; sampled through the short-request phase, not continuously through long-input/restart phases. Docker stats subtracts inactive file cache and is not the same metric. BGE touched its **4 GiB** ceiling without an OOM kill; avoid concurrent model loading. Limits remain GTE 3 GiB, BGE/Mixedbread 4 GiB.

(2) TEI reports its native inference header, while Mixedbread measures the whole sequential scoring loop. These are different timing boundaries; preserve both native and total request timing.

(3) 100% means one CPU core. The cgroup CPU time is averaged over the request/measurement window, including Docker measurement overhead; each service has a two-core CPU quota.

## Downloaded weights and persistent storage

| Model | Weight file bytes | Dedicated cache bytes | Cache GiB |
|---|---|---|---|
| gte | 611,934,706 | 629,045,433 | 0.586 |
| bge | 2,271,071,852 | 2,288,196,965 | 2.131 |
| mxbai | 988,097,536 | 1,004,024,907 | 0.935 |

Combined dedicated caches: **3,921,267,305 bytes** (3.652 GiB). These are model file/cache sizes, not wire-traffic counters.
The shared TEI image is 937,655,393 bytes; the Mixedbread image is 1,556,516,126 bytes. Build cache is additional and was not pruned.

For each cache, the live test disconnected only that reranker from its Docker network, restarted it, verified readiness without network access, checked unchanged cached blob sizes and mtimes, reconnected the `laew_default` service alias, and verified identical scores and ranking. No weights were downloaded during these restarts.

## Validation and limitations

- **23 offline tests passed**; the opt-in live test is skipped during the default test command. All three independently invoked live lifecycle tests passed. All tests used `scripts/run_isolated.py`.
- The successful reports include 15 short multilingual/technical requests, 3 explicitly truncated requests and 3 post-restart requests. Invalid native requests and unapproved token overflow were rejected for every model.
- English, Polish, German, cross-language passages, technical text/code, duplicate text, stable tie ordering and finite identifier/index mapping are covered. No assertion selects the best ranking.
- Offline regressions cover unavailable transport, malformed backend mappings, wrong revisions, startup failure/503, client timeouts, inference timeout/504 and busy/429.
- Mixedbread originally required a forced Docker shutdown (137, no OOM). SIGTERM handling was fixed and its complete inference/restart/stop test reran successfully with exit 0.
- Mixedbread emitted the pinned Transformers SDPA/sliding-window warning; `use_sliding_window=false` in its exact model revision. Long-context inference is not validated.
- TEI CPU forces an effective maximum batch of 4 despite requesting 1. Its 1024 total batch-token budget remains active. Candle approximates GeLU; results can differ numerically from Transformers.
- TEI cannot identify exactly which pairs were truncated. The common client records unknown truncation when it is explicitly permitted.
- Request timeout does not forcibly cancel an already running inference. Mixedbread continues rejecting new work as busy until its worker completes.
- 16 GiB host RAM and the 7.72 GiB Docker budget are insufficient for comfortable simultaneous operation of all models alongside the main LLM. Use one reranker at a time.

Exact model revisions, runtime versions, API usage, commands and cache cleanup are in [README.md](README.md). Per-case scores, rankings, CPU time, memory counters, native info and final container state are in [measurements-20261109.json](measurements-20261109.json).

## Final state

ChromaDB and SearXNG remain running with their original IDs/start times. Horizon remains stopped by the user, with its original ID/start time. All three new rerankers are stopped, attached to `laew_default`, with caches retained. Normal Compose startup still excludes the three profiles.

Changes are confined to `docker-compose.yml` (additive optional services/volumes) and `tools/rerankers/`. No production RAG, Horizon implementation/settings, knowledge data, Chroma collections, primary LLM or embedding server was changed. No Git commit, push, reset or clean was performed.
