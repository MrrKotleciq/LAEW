# Stage 2B.2 — Multilingual reranker quality benchmark

Experiment started 2026-11-09 (Europe/Warsaw).

**Recommendation D — no auxiliary reranker yet. Pending user review; no production integration or default change.**

The experiment reuses the existing frozen RAG evaluator, production context renderer and adapter replay. All scores use captured fixture candidates; no private production corpus, production Chroma collection, paid API or real chat-model inference was used.

## Decision proposed for review

Retain the current legacy/cosine production behavior and automatic prefetch limit of two fragments and 500 estimated tokens per scope. Do not enable a learned reranker, switch chunking defaults, increase production K, or adopt the budget-fill diagnostic on this evidence. The experimental K=20/1000 condition is a comparison setting, not a proposed production default.

BGE/legacy has the strongest independent point estimate (+12.50 percentage points of final atom coverage, complete evidence 71.43% to 85.71%), but the six-component uncertainty interval includes zero, the corrected sign-test p is 1.0, and legacy K=20 adds 27.74 seconds median CPU serving time. Its working cgroup reached the existing 4 GiB limit without an OOM. It also loses half the evidence in frozen h03. This is promising exploratory evidence, insufficient to justify option B for routine interactive requests.

GTE costs less (+12.44 seconds median at legacy K=20) and repairs structure-v2 h11, but independent complete-evidence coverage for structure-v2 remains 75%, and it regresses u21/u26 and frozen cases. Mixedbread passes real inference, but fails the predeclared latency gate at K=10; its quality is unknown. There is no basis to select it or to claim it ranks worse.

Structure-v2 benefits more on the known hard cases with GTE; the independent holdout shows a larger coverage gain on legacy for both tested rerankers. No chunker/reranker pairing has established a general advantage. A follow-up should use a larger independently judged, naturally sampled engineering holdout and actual answer evaluation before any default change.

## Design and provenance

The independent holdout was labeled before reranker scoring and kept separate from the previous development/validation cases. Its public-document paraphrases and fictional runbooks are not an expert-blind sample of industrial production questions. Treat its uncertainty estimates as exploratory and do not switch defaults solely on these authored fixtures.


| Dataset | Queries | Answered | Multi-document | Languages | Legacy chunks G/P | V2 chunks G/P |
|---|---|---|---|---|---|---|
| baseline_v1 | 28 | 24 | 4 | en, pl | 15/1 | 15/1 |
| hard_cases_v1 | 13 | 11 | 1 | en, pl | 33/1 | 25/1 |
| reranker_holdout_v1 | 32 | 28 | 7 | de, en, pl | 52/6 | 37/4 |

Captured-pool SHA-256: `4cfc7e69ae22712ec12c84318b14efb55cb1f2523d6a91074227a34ab8b87610`.

K=10 and K=20 are separate Chroma searches **per scope**, independent of final fragment count. The small baseline contains only 15 global chunks, so its K=20 condition means 15 actual candidates. All methods use the same pools and the unchanged cosine >=0.3 eligibility filter. K=20 is split into calls of at most 16 documents. Pointwise scores are reused for the K=10 subset; timing probes bypass caches.

Primary policy is top two ranked fragments per scope, at 500/1000/5000 chars/4 estimated tokens. A separate budget-fill diagnostic feeds the full ordered pool to the unchanged renderer. It is not a production policy change. Hybrid MRR/nDCG are averaged over evidence-bearing scope rankings rather than merging unrelated scope scores.

Coverage, MRR and nDCG are macro-averaged over answerable queries. Complete evidence requires every labeled atom. Mean context-token costs include no-answer queries; empty-selection rate is reported separately. Source relevance grades are fixed labels, not calibrated reranker probabilities.


| Model | Pinned revision | Backend |
|---|---|---|
| gte | 8215cf04918ba6f7b6a62bb44238ce2953d8831c | tei-cpu-1.9.4 |
| bge | 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e | tei-cpu-1.9.4 |
| mxbai | 3ea9d4dffa7d12a4f366be8e275c349de9fc9865 | mxbai-rerank-0.1.6/torch-2.6.0+cpu |


## Candidate availability


| Dataset | Chunker | Doc recall K10 | Doc recall K20 | Raw atom coverage K10 | Raw atom coverage K20 | Eligible atom coverage K20 |
|---|---|---|---|---|---|---|
| baseline_v1 | legacy | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| baseline_v1 | structure-v2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| hard_cases_v1 | legacy | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| hard_cases_v1 | structure-v2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |
| reranker_holdout_v1 | legacy | 100.00% | 100.00% | 96.43% | 100.00% | 100.00% |
| reranker_holdout_v1 | structure-v2 | 100.00% | 100.00% | 100.00% | 100.00% | 100.00% |

Rerankers cannot improve candidate recall for a fixed pool. Higher K can change availability; ranking changes which available atoms survive selection.

| Holdout chunker | Method | Final coverage K10 / K20 | Complete evidence K10 / K20 |
|---|---|---|---|
| legacy | cosine | 80.36% / 80.36% | 71.43% / 71.43% |
| legacy | gte | 88.10% / 88.10% | 78.57% / 78.57% |
| legacy | bge | 91.07% / 92.86% | 82.14% / 85.71% |
| structure-v2 | cosine | 82.74% / 82.74% | 75.00% / 75.00% |
| structure-v2 | gte | 88.10% / 88.10% | 75.00% / 75.00% |
| structure-v2 | bge | 89.29% / 89.29% | 82.14% / 82.14% |

Increasing K supplies the previously absent calibration record atom for legacy u22 and timing atom for u24, but only BGE's aggregate final coverage improves (91.07% to 92.86%). GTE/cosine do not automatically deliver the newly available atom. In this fixture, structure-v2 K=10 already contains all labeled atoms. K=20 serving costs still increase substantially.

## Frozen regression quality


| Dataset | Chunker | Method | MRR | nDCG | Final atom coverage | Complete evidence | Mean context tokens |
|---|---|---|---|---|---|---|---|
| baseline_v1 | legacy | cosine | 0.931 | 0.945 | 81.25% | 75.00% | 99.3 |
| baseline_v1 | legacy | gte | 0.979 | 0.982 | 91.67% | 83.33% | 100.2 |
| baseline_v1 | legacy | bge | 0.972 | 0.978 | 91.67% | 87.50% | 99.6 |
| baseline_v1 | structure-v2 | cosine | 0.917 | 0.938 | 91.67% | 87.50% | 99.0 |
| baseline_v1 | structure-v2 | gte | 0.979 | 0.982 | 91.67% | 83.33% | 100.5 |
| baseline_v1 | structure-v2 | bge | 0.972 | 0.978 | 91.67% | 87.50% | 100.8 |
| hard_cases_v1 | legacy | cosine | 1.000 | 1.000 | 86.36% | 72.73% | 162.8 |
| hard_cases_v1 | legacy | gte | 0.955 | 0.966 | 87.88% | 72.73% | 280.9 |
| hard_cases_v1 | legacy | bge | 1.000 | 1.000 | 90.15% | 72.73% | 282.9 |
| hard_cases_v1 | structure-v2 | cosine | 1.000 | 1.000 | 92.42% | 81.82% | 242.2 |
| hard_cases_v1 | structure-v2 | gte | 0.955 | 0.966 | 100.00% | 100.00% | 279.8 |
| hard_cases_v1 | structure-v2 | bge | 1.000 | 1.000 | 92.42% | 81.82% | 315.5 |

Tables use K=20, top2 and 1000 tokens per scope unless stated otherwise. The cosine 500-token control reproduces the previous Stage 2B.2 prefetch coverage (81.25/91.67% baseline and 86.36/92.42% hard, legacy/v2). All 82 frozen query/chunker controls match the historical per-query coverage and estimated context-token counts exactly.

## Independent holdout: ranking and final evidence


| Chunker | Method | Doc MRR | Doc nDCG | Atom rank RR | Final coverage | Complete | Multi-doc coverage | One-doc complete | Cross-language coverage |
|---|---|---|---|---|---|---|---|---|---|
| legacy | cosine | 0.938 | 0.956 | 0.763 | 80.36% | 71.43% | 57.14% | 85.71% | 78.57% |
| legacy | gte | 0.929 | 0.937 | 0.775 | 88.10% | 78.57% | 59.52% | 95.24% | 79.76% |
| legacy | bge | 0.946 | 0.956 | 0.840 | 92.86% | 85.71% | 78.57% | 95.24% | 89.29% |
| structure-v2 | cosine | 0.903 | 0.927 | 0.834 | 82.74% | 75.00% | 59.52% | 90.48% | 69.05% |
| structure-v2 | gte | 0.964 | 0.960 | 0.823 | 88.10% | 75.00% | 59.52% | 95.24% | 79.76% |
| structure-v2 | bge | 0.973 | 0.976 | 0.855 | 89.29% | 82.14% | 78.57% | 90.48% | 82.14% |

Document ranks use the frozen graded source labels in first-hit document order. Atom rank RR is the mean reciprocal position of each required passage. These describe ranking; final/complete coverage describe selected evidence. Neither is generated-answer accuracy.

## Paired independent uncertainty and regressions


| Chunker | Method | Coverage delta | Cluster bootstrap 95% CI | Components | Exact cluster sign p | Holm p | Regressed queries |
|---|---|---|---|---|---|---|---|
| legacy | bge | +12.50 pp | +0.00 to +17.07 pp | 6 | 0.500 | 1.000 | none |
| legacy | gte | +7.74 pp | +0.00 to +11.74 pp | 6 | 0.500 | 1.000 | u21 |
| structure-v2 | bge | +6.55 pp | +0.00 to +17.46 pp | 6 | 1.000 | 1.000 | u08 |
| structure-v2 | gte | +5.36 pp | +0.00 to +14.29 pp | 6 | 1.000 | 1.000 | u26 |

The bootstrap resamples connected components of shared evidence sources/topics, not independent-looking translations as separate observations. There are only six independent holdout components; intervals and p-values have low power. Holm correction covers the primary model/chunker comparisons. All other condition comparisons are exploratory. Full query deltas and single-document/ranking regressions are in the summary JSON and query CSV.
The independent regressions occur before the context budget: GTE/legacy u21 moves the required R3 contract to rank 5 and selects an R2 simulator passage; GTE/v2 u26 ranks the approved S8 configuration third in project scope behind archived/release material. BGE/v2 u08 moves the German INI DEFAULT/override passage from rank 1 to rank 3 (100% to 0% exact-atom coverage). BGE/legacy has no holdout coverage regression, while its document nDCG regresses on u23/u26/u28. These source/section errors explain why document MRR alone is insufficient.

## The requested 5000-token budget


| Chunker | Method | Top2 coverage 500/1000/5000 | Fill coverage 500 | Fill coverage 1000 | Fill coverage 5000 | Mean fill tokens @1000 / @5000 |
|---|---|---|---|---|---|---|
| legacy | cosine | 80.36% / 80.36% / 80.36% | 91.07% | 94.64% | 100.00% | 986.2 / 1642.9 |
| legacy | gte | 88.10% / 88.10% / 88.10% | 89.88% | 98.21% | 100.00% | 990.5 / 1642.9 |
| legacy | bge | 92.86% / 92.86% / 92.86% | 92.86% | 100.00% | 100.00% | 992.2 / 1642.9 |
| structure-v2 | cosine | 82.74% / 82.74% / 82.74% | 89.88% | 96.43% | 100.00% | 973.3 / 2308.8 |
| structure-v2 | gte | 88.10% / 88.10% / 88.10% | 89.88% | 97.02% | 100.00% | 968.1 / 2308.8 |
| structure-v2 | bge | 89.29% / 89.29% / 89.29% | 94.64% | 100.00% | 100.00% | 965.2 / 2308.8 |

A larger budget does not remove the top2 limit. The full-pool 5000-token diagnostic measures an evidence ceiling, not a recommendation to deliver all candidates. Actual fixture contexts may remain below 5000 tokens; no synthetic padding was added. Hybrid 5000-per-scope configurations can in principle exceed the manifest's 8000-token RAG allocation. Tokenizer-exact prompt costs and real LLM prefill/generation latency were not measured.

## h11 and the known hard regressions


| Chunker | Method | h11 atom ranks | Coverage 500 /1000 /5000 | Loss stage @1000 | Fill5000 coverage |
|---|---|---|---|---|---|
| legacy | cosine | [2, 1] | 100.00% / 100.00% / 100.00% | delivered_to_adapter, delivered_to_adapter | 100.00% |
| legacy | gte | [1, 2] | 100.00% / 100.00% / 100.00% | delivered_to_adapter, delivered_to_adapter | 100.00% |
| legacy | bge | [2, 1] | 100.00% / 100.00% / 100.00% | delivered_to_adapter, delivered_to_adapter | 100.00% |
| structure-v2 | cosine | [3, 1] | 50.00% / 50.00% / 50.00% | ranked_below_selection_limit, delivered_to_adapter | 100.00% |
| structure-v2 | gte | [2, 1] | 100.00% / 100.00% / 100.00% | delivered_to_adapter, delivered_to_adapter | 100.00% |
| structure-v2 | bge | [6, 1] | 50.00% / 50.00% / 50.00% | ranked_below_selection_limit, delivered_to_adapter | 100.00% |


| Query | Chunker | cosine coverage @500 / @1000 | gte coverage @500 / @1000 | bge coverage @500 / @1000 |
|---|---|---|---|---|
| h04 | legacy | 33.33% / 33.33% | 33.33% / 100.00% | 66.67% / 100.00% |
| h04 | structure-v2 | 66.67% / 66.67% | 66.67% / 100.00% | 100.00% / 100.00% |
| h05 | legacy | 66.67% / 66.67% | 66.67% / 66.67% | 66.67% / 66.67% |
| h05 | structure-v2 | 100.00% / 100.00% | 100.00% / 100.00% | 66.67% / 66.67% |
| h09 | legacy | 50.00% / 50.00% | 50.00% / 50.00% | 75.00% / 75.00% |
| h09 | structure-v2 | 100.00% / 100.00% | 100.00% / 100.00% | 100.00% / 100.00% |

Both learned rerankers regress frozen legacy h03 from complete to 50% coverage: the actuator-disconnection/backup prerequisite moves from rank 1 to GTE rank 4 / BGE rank 3, while a second procedural fragment consumes the other top2 slot. BGE/v2 h05 moves the sensor-02 table fragment to rank 3, losing one of three atoms despite perfect document-level MRR/nDCG. Neither loss is fixed by a larger top2 budget. On baseline_v1, GTE regresses q21 (legacy) and q21/q22 (v2); BGE regresses the single-document q09 on v2. No hardcoded repair, diversity filter or threshold was added after observing these cases.

## Warm serving performance and cold behavior

The h03 development workload uses real retrieved passages from both chunkers at raw K=5/10/20. GTE/BGE have ten warm repetitions after a first/warmup request per condition. p95 with n=10 is descriptive. The primary GTE series was repeated after the user freed memory; original pressure-affected samples are preserved in the GTE quality artifact.


| Model | Chunker | Candidates | Warm n | Request p50 / p95 seconds | POST phase p50 / p95 seconds | Native diagnostic p50 / p95 seconds | Passage min/mean/max or skip |
|---|---|---|---|---|---|---|---|
| gte | legacy | 5 | 10 | 2.07 / 2.13 | n/a / n/a | 1.09 / 1.13 | 10/276/941 chars |
| gte | legacy | 10 | 10 | 4.93 / 5.00 | n/a / n/a | 1.86 / 1.88 | 10/358/964 chars |
| gte | legacy | 20 | 10 | 12.44 / 12.71 | n/a / n/a | 2.76 / 2.81 | 7/408/1000 chars |
| gte | structure-v2 | 5 | 10 | 2.30 / 2.33 | n/a / n/a | 1.19 / 1.20 | 100/671/968 chars |
| gte | structure-v2 | 10 | 10 | 5.78 / 5.85 | n/a / n/a | 1.58 / 1.60 | 86/507/1000 chars |
| gte | structure-v2 | 20 | 10 | 15.86 / 16.59 | n/a / n/a | 3.73 / 3.92 | 58/658/1000 chars |
| bge | legacy | 5 | 10 | 4.50 / 4.66 | 4.50 / 4.64 | 2.35 / 2.44 | 10/276/941 chars |
| bge | legacy | 10 | 10 | 10.80 / 11.06 | 10.80 / 11.06 | 4.06 / 4.16 | 10/358/964 chars |
| bge | legacy | 20 | 10 | 27.74 / 28.28 | 27.73 / 28.27 | 6.15 / 6.30 | 7/408/1000 chars |
| bge | structure-v2 | 5 | 10 | 5.01 / 5.17 | 5.01 / 5.16 | 2.57 / 2.64 | 100/671/968 chars |
| bge | structure-v2 | 10 | 10 | 12.79 / 13.05 | 12.79 / 13.04 | 3.48 / 3.56 | 86/507/1000 chars |
| bge | structure-v2 | 20 | 10 | 33.90 / 35.69 | 33.89 / 35.67 | 8.04 / 8.45 | 58/658/1000 chars |
| mxbai | legacy | 5 | 3 | 7.08 / 7.69 | 7.07 / 7.68 | 7.06 / 7.67 | 10/276/941 chars |
| mxbai | legacy | 10 | 3 | 15.39 / 15.43 | 15.38 / 15.42 | 15.36 / 15.40 | 10/358/964 chars |
| mxbai | legacy | 20 | 0 | unmeasured | unmeasured | unmeasured | predeclared performance stop rule |
| mxbai | structure-v2 | 5 | 0 | unmeasured | unmeasured | unmeasured | predeclared performance stop rule |
| mxbai | structure-v2 | 10 | 0 | unmeasured | unmeasured | unmeasured | predeclared performance stop rule |
| mxbai | structure-v2 | 20 | 0 | unmeasured | unmeasured | unmeasured | predeclared performance stop rule |

The GTE timing process loaded the evaluator before POST-stage instrumentation was added; missing values are unmeasured, not zero. The shared client's end-to-end request boundary remains comparable. TEI 1.9.4 averages per-pair durations in `x-inference-time`; adding two split-call header values is diagnostic and is not whole-pool compute time. Mixedbread's native timing covers its scoring loop. Raw headers/calls are retained; do not compare these native values as identical latency units. See [the pinned TEI implementation](https://github.com/huggingface/text-embeddings-inference/blob/v1.9.4/router/src/http/server.rs).


| Model | Observed cgroup RAM peak | Observed Docker CPU peak | Evaluator readiness wait | First benchmark request seconds | Minimum host free RAM in probes | Recorded errors |
|---|---|---|---|---|---|---|
| gte | 2.195 GiB | 201.990% | 12.03s | 2.13 | 2.975 GiB | 0 |
| bge | 4.000 GiB | 202.350% | 21.08s | 4.60 | 0.558 GiB | 0 |
| mxbai | 3.640 GiB | 202.120% | 9.08s | 7.37 | 0.496 GiB | 0 |

CPU peaks are sampled, not cycle-level maxima. GTE/BGE streaming collection initially ignored terminal-control prefixes; bounded fallback samples and request-window CPU averages are retained. Cgroup memory includes file cache and is capped by the unchanged 3/4/4 GiB quotas; Docker stats excludes inactive file cache. These are cached-process starts, not fresh model downloads. GTE/BGE use two CPU quotas with no GPU allocation.

GTE's clean-repeat cgroup peak is 1.564 GiB (2.195 GiB including the original pressured lifecycle); the bounded Docker working-set samples reach 1.503 GiB for GTE and 2.451 GiB for BGE. BGE/Mixedbread probes ran with as little as 0.558/0.496 GiB free host RAM. These measurements describe this 16 GiB workstation under its actual load, not an equal-memory-headroom laboratory. No swap/page-fault profiling establishes how much low host headroom contributed to their latency. Docker Desktop remains at 8290385920 bytes and 16 logical CPUs; per-model quotas remain two CPUs and 3/4/4 GiB. The reranker's effective input ceiling is 1024 tokens and 16 documents per HTTP call; no successful benchmark call truncated inputs. This does not characterize the models at their larger architectural context limits.

**Mixedbread quality is unmeasured:** Mixedbread predeclared stop: warm configuration median >10s (starting with K=5), or a failed/deadline-exceeded probe; larger/quality workloads not extrapolated. No quality scores or larger-K latencies are inferred from the pilot.

## Evidence losses, irrelevant fragments and adapter delivery


| Chunker | Method | Loss-stage counts @top2/1000 | No-atom fragments | Qrel-irrelevant documents | Overlapping fragments | No-answer empty rate |
|---|---|---|---|---|---|---|
| legacy | cosine | {'delivered_to_adapter': 37, 'ranked_below_selection_limit': 9} | 40 | 20 | 0 | 0.00% |
| legacy | gte | {'delivered_to_adapter': 39, 'ranked_below_selection_limit': 7} | 38 | 18 | 0 | 0.00% |
| legacy | bge | {'delivered_to_adapter': 42, 'ranked_below_selection_limit': 4} | 35 | 17 | 0 | 0.00% |
| structure-v2 | cosine | {'delivered_to_adapter': 36, 'ranked_below_selection_limit': 10} | 40 | 28 | 0 | 0.00% |
| structure-v2 | gte | {'delivered_to_adapter': 39, 'ranked_below_selection_limit': 7} | 38 | 20 | 0 | 0.00% |
| structure-v2 | bge | {'delivered_to_adapter': 40, 'ranked_below_selection_limit': 6} | 36 | 19 | 0 | 0.00% |

All-context adapter replay: 5256/5256 configurations. The real AgentExecutor and llama.cpp serializer received the selected attributed context; network transport/model response were mocked. This verifies delivery, not a correct generated answer. Empty-selection rates are not refusal accuracy; no model-specific abstention threshold was introduced. A no-atom fragment contains no labeled exact atom, and a qrel-irrelevant document has no positive source label; either can still contain an unjudged paraphrase. The >80% token-set overlap count is a diagnostic, not a diversity filter.

## Operational cost and limitations

For a knowledge-prefetch request, the measured reranker latency is additional to embedding, Chroma retrieval and LLM generation. A hybrid turn runs separate scopes; two equally full scopes would approximately add their serving times, but this is an estimate rather than a measured chat turn. Larger context budgets can supply more prompt tokens without any reranker, but add unmeasured LLM prefill/context cost. Keeping a service warm retains its RAM; starting on demand adds cached initialization. No paid inference or GPU memory was used by the rerankers.

The holdout is small, authored and correlated; exact-passage labels miss equivalent unlabeled paraphrases. No generated-answer evaluation, full routing replay, production-corpus test, real tokenizer prompt cost, or long-context model-input experiment was performed. Do not equate candidate recall, document MRR, adapter delivery, or a repaired h11 case with reliable complete answers. The source and model revisions remain pinned; no thresholds or per-query exceptions were tuned.

| Added warm serving cost per populated scope | Legacy K10 / K20 | Structure-v2 K10 / K20 |
|---|---|---|
| gte | 4.93 s / 12.44 s | 5.78 s / 15.86 s |
| bge | 10.80 s / 27.74 s | 12.79 s / 33.90 s |

For two equally full K=20 scopes, adding their measured medians gives an estimated 24.9–31.7 seconds for GTE or 55.5–67.8 seconds for BGE before the normal retrieval/generation costs. Actual project pools may be much smaller. The 5000-token fill diagnostic attains 100% atom coverage for cosine on both chunkers and all three datasets; this is a possible evidence-selection investigation, not evidence that adding that context improves generated answers.

## Artifacts, checks and final state


| Model | Last cached container-start to Ready log |
|---|---|
| gte | 17.02 s |
| bge | 21.91 s |
| mxbai | 9.78 s |

These container-start intervals include initialization before the evaluator starts polling; they differ from the evaluator's readiness-wait intervals above. They exclude any image build/pull command.

All three model containers ended stopped, exit 0, OOMKilled=false. ChromaDB and SearXNG remain running; Horizon remains stopped as requested by the user. Their container IDs, StartedAt values and states match the pre-benchmark snapshot. No global Docker limits, existing service settings, model revisions or inference dependencies changed during this quality task.

- [Machine-readable summary](reranker-quality-20261109-summary.json), [summary CSV](reranker-quality-20261109-summary.csv), [per-query CSV](reranker-quality-20261109-queries.csv).
- [Full candidate metadata/text](reranker-quality-20261109-candidates.json.gz) and [all configuration diagnostics](reranker-quality-20261109-details.json.gz), compressed JSON. These contain fixture data only.
- Raw model files: [reranker-quality-20261109-gte.json](reranker-quality-20261109-gte.json), [reranker-quality-20261109-gte-performance.json](reranker-quality-20261109-gte-performance.json), [reranker-quality-20261109-bge.json](reranker-quality-20261109-bge.json), [reranker-quality-20261109-mxbai.json](reranker-quality-20261109-mxbai.json).
- [Protocol and reproduction commands](../../tools/rerankers/BENCHMARK_PROTOCOL.md).
- [Final Docker/Git/test snapshot](reranker-quality-20261109-final-state.json); relevant tests through `scripts/run_isolated.py`: **42 passed** (3.30 s), including malformed requests, unavailable/startup failures, timeouts and mapping. `git diff --check` passed.

Benchmark changes are confined to `laew/eval/reranker_benchmark.py`, its offline tests, the new frozen fixture, protocol and reports. The pre-existing uncommitted Docker/reranker infrastructure remains unchanged. No production RAG/Chief/Horizon/authorization code, production Chroma data, Obsidian vault or Memory was modified. No commit or push was performed.

New benchmark source: [evaluator](../../laew/eval/reranker_benchmark.py), [offline tests](../../tests/evaluation/test_reranker_benchmark.py), [independent fixture](../../tests/rag/reranker_holdout_v1/README.md), and the protocol linked above. Git still shows the pre-existing modified `docker-compose.yml` and untracked `tools/rerankers/`; new benchmark source, fixture and reports are untracked. No file was staged.