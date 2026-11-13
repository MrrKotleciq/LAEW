---
title: Stage 2B.2 — Pilot v4, sealed dataset and retrieval-only comparison
date: 2026-11-13
status: complete-provisional-retrieval-only
scope: Tasks 3C.2B and isolated retrieval only
---

# Dataset and execution boundaries

This is an exploratory comparison against **agent-draft reference evidence**, not independently validated ground truth. No answer generation, LLM judge, GPT-5.6 Luna request, deployment or production change is authorized or performed. Collection, separate scoring, zero-network payload replay and independent copy verification are complete. The largest sealed gain is C, with pilot regressions; retain production A and review labels before any separately authorized answer study.

The source corpus remains the restricted, text-only R3F freeze: 24 complete units, 1,281,131 content characters, 2,171 legacy and 2,185 structure-v2 chunks. Its manifest SHA-256 is `5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19`. The exact 777-file freeze inventory was independently verified before use and again after collection. All ten restricted/unavailable components, 329 uninspected High findings and remaining Medium/Low priorities remain open. Targeted evidence QA does not certify whole pages or manuals.

All large datasets, review excerpts, private code/diff snapshots, caches and indexes are outside Git and Obsidian under `C:\Users\korne\LAEW-corpus\`.

| Artifact | Versioned directory suffix | Integrity manifest SHA-256 |
|---|---|---|
| Pilot, 4 families / 12 questions | `stage-2b2-real-world-pilot-20261113-v4` | `9060c3027424da26c5c49888cea62d423a7df543242258f8eb0629c58360bcf6` |
| Sealed, 16 families / 48 questions | `stage-2b2-real-world-sealed-20261113-v3` | `4f19aba5f77f8012d74bdfdfc7305cdbba330672fa82138c8b108480eec9e437` |
| Questions-only input and fixed execution plan | `stage-2b2-real-world-evaluation-inputs-20261113-v3` | `220b16efab0411a70affd782d050644af997b7c70b863f259833f06647fcd8e0` |
| Experimental artifacts | `stage-2b2-real-world-retrieval-20261113-v2` | `4bdbeed19cf75a4e435dc1d5ee1111cf26736c29f1ed3436acd6b99d52b5aad5` |

Each dataset separates `questions.json`, `draft-labels.json`, `evidence-spans.json`, provenance, QA and review packages. `review.html` contains exact excerpts, original locations/revisions and proposed facts; `blind-second-review.html` supports a separate reviewer. The inherited pilot `authoring-plan.json` is historical v3 input; v4 questions/families/labels, amended provenance, generator snapshot and human-feedback record define the current revision.

# Pilot amendment and sealed preparation

P01/P03/P04 question and label objects remain identical to v3. P02 preserves the user-supplied Polish wording and uses agent-authored EN/DE equivalents. Its labels make cleaning conditional on need, retain the cool-surface/burn warning when cleaning is advised, and require appropriate first-layer observation/Live Z only as necessary after changing sheets. They do not require automatic solvent treatment or a full calibration cycle. The user's feedback is recorded as Polish question-naturalness feedback, with no invented review timestamp, domain certification or independent agreement.

The sealed reservation is met exactly: five single-document, five multi-section, three complementary multi-document and three insufficient/unavailable families, each in EN/PL/DE. All six Prusa manuals have distinct answerable sealed coverage. Pro Git retains genuine translated and fallback content; PostgreSQL retains its frozen v11/v17 scope and WAL commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48`. Exact source/version/normalized offsets and original section/page references are stored in 56 sealed spans. Alternatives are coherent sufficient evidence sets, never chunk IDs. Source-span intersections with pilot evidence are zero. Six or more families satisfy the pre-existing, query-independent ten-chunk-distance rule.

The answerable-family balance is eight Prusa, four Git and four PostgreSQL, rather than the specification's approximate preference of six/six/four. Category quotas and all-six-manual coverage are mandatory and met; the source-group preference is not an exact quota. This imbalance is disclosed before results and makes source-group strata essential; no aggregate score should be generalized to a differently balanced workload.

| Family | Category | Operational intent |
|---|---|---|
| S01 | Single document | MMU3 directional purge settings |
| S02 | Single document | Delete an agreed remote branch and interpret retained data |
| S03 | Single document | Windows/Linux Git line endings |
| S04 | Single document | PostgreSQL WAL soft size limit under archiving failure |
| S05 | Single document | MK4S workshop environment and power applicability |
| S06 | Multi-section | MK3.9-to-MK4 firmware/model checks and rollback |
| S07 | Multi-section | Five-tool XL loading and tube maintenance |
| S08 | Multi-section | MINI+ PTFE and stuck-filament diagnostics |
| S09 | Multi-section | MK3S flow adjustment persistence and ABS cracking |
| S10 | Multi-section | Nested submodule initialization and safe publication |
| S11 | Multi-document | Separate MK4S/MMU3 firmware paths and warnings |
| S12 | Multi-document | PostgreSQL 11/17 non-exclusive backup APIs |
| S13 | Multi-document | PostgreSQL 11/17 recovery timeline defaults |
| S14 | Insufficient specification | Missing MINI+ model-specific screw torque |
| S15 | Insufficient user context | Unspecified Git push destination |
| S16 | Explicitly unavailable | XL PDU terminal position and drawn symbol |

Source QA preceded retrieval: original mapped AsciiDoc/HTML was checked for software spans, and native frozen page rasters/cells were inspected for selected Prusa evidence and required context. Inspected sealed pages include MMU3 EN 15/17/39/40, MK4S EN 6/29, MK4 DE 32/67, XL DE 27/76, MINI PL 48/56 and MK3S PL 62/77. Derived neutral table headers are excluded from technical evidence. Values, units, negations, warnings and product/version applicability remain draft judgments requiring human review. No restricted component is accepted as positive evidence.

S14 has an all-24-source inspection record and bounded absence rationale, not a failed-search assumption. Its absence judgment still needs independent full-corpus adjudication. S15 needs missing user prerequisites. S16 uses the explicit XL page 81/83 restriction as unavailability provenance, not as evidence of protective-earth placement or symbol meaning. Positive recall is N/A for unsupported questions; nonempty retrieval is diagnostic.

Before any question retrieval, a source-only audit found generic S09 material advice could admit same-language alternatives. A new sealed v2 adds indispensable native MK3S flow-control/persistence evidence; `M221` occurs only in the Polish MK3S source across the 24 units. S09 EN/PL/DE wording and labels were revised; all other sealed questions remain unchanged. The earlier sealed v1 and evaluation-input v1 remain preserved. The first collection attempt was deliberately stopped after 124 committed **source** embeddings, before index insertion or any question retrieval: no trace, ranking or score existed. Its exact-input/model-identity cache is imported from an unchanged read-only source into a new run; entries are reused only if their strict keys match. Initial compute cost is additional and not silently counted as zero. The service catalog's changing `created` timestamp can prevent cross-run cache hits; actual hits are recorded in run costs. This overly strict cache identity affects efficiency, not vectors or retrieval policy, and is not changed during this experiment.

A subsequent source-only minimality audit, still before any question retrieval, found S10 unnecessarily required both `check` and `on-demand` publication options. Sealed **v3** makes the check guard sufficient and documents on-demand as an optional valid workflow; no question text changed from v2. The v3 input-plan addendum pins this label revision. The active collector continues with the byte-identical questions-only v2 file (same hash); it cannot read either label version. No retrieval result informed either correction, and no parameter changed. Historical v1/v2 packages and plans remain intact.

# Fixed retrieval method

| Arm | Chunker | Native K | Selector | Estimated tokens/scope |
|---|---|---:|---|---:|
| A | Legacy | 2 | top2 | 500 |
| B | Legacy | 10 | ranked_fill | 1,000 |
| C | Structure-v2 | 10 | ranked_fill | 1,000 |

All use dense cosine, eligibility >=0.3, chunk size 1,000, legacy overlap 200, one public Global scope and empty Project scope, with overall allocation 8,000. A/B share the same legacy vectors/index. Native K2 and K10 searches are recorded separately. The production loader, serializer and selectors are reused without modifications, and generated chunks are checked against frozen payload hashes. Exactly the 24 normalized sources enter each primary collection; questions, labels and review material never enter indexes. No query-dependent filtering, model download, service start, reranker, fusion, hierarchy or parameter tuning occurs.

The user started the existing embedding service after its initial unavailability. Its model is `laew-qwen3-embedding`, 1,024 dimensions, Qwen3-Embedding-0.6B Q8_0, artifact SHA-256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`, local Hugging Face snapshot `370f27d7550e0def9b39c1f16d3fbaa13aa67728`. Model catalog identity and exact input text key the vector cache; the independently hashed weight artifact is recorded in environment provenance. There are 4,256 unique source inputs and 60 queries before prior-cache reuse. Batch size eight changes transport efficiency only.

The collector receives a hash-pinned sanitized questions-only file (`ceca055a19e70ed610d0aae3a07f93e9406c149d5f79b2e6d3dbf1fe5d4671ed`). It seals candidate/eligibility/selection traces before the scorer reads labels in another process. Source-offset unions account for visible primary/context text and clipping; annotations, missing non-whitespace content and wrong source identities cannot earn credit. Fact coverage is maximized within one coherent alternative set, not by mixing incompatible methods/versions. This conservative full-span metric can under-credit partial semantically sufficient prose; it is not human semantic adjudication.

The predeclared timing subset is the 12 pilot questions, 20 warm repetitions per arm (720 searches), plus one fixed-order rebuild and 36 membership/order checks. Context cost uses the actual production `ceil(chars/4)` estimator; the already-running embedding tokenizer provides supplementary counts, not answer-model token counts. Embedded Chroma timings are not production HTTP-server timings.

**User operational instruction during collection:** finish this run in its current configuration. Before future large embedding jobs, report input counts and potentially long runtime in advance so the user can configure GPU execution and more llama.cpp slots. Do not change or restart this service during the current run. Future capacity changes require fresh recorded environment provenance; they must not be retroactively attributed to this measurement.

# Remaining review and authorization requirements

All technical labels remain `agent_draft`. Required next reviews: domain validation of facts/warnings/applicability and alternatives; bilingual review of all variants, including the proposed twelve required cross-language cases; independent second review of unsupported and historical-conflict families plus a preselected quarter of other families; adjudication of bounded absence and disputed equivalences. Connected sealed topics S06/S11, S08/S14 and S12/S13 must not be treated as independent observations. The 60 language variants represent 20 intent families, not 60 independent samples.

Future answer-quality work needs separate user approval, an approved public-content/usage allowance, a current provider preflight and a reviewed grading plan. Nothing in this retrieval experiment authorizes live inference, LLM judging or changing production legacy/cosine/K2/top2/500.

# Implementation and reproducibility

New evaluation-only code: `tools/corpus/prepare_real_world_dataset.py`, `laew/eval/real_world_retrieval.py`, `laew/eval/real_world_payload_replay.py`, `laew/eval/real_world_analysis.py`, and `tests/evaluation/test_real_world_retrieval.py`. No production chunker/retrieval implementation is edited. The external experiment directory preserves executable source snapshots, content fingerprints, dependency versions, effective settings and the private existing-working-tree diff. Final analysis/replay code is preserved separately if added after the collection snapshot.

Dataset preparation and verification use the generic builder's `pilot`, `sealed` and `verify` modes with new output paths. Authoring plans, exact spans, parent manifest hashes and generator copies are retained in each versioned dataset. Historical authoring attempts and superseded snapshots remain available; no historical output is overwritten.

Collection uses `scripts/run_isolated.py --keep-diagnostics eval laew.eval.real_world_retrieval collect`, absolute frozen corpus/questions paths, the questions SHA-256, a relative new output directory and the documented read-only initial cache. Scoring runs separately with mode `score`, `--run`, and two `--dataset` arguments pointing to pilot v4 and sealed v3. Replay uses `laew.eval.real_world_payload_replay`; descriptive analysis uses `laew.eval.real_world_analysis`. Every later run must verify manifests first, create fresh output/index directories and retain the same A/B/C plan. Do not treat a repeated run as permission to change labels or tune parameters.

Validation: **38 tests passed** for scorer/mapper/dataset and production-selector/chunker regressions; **24 tests passed** for zero-network first-dispatch replay and existing scope/synchronization/project-isolation/process-lock controls. After the label-only sealed v3 correction, **two focused dataset integrity/quota tests passed** again. One additional test reproduced the frozen pilot questions/families/labels/spans from an external amendment plan, keeping technical draft content out of the generic repository generator; the original frozen generator copies remain untouched. Tests use `scripts/run_isolated.py`; no live generation is part of them. Initial state records 213 pre-existing dirty/untracked file hashes; all 213 were rechecked unchanged at completion.


# Measured results
Recall is macro required-fact coverage within a coherent evidence set. Complete counts use 9 answerable pilot variants (3 families) or 39 answerable sealed variants (13 families); positive recall is N/A for the remaining unsupported variants. Context cost includes all 12/48 questions. Raw and eligible scores are identical here: no required fact was lost to the fixed 0.3 threshold. Selected scores also describe delivery into the mocked first provider payload: all 180 exact contexts were retained. No live answer was generated.
| Split | Arm | Raw recall@K | Raw complete | Selected recall | Selected complete | Selected warning/condition coverage | Selected document hit | Mean estimated tokens |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| pilot | A | 14.8% | 0/9 | 13.0% | 0/9 | 2.8% | 72.2% | 442.4 |
| pilot | B | 38.9% | 3/9 | 14.8% | 0/9 | 2.8% | 77.8% | 920.8 |
| pilot | C | 31.9% | 1/9 | 13.0% | 0/9 | 0.0% | 77.8% | 967.3 |
| sealed | A | 26.9% | 8/39 | 11.5% | 2/39 | 11.1% | 76.9% | 383.7 |
| sealed | B | 46.2% | 15/39 | 32.1% | 10/39 | 27.8% | 89.7% | 922.6 |
| sealed | C | 55.1% | 18/39 | 37.2% | 13/39 | 30.6% | 87.2% | 893.0 |

B versus A increases selected sealed recall by 20.5 percentage points and complete coverage from 2/39 to 10/39, while mean context grows from 383.7 to 922.6 estimated tokens. C versus B adds 5.1 points of sealed recall and three complete cases, using slightly fewer tokens (893.0). The three additional complete cases are S01-en and S06-pl/de. In the pilot, B has only a small selected-recall improvement; C falls back to A-level selected recall. Every arm has zero complete pilot contexts. Candidate coverage alone therefore overstates usable evidence.

## Sealed strata
Cells show selected fact recall / complete evidence. Each language has 13 answerable variants; category/source denominators appear below. All full pilot/sealed language/category/source strata are retained in `score-v2/summary.json`.
| Stratum | Answerable variants | A | B | C |
|---|---:|---:|---:|---:|
| EN | 13 | 7.7% / 0.0% | 38.5% / 30.8% | 42.3% / 38.5% |
| PL | 13 | 15.4% / 7.7% | 30.8% / 23.1% | 34.6% / 30.8% |
| DE | 13 | 11.5% / 7.7% | 26.9% / 23.1% | 34.6% / 30.8% |
| Single document | 15 | 20.0% / 13.3% | 63.3% / 60.0% | 66.7% / 66.7% |
| Multi-section | 15 | 10.0% / 0.0% | 13.3% / 0.0% | 23.3% / 13.3% |
| Multi-document | 9 | 0.0% / 0.0% | 11.1% / 11.1% | 11.1% / 11.1% |
| Prusa | 21 | 7.1% / 0.0% | 11.9% / 0.0% | 21.4% / 14.3% |
| Pro Git | 9 | 33.3% / 22.2% | 66.7% / 66.7% | 66.7% / 66.7% |
| PostgreSQL | 9 | 0.0% / 0.0% | 44.4% / 44.4% | 44.4% / 44.4% |

The predeclared twelve cross-language cases and all six directions are reported separately in `analysis-v1/analysis.json`; these necessity tags remain agent judgments. All 60 variants are now observed validation data. Future algorithm development needs a new holdout, not retuning on these sealed results. No significance interval is claimed from three pilot or thirteen sealed answerable families and dependent topic clusters.

## Costs and reproducibility
| Arm | Warm search p50 / p95 (ms) | Pilot tokens p50 / p95 / max | Sealed tokens p50 / p95 / max | Sealed actual embedding-tokenizer mean |
|---|---:|---:|---:|---:|
| A | 19.22 / 21.98 | 490.5 / 500.0 / 500 | 397.5 / 500.0 / 500 | 459.5 |
| B | 19.85 / 25.29 | 924.5 / 997.0 / 997 | 930.0 / 995.3 / 1000 | 1079.9 |
| C | 20.83 / 27.18 | 976.0 / 990.2 / 993 | 924.0 / 995.0 / 999 | 1068.3 |

There were 720 warm searches (240 per arm) and 36 rebuild checks: zero membership/order changes on the 12-question pilot subset. This does not establish stability for every sealed query. Quality searches and selection timings are logged per row; timing is local embedded Chroma 1.5.9, not the production HTTP backend. All per-scope and overall rendered budgets passed. Actual tokenizer counts exist for all 180 contexts and are supplementary Qwen embedding-tokenizer counts, not GPT-5.6 Luna tokens. Six A fragments were clipped (2 pilot, 4 sealed); B/C had no clipped fragments. Character/fragment distributions and facts per 1,000 estimated tokens are retained in the analysis.

Embedding work dominated: 4,316 inputs in 541 successful requests, 100.55 minutes; the measured collection phase lasted 101.15 minutes. Legacy used 2,106 source inputs / 48.93 minutes and 2.39 seconds to insert/check its index; structure-v2 used 2,150 / 51.14 minutes and 3.77 seconds. The 60 query inputs took 28.28 seconds. Exact-text deduplication saved 100 source embeddings within this run. Imported prior-cache hits were **zero** because the catalog timestamp changed; the earlier 124 completed source inputs are additional confirmed compute, with interrupted in-flight work unmeasured. Embedding token/energy accounting is unavailable, not zero. No paid model API was used.

The four primary/rebuild collections occupy about 83.5 MiB at collection end; the preserved run is about 108.3 MiB including vectors and traces. Collection UUIDs, dimensions and backend configuration are in `collection-catalog.json`. Native Windows sampling observed up to 403.2 MiB client working set, excluding the model service. Sampling began during embeddings, so this is an observed peak, not a full-lifetime bound. The existing server remained CPU-only, one slot, build b11540-1e6f04a75 throughout; it was not restarted.

## Failures, exposure and all regressions
All 81 proposed reference spans were fully attributable in both query-independent indexed text universes; there were no missing-source/index-attribution fact failures and no threshold fact losses. Mechanical unsupported-attribution fragments: zero. This verifies source/version/offset identity, not independent semantic citation quality.
| Split / arm | Present but not retrieved (fact cases) | Selection/budget loss (fact cases) | Restricted-context exposure (questions) | Uninspected-High page exposure (questions) |
|---|---:|---:|---:|---:|
| pilot/A | 37 | 1 | 0 | 2 |
| pilot/B | 28 | 9 | 0 | 3 |
| pilot/C | 30 | 8 | 1 | 3 |
| sealed/A | 60 | 12 | 1 | 25 |
| sealed/B | 45 | 11 | 1 | 27 |
| sealed/C | 38 | 14 | 2 | 27 |

Restricted exposure consists of S16-de / XL page 83 in A/B/C, S16-en / XL page 81 additionally in C, and pilot P02-en / MINI page 45 in C. This means the unavailable component or its registered related context entered a selected fragment; it is not proof of answer hallucination or technical support. Positive labels never use these regions. All 329 High findings and other priorities remain open. Page-level risk exposure remains flagged even when a narrower proposed span received agent QA.

Unjudged text means delivered source characters outside the union of all 81 proposed reference spans, not a query-relevance judgment. Sealed fractions are 69.6% / 79.6% / 76.6% (A/B/C); pilot 57.8% / 69.0% / 68.7%. Text inside another question's reference span can still have unjudged relevance to the current question. Neither unknown nor other-model/version text is automatically irrelevant or technically valid. Inapplicability and alternate evidence need domain adjudication; no unsupported answer-precision metric is inferred.

Every negative paired recall difference is preserved in `analysis-v1/analysis.json` and the metadata-only repository regression file:
| Comparison | Question | Regression |
|---|---|---|
| B to C | P01-en | Raw/eligible complete to incomplete; selected coverage unchanged |
| B to C | P01-de | Raw/eligible complete to incomplete; selected coverage unchanged |
| B to C | P03-en | Raw/eligible complete to incomplete; selected recall lower |
| B to C | S06-en | Raw complete in both; selected recall drops 0.5 to 0 through budget/selection |
| B to C | S12-en | Raw recall drops 0.5 to 0; selected coverage already zero |

There are no A-to-B recall regressions and no B-to-C selected complete-to-incomplete regressions in this set. The three raw complete-to-incomplete cases still require independent review. P01/P03 illustrate candidate evidence being excluded by the 1,000-token selector; P02 misses all required source spans even at K10. Multi-document selected completeness remains only 1/9 in B/C. Do not repair these cases by changing sealed questions, source representation or A/B/C settings. Full-span matching can under-credit a semantically sufficient shorter passage, and optional/alternative workflow completeness remains a human-review issue. No labels were revised after retrieval.

## Recommendation and final state
Retain production **A** unchanged. **C merits a separately approved further evaluation**, with B as the necessary legacy/large-budget comparator and A as reference: its sealed gain is modest, concentrated in Prusa, and accompanied by pilot/individual regressions and more restricted-context exposure. B also materially improves the sealed reference over A, but much larger context brings little pilot benefit. None is independently validated or established as generally superior. Prioritize domain/bilingual/independent label review and the complete-to-incomplete cases; the result does not authorize a larger budget, a new retrieval policy or deployment.

The durable workspace is `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-retrieval-20261113-v2`. `completion-verification.json` records fresh corpus/dataset/model integrity and byte/hash-verified copies: 28 run/index files, 3 scoring files, 1 replay file and 2 analysis files. The 777-file source freeze, original pilot v3 and current dataset/input manifests remain intact. `trace-integrity.json` SHA-256 is `e91d52ea4209fc44dc32faaa22ad5e8adda13367939f6e21fc3db20116cb342a`; replay SHA-256 is `82c2213a95ab67b0a92121fe251f369c1b68d7e3c842d13c5a9bd6092cf94997`. Initial historical run-location/plan records are retained; the v3 plan addendum and completion receipt are authoritative. First sandbox scoring/replay passed, but their temporary paths were unavailable afterward; the unchanged sealed traces were scored/replayed again into durable isolation. No retrieval/model calls were repeated for this persistence repair.

Changed repository files are only the new evaluation tool/modules/test and this report plus metadata snapshots/summary/regression/status artifacts. All 213 pre-existing file hashes remain unchanged; tracked dirty files are still only the pre-existing `docker-compose.yml` and `docs/README.md`. No add/commit/push/reset/clean, production setting change, source/PDF regeneration, live answer test or LLM judge occurred. The separately requested GPU report and unlaunched candidate script are in `C:\Users\korne\Scripts`; they did not alter the running CPU service or benchmark files.

**Hard stop:** Task 3C.3 answer generation/evaluation remains unauthorized. Remaining requirements are explicit user approval of the live pilot/public content/usage allowance, a current provider preflight, reviewer/provenance handling and an approved grading plan. Do not run Luna, an answer model or a judge from this result.

Final experimental artifact seal: **201 inventoried files plus `artifact-integrity.json`**, 117,183,411 inventoried bytes; manifest SHA-256 `4bdbeed19cf75a4e435dc1d5ee1111cf26736c29f1ed3436acd6b99d52b5aad5`. All recorded sizes/hashes and the exact file set were independently verified. The interrupted 124-vector attempt is also copied and verified. Its initial plan preserves the old collector hash, but the old source bytes were not snapshotted (the isolated runner imports repository Python modules). This provenance limitation concerns only the unused interrupted cache; the complete final collector source/hash, all consumed code/configuration pins, frozen datasets and closed traces are preserved and mutually consistent.

Warning coverage averages only cases with declared warning/condition facts; it is not an independently adjudicated count of every clause. Facts and warning classifications require domain review. No label, arm or document correction was made from results.
