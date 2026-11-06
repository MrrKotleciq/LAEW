# Memory Sufficiency: Isolated Validation (2026-11-05)

## Question and status

The available evidence does not establish whether model assessment is worth its
extra inference. Neither an active local Chief model nor a separate local model
could be verified. The manifest names llama.cpp on `127.0.0.1:8080`; requests to
its model catalog and the Ollama catalog on `127.0.0.1:11434` were blocked in
the sandbox and timed out in a separate local check. This does not prove that
no models exist. No servers were started, models downloaded, or paid APIs used.

Until a real-model comparison is available, keep model assessment disabled and
retain conservative RAG fallback. This is a provisional decision, not a finding
that classifiers cannot improve results.

## Data and method

The 24 hand-labeled cases in `tests/evaluation/memory_sufficiency/validation.json`
include eight where the stored memory is labeled sufficient and sixteen that
need an independent Global search, including two where no answer exists in the
corpus. Topics include natural-language answers, structured values, missing or
partial facts, stale and conflicting records, topical non-answers, multi-part
questions and Polish/English formulations. They were written separately from
the previous 23-case assessment corpus, which remains a development set; both
are small, synthetic, and contain conceptually related examples. Labels are
single-author judgments, not independently adjudicated ground truth.

The evaluator creates disposable SQLite Memory databases and a persistent Chroma
index under a newly created temporary workspace directory, indexes one synthetic
Global note per case, and deletes that directory at exit. It exercises the real
Memory FTS recall, `KnowledgeTurn`, real `RagTool`, source routing and executor.
It uses deterministic one-hot fixture embeddings that select the intended
Global document; this is not a real embedding model or a realistic retrieval
quality benchmark. An observing adapter emits a fixed response, so no Chief
answer correctness or real model inference was measured. Timing covers
`prepare` and the executor through the fixed adapter; index creation, per-case
SQLite construction and real answer generation are excluded. It is a single
pass without warmup control, not a production latency benchmark.

Command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m laew.eval.memory_sufficiency_eval --output docs/reports/memory-sufficiency-validation.json
```

For a verified, already-running *local llama.cpp* model, add
`--active-model MODEL_ID --active-url http://127.0.0.1:8080`. For a separate
already-running server/model, add `--dedicated-model MODEL_ID --dedicated-url
http://127.0.0.1:PORT`. The model ID must be present in the server's catalog.
The evaluator rejects non-loopback endpoints, never starts a server and skips a
configuration when its model is unspecified or unavailable. Active and
dedicated differ in configuration path; the fixed answer adapter does not call
Chief. Ollama is not yet supported by this evaluator. Details and dataset hash
are retained in `docs/reports/memory-sufficiency-validation-20261105.json`.

## Results

| Metric | Heuristic | Active | Dedicated |
|---|---:|---:|---:|
| Cases | 24 | not run | not run |
| False sufficient / needed RAG | 0/16 | not measured | not measured |
| Unnecessary RAG / memory-sufficient labels | 5/8 | not measured | not measured |
| Needed RAG not executed | 1/16 | not measured | not measured |
| Evidence marker covered | 20/22 | not measured | not measured |
| RAG / classifier calls | 20 / 0 | not measured | not measured |
| Total retrieval time | 107.2 ms | not measured | not measured |
| Total end-to-end time, fixed adapter | 404.48 ms | not measured | not measured |
| Classifier tokens | 0 | not measured | not measured |

The evidence denominator excludes the two explicitly unanswerable cases. The
false-sufficient denominator includes all cases labeled as needing RAG; 0/16
must not be interpreted as a real-model error estimate. Missing required RAG
and missing evidence are separate: source selection can fail before Memory
assessment. The 5/8 count is relative to memory contents as labeled; some
searches compensate for FTS failing to recall the available fact, so the count
is not a claim that every search was avoidable given the supplied context.

`v20` (Polish question about a novel) was not routed to Memory or RAG; its
answer was consequently not supplied. `v21` (who has a camera) was likewise
not routed and the needed Global evidence was missing. `v01` did invoke Memory
and RAG, but lexical recall was assessed weak because the inflected form in
Memory did not match the content words of the question. These are observations
about the entire routing/recall pipeline, not classifier judgments. No routing,
retrieval or classifier policy was changed in response.

## What remains

Run both local model configurations on these exact data and an additional
independently reviewed held-out set, record errors and token usage, and compare
classification time plus subsequent retrieval against heuristic retrieval.
Measure real Chief answers and production-representative retrieval separately.
False-sufficient decisions require manual review and should weigh more heavily
than reducing RAG calls. Test results using stubs validate orchestration and
fallback only; they cannot justify a classifier quality or cost claim.

## Regression

The isolated evaluation harness, classifier unit tests, both recall integration
paths, knowledge routing and multi-turn tests completed with **141 passed and
1 skipped**. These include stubbed classifier error/fallback and source-policy
checks. They do not constitute a browser visual check or a real-model test.
