# Ornith 1.5 9B: isolated memory sufficiency evaluation (2026-11-06)

## Decision

**B — Keep model assessment optional and continue experimenting.** In the existing configuration, the classifier fails to produce usable JSON on 14 of 16 calls. Fallback preserves evidence coverage, and two successful positive decisions save two searches, but the measured extra inference cost is substantial. These data do not establish reliable semantic classification, nor do they justify enabling it by default. This result describes the exact server/template and assessor configuration, not the inherent capability of the weights.

## Setup and method

The already-running local llama.cpp server at `http://127.0.0.1:8080/v1` listed `Ornith-1.5-9B`, loaded from `Ornith-1.5-9B-IQ4_XS.gguf` (IQ4_XS), with `claude-template.jinja`, context 131072, one slot, and GPU offload. Its OpenAI-compatible chat endpoint responded to a text request. A smoke request with a 16-token output limit returned only reasoning content and hit the limit. The assessor uses temperature 0, max_tokens 64, and the active provider has a 30-second non-streaming timeout; the dedicated provider uses the registry default of 30 seconds. Neither the prompt nor labels were altered. No paid endpoint was used.

The unchanged 24-case validation dataset and existing evaluator were used. The evaluator constructs isolated temporary SQLite Memory and Chroma databases, with deterministic fixture embeddings; it exercises actual routing, FTS recall, RAG and the executor. The Chief adapter returns fixed text: orchestration times do not include real answer generation. Index construction and per-case database setup are excluded from timing. Active and dedicated use the same endpoint, weights and parameters, through distinct configuration paths. Each path was run once, and the active path was repeated with HTTP response capture. These are repeated runs of one model, not different models. Dataset hash and per-case diagnostics are in the original JSON artifact.

## Main comparison

| Metric | Heuristic | Active Ornith |
|---|---:|---:|
| False sufficient / cases requiring RAG | 0/16 (0%) | 0/16 (0%) |
| Unnecessary RAG / memory-sufficient labels | 5/8 (62.5%) | 3/8 (37.5%) |
| Missed evidence / answerable cases | 2/22 (9.1%) | 2/22 (9.1%) |
| Evidence coverage | 20/22 (90.9%) | 20/22 (90.9%) |
| RAG calls | 20 | 18 |
| LLM assessments | 0 | 16 |
| Total orchestration with fixed adapter | 231.30 ms | 26,328.08 ms |
| Classifier tokens | 0 | At least 338 recorded; 14 calls missing usage in primary artifact |

The two cases with no answer are excluded from coverage, but included among 16 needing RAG. One required search was missed in both configurations. The unnecessary-search denominator uses stored-memory labels; recall may not have supplied a usable match. A zero false-sufficient result does not establish model safety: 14 calls failed and the fallback did not trust them. In the dedicated run the metrics and decisions matched active (18 RAG, 16 calls, 14 failures); orchestration was 25,819.59 ms.

For active, assessment time summed to 26,118.8 ms; mean 1,632.4 ms, median 1,637.4 ms and nearest-rank p95 1,899.1 ms (n=16; p95 is the maximum and is unstable). RAG prefetch time summed to 63.6 ms heuristic versus 53.2 ms active. Total measured overhead was 26,096.78 ms for 24 turns, about 1,087 ms per turn, for two fewer searches. This one-hot local fixture is not representative of production RAG latency, and timings include warmup/order and shared-server effects; they are not a production cost forecast.

## Errors, tokens and stability

Active and dedicated each had 14 `JSONDecodeError` outcomes, zero recorded timeout or provider errors, and two valid `true` outcomes (v05 and v19). The assessor omits token counts after parse failure: the 221 prompt and 117 completion tokens in the primary artifact cover only two successful calls and are not the total. A separate instrumented active replay with unchanged inputs captured all 16 HTTP responses: 1,825 prompt and 1,009 completion tokens (2,834 total). This is the measured total for the replay, not a claim of observed tokens for the original pass. The replay yielded the same case statuses and error categories as both original modes. Temperature zero does not guarantee stability beyond these three passes.

In the captured replay, 13 responses hit the output limit: 12 had empty content and one contained only a partial JSON prefix. One more response returned a Markdown-fenced JSON object, rejected by the strict parser. All 16 had a separate reasoning field. The full HTTP capture contains synthetic fixture data. This explains the observed parsing failures in the replay; it does not prove every failed original response had the same form. No valid `false` decision was observed, so semantic performance on partial facts, topical non-answers, negation, stale facts and conflicts remains unmeasured. v02 and v06 are sufficient according to labels but failed parsing and fell back; these are not model judgments of insufficiency. v09's multipart question bypassed the model and fell back heuristically. v07, v08, v10, v11, v16, v18, v22 and v24 similarly fell back after parse errors; no semantic decision can be attributed to the model.

## Pipeline attribution and limitations

Routing did not select Memory or RAG for v20 and v21, so their evidence was missing; v21 accounts for the missed required search. Recall supplied v01's memory but lexical matching was weak, bypassing the assessor and causing RAG. These failures precede model assessment. v05 and v19 were successfully classified sufficient and saved searches. v03 and v04 were judged sufficient by structured heuristics without a model call. The two missing evidence markers were v20 and v21 in both modes.

The labels are single-author, the sample is small and synthetic, fixture embeddings select the expected document, and actual Chief answers were not scored. Latencies and token usage depend on the running server's template, hardware and concurrent load. An independently reviewed held-out corpus, realistic retrieval and actual answer generation are needed before generalization. A future separately recorded experiment could test whether a compatible non-reasoning template or output budget yields parseable decisions, without changing this baseline; compare its false-sufficient errors and end-to-end costs before any default change.

## Validation and artifacts

The evaluator runner, calibration, memory sufficiency unit and integration tests passed: **23 passed**, one dependency deprecation warning. Initial sandbox test setup could not create temporary directories; the successful rerun used an isolated workspace basetemp with appropriate Windows access. The prior baseline was preserved.

- `memory-sufficiency-ornith-20261106.json`: primary heuristic, active and dedicated comparison.
- `memory-sufficiency-ornith-replay-20261106.json`: independent repeated active comparison.
- `memory-sufficiency-ornith-replay-http-20261106.json`: request/response capture for replay, including token usage.
- `memory-sufficiency-ornith-capture-20261106.py`: one-off capture script using the existing evaluator.
