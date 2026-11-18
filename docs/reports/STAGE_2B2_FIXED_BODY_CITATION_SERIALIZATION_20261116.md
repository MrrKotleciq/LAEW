---
status: completed offline shadow experiment; no production decision
date: 2026-11-16
dataset: 60 exposed development questions, saved B/K10 and C/K10 contexts
judgment_provenance: post_result_agent_boundary_review
---

# Fixed-body citation serialization

Removing tags and backlinks (S1) saves **90 estimated tokens on average** across
120 contexts: **9.84% of total context cost and 34.44% of attribution/separator
overhead**, with every delivered body character unchanged. The median saving is
only 22 tokens; the benefit is concentrated in PostgreSQL navigation metadata.
This is unused capacity, not added evidence. Complete contexts remain **B 13/48,
C 18/48** in every format.

The predeclared full inline provenance formats S2/S3 preserve mechanically
unambiguous source references and independent passage boundaries, but increase
mean total cost by 21.70%/16.44%. They exceed 1,000 tokens in 92/89 of 120
contexts. Reject these exact formats for the present per-scope budget. Do not
repack the bodies to make them fit.

S1 is worth investigating separately as metadata removal. It preserves the
historical attribution and the complete version/range bindings in the frozen
sidecar bundle; it does **not** add inline revisions, offsets or an explicit
warning about omissions within an existing body. Consequently it is not a
standalone solution to all provenance/continuity acceptance criteria. No format
is approved for deployment or certified as safe for model interpretation.

# Inputs, isolation and freeze

External package (all large artifacts, outside Git and Obsidian):

`C:\Users\korne\.codex\visualizations\2026\11\16\01a1e47e-cedb-70e1-a4df-b6d1aa1ea057\laew-fixed-body-citations-v1`

The boundary audit/specification, extraction feasibility, retrieval budget and
historical context-delivery reports were inspected, together with the historical
renderer, selected payloads, source mappings and traces. These reports contain
agent-authored post-result judgments, not independent domain validation.

Before collection, verification covered 777 frozen corpus files (774 copies),
201 historical retrieval artifacts, trace/input manifests and both preceding
research packages. `inputs/input-integrity.json` records exact receipts.
Parent manifest pins are:

- Fine-evidence package: `dfd32baa3e9de0aa67ecaa47a0b6be7b0dcba0b3fb6f05a25abbb8377d6218db`.
- Boundary package: `35225effb768c1a4256926428ac78995eef7876fe1431423919bdcf1c62b290f`.
- Fixed input manifest: `e62c5273ba782fa46fe3278733b78a5aac77676834035a715ea9767e761d992f`.

The primary input contains exactly 120 saved B/C K10 contexts, 60 question IDs,
441 selected passages and 313,599 body characters. The study reconstructs and
hash-checks existing legacy/structure-v2 chunks using `embed=False`; it does not
query an index, rerank, select, retrieve or embed anything. Cosines, raw candidate
order, eligibility, selected/skipped IDs, selected order, clipping, 1,000-token
scope allocation and 8,000-token overall allocation are frozen in each contract.

The only additional fixture is a **separate, already-saved, reference-informed
P03-en seven-whole-chunk oracle witness**, costing 3,699 tokens historically.
It is not a valid historical 1,000-token selection, not part of primary averages,
and not evidence of a runtime mechanism. K20 and the curated 991-token sentence
fixture were not added to the primary experiment.

`DESIGN_BEFORE_EVALUATION.md`, 27 synthetic tests and `format-freeze.json` precede
full collection. Serializer SHA-256:
`62cf8f291ea98d90ff00578ee5eb22d4e351b42e8eba7aecc62f209d7703e689`.
The serializer and driver were not changed after observing results. Six additive
acceptance cases were subsequently added to the test file; its original frozen
copy remains in `code-freeze/`. No additional format was invented.

**Provenance clarification:** preparation reads the saved oracle indices for the
separate P03 diagnostic. The original `inputs/provenance.json` flag
`labels_read: false` applies to primary serialization, but is too broad for the
whole preparation process. This report and `PROVENANCE_CLARIFICATION.md` record
that limitation without rewriting the frozen receipt. Primary choices never
read benchmark requirements. Collection reads no labels; v2.1 scoring is a
separate, subsequent process. No saved answers are read.

# Fixed-body contract and formats

Each contract pins source ID, normalized source hash, document revision,
product/version applicability, ownership scope, exact Unicode ranges, original
chunk map, payload hash, fragment order and historical context. Unicode is
preserved without normalization; offsets are code points in LF snapshots.
CRLF inputs and invalid offsets fail closed. Historical clipping is kept,
including its ellipsis; savings never expand a clipped body.

The selected structure-v2 bodies contain preexisting synthetic labels, repeated
related context and tables. These remain byte-for-byte equivalent in UTF-8;
they are not newly claimed as source-exact prose. Their original mappings and
annotation flags remain bound. There are 149 primary passages with multiple
mapped source ranges; retaining them does not resolve their semantic boundaries.

| Format | Change permitted | Attribution and boundary behavior |
|---|---|---|
| S0 | None | Exact historical rendering; full version/range proof in sidecar |
| S1 | Remove tags and backlinks only | Original path/ownership/section/type/status and separators; same full sidecar; same-path revision collisions rejected |
| S2 | Group immutable source records, use D/H/P references | Full inline ID/revision/hash/path/scope/applicability; exact ranges and body lengths; explicit independent-passage notice, verbose separators and passage ends |
| S3 | S2 with compact separators | Same provenance and lengths; seven-character separators, independent-passage notice and explicit passage ends retained |

Source/section aliases follow first occurrence, without sorting passages.
Aliases do not combine revisions or source hashes. A length-framed decoder
round-trips S2/S3; source text resembling a marker cannot escape its body.
The inline contract hash binds original chunk identities/maps in the sidecar.
S0/S1 deliberately retain historical inline limitations; auditing their full
version/range identity requires the matching immutable sidecar.

# Primary measurements

Estimator: `ceil(len(text) / 4)`, not a model tokenizer. p95 is nearest rank.
Positive savings mean a reduction. Rows are correlated B/C variants of the same
60 exposed questions; there is no significance or generalization claim.

| Format | Mean total tokens | Mean / median / p95 saving | Total cost reduction | Mean overhead chars/4 | Over 1,000 |
|---|---:|---:|---:|---:|---:|
| S0 | 915.05 | 0 / 0 / 0 | 0% | 261.35 | 0/120 |
| S1 | 825.05 | 90 / 22 / 426 | 9.84% | 171.35 | 0/120 |
| S2 | 1113.63 | -198.58 / -240.5 / 225 | -21.70% | 459.92 | 92/120 |
| S3 | 1065.48 | -150.43 / -184 / 243 | -16.44% | 411.77 | 89/120 |

S1 saves tokens in 96 contexts, ties in 24 and increases none. Its maximum saving
is 550. Mean unused per-scope headroom changes from 84.95 to 174.95 tokens;
none is used. All 484 serialized rows (480 primary, four diagnostic) retain
exact bodies/ranges and have empty requirement gains/regressions ledgers.
Minimum-evidence coverage and critical support are unchanged per question.

| Arm | Historical mean | S1 mean | S1 mean saving | Complete, every format |
|---|---:|---:|---:|---:|
| B | 922.23 | 822.95 | 99.28 | 13/48 |
| C | 907.87 | 827.15 | 80.72 | 18/48 |

| Language | Contexts | S1 mean saving | S2 mean saving | S3 mean saving |
|---|---:|---:|---:|---:|
| EN | 40 | 86.20 | -213.95 | -163.55 |
| PL | 40 | 95.92 | -175.45 | -130.00 |
| DE | 40 | 87.88 | -206.35 | -157.75 |

| Delivered source domain | Contexts | S1 mean saving | S2 mean saving | S3 mean saving |
|---|---:|---:|---:|---:|
| PostgreSQL | 30 | 314.13 | 96.30 | 116.10 |
| Pro Git | 30 | 1.30 | -359.03 | -300.23 |
| Prusa | 60 | 22.28 | -265.80 | -208.80 |

By original question category, S1 saves 79.28 tokens for single-document tasks,
18.14 for multi-section tasks, 257.50 for multi-document tasks and 46.38 for
insufficiently specified tasks. These are descriptive strata, not causal claims.
The delivered bodies can have a different structure: 78 multi-document,
27 single-source/multi-section and 15 single-section contexts. Their S1 means
are 79.69, 39.70 and 234.13 respectively. Full strata and all 60 questions,
including EN/PL/DE variants and refusal/insufficient-evidence cases, appear in
`RESULTS_TABLES.md`, `summary.json` and `per-question-ledger.csv`.

# Attribution savings versus other changes

S0 to S1 isolates discovery metadata removal: 319 populated tag/backlink field
occurrences are removed; body, headings and separators do not change. This
accounts for the entire S1 saving. No duplicate source-body text is removed.

S2/S3 reduce repeated full source identity descriptions from 441 per-passage
occurrences to 236 per-context source records. Their arithmetic repeated-registry
control avoids 130,210 characters (32,552.5 token equivalents) relative to
repeating **the same expanded registry descriptions** at each passage. This is
not a fifth measured format or a saving relative to S0. Full inline hashes,
revision/applicability fields, section dictionaries, ranges, lengths, contract
hashes and explicit boundaries cost more than the old sparse inline labels.
S1 to S2 therefore does not isolate grouping alone.

S2 to S3 isolates separator compression: 48.15 tokens per primary context on
average. Source identities, section dictionaries, passage headers, body lengths,
body text, independence notice and closing markers are identical. The resulting
net cost still exceeds S0 for 97 contexts; 22 improve and one ties.

# Near-budget and boundary limitations

| Fixture | Arm | S0 | S1 | S2 | S3 |
|---|---|---:|---:|---:|---:|
| P03-en actual selected, two fragments | B | 911 | 561 | 671 | 653 |
| P03-en actual selected, two fragments | C | 993 | 642 | 765 | 747 |
| S12-en actual selected | B | 878 | 599 | 844 | 826 |
| S12-en actual selected | C | 945 | 634 | 806 | 770 |
| S04-en actual selected | B | 842 | 364 | 617 | 599 |
| S04-en actual selected | C | 685 | 311 | 502 | 502 |
| P03-en separate whole-chunk oracle, seven fragments | B | 3699 | 1874 | 1964 | 1856 |

The full ledger is authoritative for numerical values. Per-scope figures exclude
the existing 69-character outer global wrapper (17 or 18 additional estimated
tokens after rounding). `enclosing_tokens` records the exact enclosing cost.
All primary S0 selections satisfy the per-scope cap. S2/S3 overflows are retained
as failures, not repaired. None exceeds the overall 8,000-token allocation;
this does not make a per-scope overflow valid.

The separate P03 whole-body witness remains above 1,000 in every format.
The previous 1,324-token source-union control deduplicated overlapping bodies;
the curated 991/1,008-token fixture also changed boundaries/body selection.
Neither saving can be credited to fixed-body serialization.

P03 WAL-summary coverage/retention, manifest dependencies, recovery chain and
checksum cautions remain subject to the earlier scope/domain review. S12 API
identity, session lifetime, exact returned metadata and conditional role/stop
requirements retain the historical boundaries. S04 formal-heading closure
judgments remain post-result agent review. This experiment does not settle
them, alter v2.1, or treat frozen historical completeness as semantic safety.

# Mechanical integrity, restrictions and cost

All 484 rows pass character, selected-order, source ownership, source revision,
applicability and offset checks. S2/S3 decoder round trips introduce zero
unresolved source references or newly ambiguous outer passage boundaries.
That is a mechanical result, not proof an LLM understands discontinuity.
S0/S1 retain historical boundary limitations; intra-body multi-range continuity
is unchanged in all four formats. Missing warnings outside selected bodies
stay missing; no format manufactures them or claims procedural completeness.

Four primary contexts already intersect mapped restricted regions, involving
three IDs (MINI PL page 45; XL DE pages 81 and 83). Exposure is identical across
formats, visibly flagged in S2/S3 and retained in every sidecar. No restricted
region gains positive scoring credit. All ten component restrictions and the
329 uninspected High risks remain open. No unavailable graphical evidence is
reconstructed. Body preservation is not permission to promote this corpus.

| Format | Warm median ms | Warm p95 ms |
|---|---:|---:|
| S0 | 0.200 | 0.332 |
| S1 | 0.200 | 0.331 |
| S2 | 0.461 | 0.755 |
| S3 | 0.461 | 0.760 |

Timing uses 2,400 samples per format: 120 contexts, 20 cyclic/reversed repeats.
It includes validation and serialization, excludes source construction, disk
loading, source hashing at construction, retrieval and decoding. This is a
single-machine warm measurement, not a production latency benchmark. The full
unrounded sample distribution is in `delivery/latency.json`. Validation scales
with payload length/range count; grouped encoding adds registry/framing work.
Current Python concatenation is evaluation code, not a promised linear runtime.

# Decision and single next experiment

**Investigate S1 separately; reject these S2/S3 representations at 1,000 tokens.**
The most justified next engineering experiment is a controlled paired
S0-versus-S1 answer-quality validation on these same frozen bodies, only after
reviewing the sidecar/version contract and historical continuity limitations.
It must test whether removing navigation metadata changes source ownership,
version use, warning retention or groundedness; token savings alone cannot
answer that. `FUTURE_QUALITY_PROTOCOL.md` defines the protocol and its gates.
No inference is authorized or executed by this task. No selector, extractor,
renderer deployment or new holdout is proposed here.

The narrow finding is useful: redundant navigation metadata can materially
increase context cost, especially for PostgreSQL. Full inline provenance can
also cost more than it saves. A general compact citation design and semantic
continuity remain separate open problems, not solved by these measurements.

# Validation and reproducibility

`scripts/run_isolated.py` ran preparation, collection, separate scoring and
tests. Final result: **33 passed, zero skipped** (27 pre-freeze synthetic cases
plus six frozen-data acceptance cases). Tests cover same-name/different-revision
sources, alias tampering, multi-range/omitted steps, missing external warnings,
table units/negation, Unicode/LF semantics, restricted graphics, marker injection,
historical clipping, product/scope conflicts, body/order/range identity, original
complete counts and preservation of all 13 preexisting changed files.

`REPRODUCE.ps1` repeats collection and scoring against pinned inputs using fresh
isolated directories; `analyze_results.py` regenerates tables/ledger. External
`artifact-integrity.json` seals the experiment, code snapshots, tests and report;
`final-verification.json` records frozen/source and Git preservation checks.

Only four new repository files belong to this task: this report,
`laew/eval/fixed_body_citations.py`,
`laew/eval/fixed_body_serialization_study.py`, and
`tests/evaluation/test_fixed_body_citations.py`. The preexisting modified
`docs/README.md` and 12 other uncommitted files are preserved. Nothing was
staged, committed, pushed, reset or cleaned. Production A and production
renderer files remain unchanged. No embeddings, network calls, retrieval reruns,
model answers, judges or holdout creation occurred.
