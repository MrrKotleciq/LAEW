---
type: report
title: Stage 2B.2 hierarchical dense retrieval — Task 3B
date: 2026-11-11
status: experimental-complete-no-rollout
scope: isolated Chroma document routing, frozen quality and security evaluation
---

# Stage 2B.2 — Hierarchical dense retrieval, Task 3B

**Recommendation: revise before further validation; retain dense-only in production.** The fixed three-document strategy recovers `s14` and improves final holdout evidence at unchanged M10/1000 limits. However, it removes a valid `u27` candidate, its stress advantage disappears when distractors share longer documents, and the new long-document set shows no gain. These results do not justify rollout or replacement of dense-only. No production integration was made.

## Implementation and frozen policy

Reviewed the [Task 3A diagnosis](STAGE_2B2_ADVANCED_DENSE_REVIEW_20261111.md), pipeline, Chroma serialization/source reconstruction, generation locks, selector and existing frozen evaluators. The [protocol](../../tools/hierarchical/PROTOCOL.md) was written before strategy comparisons. The new `hierarchical_experiment.py` is imported only by its evaluator/tests. It does not embed, open a database, write an index, or use FTS5/RRF/rerankers.

* **A:** source-filtered native Chroma D10, cosine >=0.3, nonempty authorized unique leaves, M10.
* **B:** the identical D10 seeds; first three distinct authorized documents by first eligible hit; **one** Chroma query with `source AND file_path IN (...)`, using the original normalized query vector. Fetch depth is `min(128, authorized child count)`; sort the restricted pool by descending original cosine then stable ID and return M10 original leaves. There are no document quotas, reserved seed slots, score boosts or per-query exceptions.
* Both use the existing experimental `ranked_fill`, 1000 estimated tokens **per scope**, independent Global/Project rankings, existing fragment identity and overall manifest RAG allocation of 8000. No expanded parent text is sent to the selector.

Conditional depth 128 is an internal bounded retrieval pool, **not** the final candidate count. Maximum reads are 10+128 records and two Chroma calls per scope, versus 10 records/one call for A. No embeddings are fetched. Result ordering/ties are deterministic within the native returned pool; approximate membership at the cutoff remains a Chroma limitation.

Identity includes collection UUID, project root, scope and normalized relative Windows path, never basename or text alone. A mandatory freshness lease spans both stages and validation; the optional experimental `kb_lease` reuses existing scope/process locks and generation checks. Every returned ID, source, path, text and decoded metadata must match the generation-bound authorized snapshot. Source/identity conflicts, unknown IDs, stale payloads, invalid scores and generation changes fail closed. Missing mappings or a typed filtered-query availability failure return the exact original seeds **only after** rechecking freshness. Empty matches are not outages; authorization errors never trigger unfiltered retries.

## Corpus and controls

Reused all four frozen datasets under legacy/v2, their stable IDs and existing vectors. Original stress is 1036 legacy leaves. Its v2 counterpart uses the same 1024 distractors plus the **11 already-cached v2 Atlas leaves: 1035 total**, with no new stress embeddings.

Added four authored manuals of 8.6k characters, 21 leaves/document under each chunker, seven answerable questions and one unsupported question. They include Polish/English/German and multi-document/cross-scope requirements. Texts and labels were [frozen](../../tests/rag/hierarchical_long_v1/FREEZE.json) **before embedding/scoring**. These are agent-authored fixtures, not independently human-judged data. Initialization embedded 168 new chunk texts and eight original query texts once through the existing local Qwen endpoint (176 unique inputs, 70 seconds). Retrieval adds **zero** query embeddings for B and reuses these vectors across strategies/chunkers.

The grouped stress control puts the same 1024 distractor leaves into 16 documents of 64 leaves, preserving text, vectors and leaf IDs. Critically, it updates **only metadata in the same disposable Chroma vector graph**. A preliminary separately rebuilt control changed native ANN results and was discarded as a layout comparison; its explicitly named preliminary artifact is retained. Final assertions confirm identical seed IDs between A/B and between stress layouts. Against 190 earlier native D10 captures, five rankings differ (h07 v2 and four legacy stress queries), with **no candidate evidence-coverage changes**. Fresh builds nevertheless showed larger ANN variation in the preliminary run; this is a reproducibility limitation, not a routing gain.

All quality results use actual isolated `PersistentClient` Chroma collections through the existing metadata serializer, not label-conditioned in-memory lookups. Installed client/embedded backend is 1.5.9; these are not latency measurements of the production HTTP server. Exact cached cosine is a separately labeled diagnostic and supplies no candidates. There are **436 strategy/query/chunker/layout rows**.

## Candidate availability versus final delivery

Percentages are macro means over answerable queries. Each cell shows **A → B**. Complete evidence means every labeled atom, not merely a relevant document.

| Dataset / chunker | Candidate atoms | Candidate complete | Final atoms | Final complete |
|---|---:|---:|---:|---:|
| Baseline, hard, supplement / both | 100 → 100 | 100 → 100 | 100 → 100 | 100 → 100 |
| Holdout / legacy (28 questions) | 96.43 → 98.21 | 92.86 → 96.43 | 94.64 → 98.21 | 89.29 → 96.43 |
| Holdout / v2 (28 questions) | 100 → 98.21 | 100 → 96.43 | 96.43 → 98.21 | 92.86 → 96.43 |
| Stress, separate distractor files / both | 77.78 → 100 | 66.67 → 100 | 77.78 → 100 | 66.67 → 100 |
| Stress, grouped distractors / both | 77.78 → 77.78 | 66.67 → 66.67 | 77.78 → 77.78 | 66.67 → 66.67 |
| Authored long / legacy (7 questions) | 92.86 → 92.86 | 85.71 → 85.71 | 92.86 → 92.86 | 85.71 → 85.71 |
| Authored long / v2 (7 questions) | 96.43 → 96.43 | 85.71 → 85.71 | 92.86 → 92.86 | 85.71 → 85.71 |

Holdout multi-document final atom coverage (n=7) improves **78.57→92.86% legacy**, **85.71→92.86% v2**. Cross-language final coverage (n=14) improves **89.29→96.43% legacy**, **92.86→96.43% v2**. This uses only existing multilingual embeddings, with no translation or query rewriting. Cases share sources/topics and do not establish statistical significance.

### `s14`, `u27` and every regression

* **`s14`:** exact global acceptance rank remains **66 for both chunkers**. With separate distractor files, B routes Atlas plus two one-leaf competitors; acceptance becomes candidate/final position **6 legacy / 5 v2**. All three atoms survive at 945/971 tokens respectively, versus A's 958/926 tokens and missing acceptance. No larger M/context budget is used.
* **Grouped `s14`:** Atlas is still seeded, but its competing routes now each contain 64 leaves. The acceptance chunk remains outside final M10; neither strategy delivers its two atoms. The original gain depends strongly on document layout. Grouping does not repair question representation.
* **`u27` v2 — the only newly lost atom:** B excludes `calibration.md`, fourth in Global document order, after choosing release, gateway-prod and calibration-old. Candidate positions change **[1,8] → [1,missing]**. A already loses that atom during the 1000-token selector stage, so final coverage is unchanged at 1/2; this does **not** excuse the candidate regression. No beam widening or query exception was applied. Legacy instead retains calibration and improves its final positions **[1,missing] → [1,8]**.
* **`u22`:** legacy recovers the calibration atom at candidate/final position 10. V2 already has that candidate, and removing other documents lets it survive the budget at final position 7. These are the other holdout gains.
* **`s16` v2 — ranking regression:** acceptance moves **2→3** in candidates and final selection, in both stress layouts; coverage remains complete. There are no other new lost atoms or worsened labeled positions in this run. Full before/after positions and excluded documents are retained in the [regression artifact](hierarchical-20261111-regressions.json).

The authored set's `l07` remains incomplete: it asks for preparation from four documents across two scopes. Legacy retrieves 2/4 atoms; v2 retrieves 3/4 but delivers 2/4 after the budget. With only three Global manuals and one Project manual, this set weakly exercises exclusion by a three-document beam and provides **no independent gain**. Larger and independently judged collections remain necessary. Unsupported queries continue to receive irrelevant context; routing is not an answer-sufficiency detector.

## Context and resource costs

Holdout mean combined rendered tokens change **871→901 legacy**, **982→943 v2**; selected fragments **9.62→8.97**, **6.81→6.56**. Qrel-irrelevant fragment rates drop **66.9→60.6%**, **67.0→63.8%**, although fragments without a labeled atom remain high (89.0→87.5%, 83.9→82.9%). Relevance judgments are document-level; unlabeled context is not necessarily useless. Authored long-set context/fragments are unchanged. Combined totals may exceed 1000 when both scopes participate; each scope remains separately bounded.

All **436 adapter replays received the selected context**, no allocation violations occurred, M never exceeds 10 and the maximum observed per-scope estimate is 996 tokens. These replay checks use the existing observer adapter, not paid or real answer generation. Token counts use the existing character estimate, not an LLM tokenizer.

Warm local timings below are the **mean of three fixed queries' p50/p95**, each with 20 repetitions; all timed queries use one scope. They include retrieval, validation and routing, excluding the shared query embedding, selector and index build.

| Workload / chunker | A p50 / p95 ms | B p50 / p95 ms | Returned metadata A → B |
|---|---:|---:|---:|
| Holdout / legacy | 2.68 / 2.74 | 5.29 / 5.55 | 7.1 → 14.6 kB |
| Holdout / v2 | 3.37 / 3.48 | 6.34 / 6.47 | 12.3 → 21.6 kB |
| Stress separate / legacy | 4.79 / 5.13 | 8.45 / 8.71 | 5.1 → 12.3 kB |
| Stress separate / v2 | 5.05 / 5.28 | 9.42 / 9.88 | 6.4 → 19.2 kB |
| Stress grouped / legacy | 4.76 / 4.93 | 12.58 / 12.86 | 5.4 → 75.2 kB |
| Stress grouped / v2 | 4.99 / 5.09 | 13.38 / 13.90 | 6.8 → 79.8 kB |
| Authored long / legacy | 2.54 / 2.71 | 6.33 / 6.47 | 6.1 → 28.1 kB |
| Authored long / v2 | 3.22 / 3.31 | 9.18 / 9.51 | 9.6 → 43.9 kB |

B doubles calls per participating nonempty scope; grouped stress consumes the full **138-record read bound**. Bytes are serialized IDs/metadata/distances, **not HTTP traffic**. Selector single observations have median 0.076 ms, max 0.187 ms; they are not a separate repeated latency benchmark.

Maximum traced per-query Python allocation is about **92→105 KiB** on legacy holdout, **64→110 KiB** on v2 separate stress, **65→334 KiB** on grouped v2 and **86→405 KiB** on authored v2. These do not include native Chroma allocations. The 1036-leaf snapshot has a 176 kB string representation and ~669 KiB traced construction peak; construction with tracing takes 61 ms. Scratch index plus registry builds take ~629 ms / 10.96 MB disk. No second retrieval index or additional corpus vectors are needed by B.

Process working set around stress indexing/warmup is roughly 322–346 MiB, including the evaluator/cache/native client. The process lifetime peak (~893 MiB) includes cache parsing; it is not B's incremental RAM. Allocator reuse and sequential measurements do not isolate native per-method RAM. Snapshot dictionaries grow O(number of leaves), and rebuilding their hashes scans payloads; this prototype is not a production synchronization solution for millions of changing chunks. The 1 MiB result check bounds accepted client payloads after receipt, not server allocation or HNSW search work. Long-document follow-up remains bounded top-pool retrieval, not an exhaustive scan or source-order truncation.

## Validation, files and decision

`scripts/run_isolated.py pytest` completed **68 tests**, covering the new adapter/evaluator, existing selector/chunkers and process locks. A rooted-path rejection discovered in the first focused run was fixed. Tests exercise real metadata filters, multiple leaves/document, source/project isolation, duplicate IDs across scopes, rename/delete with fresh snapshots, stale/conflicting payloads, generation changes at either stage, failed authorization/freshness, missing mappings, safe availability fallback, stable ties and read/response bounds. The grouped control asserts an unchanged seed ranking. One upstream Chroma deprecation warning remains. No source-security or freshness violation was observed in these tests; this is not a production audit.

Exact new implementation/fixture files:

* `laew/rag/hierarchical_experiment.py`, `laew/eval/hierarchical_benchmark.py`.
* `tests/rag/test_hierarchical_experiment.py`, `tests/evaluation/test_hierarchical_benchmark.py`.
* `tests/rag/hierarchical_long_v1/{dataset.json,FREEZE.json,global/orion.md,global/mira.md,global/polar.md,project/delta.md}`.
* `tools/hierarchical/{PROTOCOL.md,prepare_fixtures.py}`; this report; one appended navigation link in `docs/README.md`.
* Task-prefixed `docs/reports/hierarchical-20261111-*` cache/results, summaries, CSV, regression/control JSON, logs and state manifests. The [final state](hierarchical-20261111-final-state.json) enumerates every file and hash; [summary](hierarchical-20261111-summary.json), [details](hierarchical-20261111-details.json.gz), [validation log](hierarchical-20261111-validation.log).

Git remains dirty, with the earlier `docker-compose.yml`, README and untracked Stage 2B.2 work preserved. Among captured pre-existing files, Task 3B changes only the README by adding its report link. Production RAG/routing/chunking, Chroma/SQLite, Obsidian, Horizon and rerankers were not modified. No new service/dependency/model, commit or push.

Further work should first address irreversible exclusion of relevant seed documents and validate on independently judged, larger multi-document sources, with ANN reproducibility controlled. That would be a **new approved isolated experiment**, not an automatic rollout of this policy. Stop here; any subsequent rollout requires explicit approval.
