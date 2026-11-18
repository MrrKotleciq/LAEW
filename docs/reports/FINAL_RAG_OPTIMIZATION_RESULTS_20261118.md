# Final RAG optimization results

2026-11-18 · Both independent experiments completed · **NO-GO for both**

Retain Production A and conclude this RAG optimization cycle. The two changes found more K10 pools with complete registered evidence than C, but each delivered fewer complete contexts at the fixed budget. Neither gained a majority-complete family relative to C. No answer generation or deployment was performed.

## Controlled retrieval and delivery

The same 60 exposed multilingual questions, 48 answerable variants and 20 dependent families were used. Controls B and C are the restriction-audited Chroma rebuilds. Their complete-pool and complete-delivery counts reproduce historical B/K10 and C/K10. All arms used unchanged cached query vectors, Chroma 1.5.9 cosine, K10, threshold 0.30, ranked fill, a 1,000-estimated-token Global scope and an 8,000-token wrapper budget. Selection and traces were sealed before rubric v2.1 was read. Contextual changed only C's document-side embedding input. Adaptive changed fragment boundaries and used exact unaugmented body inputs. The two techniques were never combined.

| Arm | Candidate complete / 48 | Delivered complete / 48 | Macro evidence recall, raw / delivered | Majority-complete / all three languages, of 16 families | Delivered complete Prusa / Pro Git / PostgreSQL |
|---|---:|---:|---:|---:|---:|
| Matched B | 21 | 13 | 53.99% / 39.93% | 4 / 4 | 0 / 9 / 4 |
| Matched C | 21 | 18 | 55.56% / 42.53% | 6 / 4 | 5 / 9 / 4 |
| Adaptive | 22 | 15 | 53.99% / 44.44% | 4 / 4 | 2 / 9 / 4 |
| Contextual | 24 | 14 | 58.33% / 38.19% | 4 / 3 | 4 / 6 / 4 |

No completeness or macro recall differences arose between raw and threshold-eligible stages. The C two-document ceiling of 42/48 remains historical accessibility only. All metrics are registered-proof diagnostics on the already exposed development questions. Translations are paired observations of the same intents. This does not establish answer quality or 90% real-world performance.

| Comparison | Newly complete delivered variants | Previously complete variants lost |
|---|---|---|
| Adaptive vs B | S01-en, S05-en | None |
| Adaptive vs C | S05-en | S06-pl/de, S08-en/pl |
| Contextual vs B | S01-en, S06-de, S08-en/de | S03-en/pl/de |
| Contextual vs C | S08-de | S03-en/pl/de, S06-pl, S08-pl |

**Adaptive.** The S05-en gain recovers the verified MK4S rev. 1.01 electrical and environmental ranges. Every S06/S08 complete-context loss versus C still has a complete eligible pool. Ranked fill leaves out the MK4 rev. 1.03 firmware media requirement or the MINI+ rev. 1.09 diagnostic step. S06 and S08 lose majority completeness. Improved partial evidence and a smaller index do not offset the delivery regressions. **NO-GO.**

**Contextual.** The S08-de gain retrieves the correct MINI+ triage span, but S08-pl loses that span during discovery. The three S03 variants still retrieve sufficient candidate evidence, then lose all or part of the registered Windows or Linux/macOS guidance for `core.autocrlf` during delivery. S06-pl drops the MK4 self-test and firmware media conditions. S03 and S06 lose majority completeness. The reduction in other-target material does not offset these losses. **NO-GO.**

The external comparison package records every per-question candidate and delivery change for both controls, plus all registered method and requirement transitions, target flags, source identifiers and offset-bearing retrieval traces. The source review above uses the exact registered source excerpts for every complete-context change against C. Alternative wording or procedures beyond the registry have no independent domain adjudication.

## Warnings, versions and restrictions

| Arm | Critical requirements covered / active, selected best method | Conditional requirements covered / active, selected best method | Explicit other-target documents in raw / delivered contexts |
|---|---:|---:|---:|
| Matched B | 39/105 | 3/3 | 28 / 23 |
| Matched C | 37/105 | 3/3 | 22 / 15 |
| Adaptive | 41/105 | 3/3 | 27 / 20 |
| Contextual | 35/106 | 4/4 | 18 / 11 |

The contextual best method changes one conditional denominator. Comparing identical per-question methods against C, adaptive gains eight critical proof instances and loses four. Contextual gains two and loses four, including the MMU firmware path for S11-de. The paired ledger records partial-to-full and full-to-partial changes as well as missing evidence.

Other-target flags are document-level and only use explicit target hardware in eight families or PostgreSQL 17 versus PG11 documentation in two families. The denominator is a count of affected variants, with 30 eligible to be flagged. Other-target passages can sometimes supply shared or historical information. The diagnostic excludes generic cross-printer accessory documents and version-transition notes, and does not label a generated answer as wrong. Contextual keeps 11 affected deliveries, including an MK4S document for S06-de targeting MK4. Adaptive introduces PG11 documentation into three PG17 S04 deliveries. Exact copied and adaptive source offsets bind to normalized source hashes, revisions and the frozen source maps.

All ten declared restrictions, including their related-context ranges, were preserved. There were zero restricted ranges in either variant's index or raw, eligible and delivered contexts. Inherited unresolved source-layout risks remain, including 329 uninspected High findings. No source, label, corpus file, production index or historical cache identity was changed.

## Cost and reproducibility

| Arm | Indexed fragments | Built disk MiB | Build seconds | Warm K10 p50 / p95 ms | Render p50 / p95 ms | Delivered context p50 / p95 estimated tokens |
|---|---:|---:|---:|---:|---:|---:|
| Matched B | 2,152 | 21.77 | 2.21 | 13.49 / 14.38 | 0.16 / 0.25 | 932 / 996 |
| Matched C | 2,161 | 26.19 | 2.72 | 15.87 / 20.07 | 0.20 / 0.29 | 942 / 995 |
| Adaptive | 1,759 | 16.32 | 1.93 | 13.05 / 15.07 | 0.17 / 0.23 | 928 / 988 |
| Contextual | 2,161 | 26.20 | 2.94 | 17.71 / 19.94 | 0.21 / 0.32 | 939 / 988 |

Each arm uses 60 warm local searches, excluding embeddings. These single-run timings describe the workstation and embedded Chroma. No experimental delivery exceeded the budget or clipped a fragment. All 120 primary-run K10 memberships agreed with direct float64 cosine. Maximum absolute score discrepancies were below 8e-7. An offline fresh rebuild reproduced all selected traces and both score ledgers byte-for-byte. It changed two adaptive raw and eligible memberships. P02-de swapped two distinct source IDs tied on the score at the boundary. S15-pl returned one result below the exact cutoff by 0.00038935. Neither change affected delivered content or any registered outcome. Both native traces are preserved.

| Workload, in execution order | Unique new vectors | Embedding requests | Reported input tokens | Sum of request times |
|---|---:|---:|---:|---:|
| Adaptive | 1,307 | 333 | 277,513 | 59.55 s |
| Contextual | 2,161 | 662 | 647,829 | 130.75 s |
| Total | 3,468 | 995 | 925,342 | 190.29 s |

Total dispatch to completion took 201.39 seconds including ledger overhead. Confirmed model SHA-256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`, Q8_0, 1,024 dimensions, last pooling and L2 normalization. Actual CUDA launch used `CUDA0`, `--gpu-layers all`, two slots, 16,384 total context and 1,024 batch and microbatch. GPU activity was visible with 76–83% utilization in the sampled windows and about 3.6 GiB free. These readings are device-wide samples. The build fails oversized non-splittable inputs rather than clipping. Every accepted POST returned complete indexed vectors and input-only usage. No retries, CPU fallback or extra inference probes. The prior cache remained under its original identity. [Pinned llama.cpp oversized-input handling](https://github.com/ggml-org/llama.cpp/blob/1e6f04a75/tools/server/server-context.cpp#L3243-L3272)

Reproduce retrieval and scoring offline from the sealed vectors with `reproduce-results.ps1` in the study package. The package includes input and output hashes, request ledger, manifests, exact ranked traces, score deltas and Git status. Use the isolated tests and a new external output folder. The model receipt's `created` catalog field differs from the historical catalog. GGUF identity, build and settings were independently checked without rekeying the historical cache.

Focused verification produced 55 passes and three skips via `scripts/run_isolated.py`. GPT-6.1 Terra was requested for the narrow contract-test task in the preflight and the read-only target applicability review in the authorized stage. The tool accepted the model override and independent worker-runtime attestation was unavailable. The coordinator verified the assessment against the frozen metadata. GPT-6 Luna was unavailable for Codex delegation. There were zero ChatGPT OAuth or other answer-model requests.
