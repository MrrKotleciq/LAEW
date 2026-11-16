---
title: Stage 2B.2 — Complementary evidence context selection
date: 2026-11-15
status: rejected-development-experiment
scope: frozen native candidates; 60 exposed development questions; no model work
---

# Decision

**Reject both experimental versions as replacements for ranked_fill.** Joint
redundancy-aware packing reduced repeated text but lost necessary evidence.
Adding a baseline-body preservation constraint removed those regressions, yet
produced only one additional minimum requirement, no new complete contexts,
and slightly more repeated text. Keep B as the development baseline, C as a
comparison, and production A unchanged. No selector is deployed or promoted.

This experiment does **not** establish that a lightweight selector generally
cannot help. It shows that this small lexical coverage mechanism does not
deliver a material, reliable improvement at native K10 / 1,000 estimated tokens.
The 60 exposed questions represent 20 dependent intent families. All results
are development diagnostics under provisional agent-authored v2.1 proofs,
not independent validation, statistical superiority or answer-quality scores.

# Diagnosis and integrity before implementation

The separate [pre-implementation root-cause report](STAGE_2B2_COMPLEMENTARY_SELECTION_ROOT_CAUSE_20261115.md)
was written before the selector. All six requested reports, prior novelty/D1
experiments, production ranked_fill/attribution, native traces, source mapping
and repaired offline scorer were reviewed. The user's current instruction
explicitly authorizes this new development study; historical stop recommendations
are not treated as authorization for inference or production changes.

Verified the 777-file source freeze, all 201 historical retrieval artifacts,
pilot v4 and sealed v3 manifests, sanitized 60-question inputs and calibration
package before reuse. Reconstructed both chunkers with `embed=False` and checked
all frozen chunk hashes, candidate text, source/version hashes and visible ranges.
Reproduced **180 historical contexts byte-for-byte and 540 v2.1 stage scores**.
The repaired scorer's evidence outputs match the historical calibrated outputs.
No historical dataset, rubric, trace, score or source was modified.

Key limitations remain distinct:

- P02/B lacks registered minimum evidence in K10; changing selection cannot
  repair this. C has some cleaning/first-layer material, but no complete minimum.
- P03-en/B has complete raw minimum evidence but selected coverage is only 2/6.
  P03 PL/DE also has retrieval gaps. The final variant does not repair P03-en.
- S11-en retrieves only MMU3 passages in B/C, omitting the necessary MK4S side.
  S07 and S13 also require complementary sections or distinct versions.
- B/C lose 38/32 supported requirement instances on answerable rows during
  selection. The all-question branch ledger adds one unsupported-case loss for B.
  Counts include conditional/optional requirements, not independent observations.
- Repeated related context and navigation attribution consume budget. Shortening
  attribution alone was already known to displace useful later fragments in D1.

# Algorithm and development history

`laew/eval/complementary_context_selection.py` is a new evaluation-only module.
It accepts the query, original cosine-scored candidates and ordinary metadata.
It performs no retrieval, corpus expansion, embedding, file read, label access,
answer access, model ranking or semantic warning classification.

Both versions enumerate feasible subsets of at most ten eligible candidates
(at most 1,023 nonempty subsets). Every admitted body is unchanged and whole;
only copied `tags` and `backlinks` discovery metadata are omitted. Existing
scope, file identity, section path, type/status and source/version-bound trace
identity remain. Rendering and scope allocation reuse the historical functions.
Original metadata and candidate objects are never mutated. A historically
clipped baseline falls back verbatim rather than creating a new partial procedure.

For subset S, maximize:

```text
sum over unique 3-word shingles [max original cosine among selected carriers] / 100
+ 0.10 * sum over source identities [max selected cosine]
+ 0.10 * sum over source/section identities [max selected cosine]
+ 0.20 * fraction of query word types appearing in selected bodies
```

Unicode case-folded lexical shingles are an information-gain proxy. They do
not establish semantic equivalence, warning applicability, contradictions or
cross-language duplication. Numbers and negations are not removed from bodies.
No warning keyword creates an inferred dependency or special score. Source
and section bonuses are soft, with no quota or forced document substitution.
Exact rendered cost, separators and metadata determine feasibility; lower cost,
then stable input order resolve objective ties. Scores never cross scopes.

| Version | Constraint | Motivation and outcome |
|---|---|---|
| complementary-pack-v1 | Retain the strongest baseline body | Joint packing differs from greedy token-set novelty and metadata-only D1. Synthetic tests, pilot, then all 60 questions exposed lost complementary requirements. Rejected. |
| complementary-pack-v2 | Retain **all** baseline-delivered bodies | The single planned refinement protects unknown prerequisites and warnings without reading labels. Same objective/weights, no parameter sweep. Frozen before its pilot/full scoring. No evidence regressions, but negligible gain. Rejected. |

The final implementation retains both versions. No further tuning followed the
v2 result. At fixed K10, exact enumeration is small; lexical preprocessing and
bitsets plus subset cost storage are bounded. The approach is substantially
smaller than document routing, learned ranking or a dependency graph, but still
adds complexity that these results do not justify.

All B/C experiments keep legacy/structure-v2 respectively, dense cosine, native
K10, eligibility 0.3, 1,000 tokens per scope and the unchanged 8,000 overall
allocator. Production A remains legacy/K2/top2/500. No new vectors are necessary:
all native scores/text/metadata are reconstructed from frozen traces and sources.

# Results across all 60 development questions

Minimum coverage and complete counts use **48 answerable variants**. The other
12 retain N/A positive technical recall and remain included in cost, conditional
support and exposure measurements. A uses its historical smaller K/budget.

| Arm | Minimum coverage | Complete / 48 | Critical support / 132 | Condition support / 147 | Supported in native pool, lost in context | Mean tokens |
|---|---:|---:|---:|---:|---:|---:|
| A, unchanged | 22.40% | 5 | 24 | 24 | 22 | 395.5 |
| B, unchanged | 39.93% | 13 | 45 | 46 | 39 | 922.2 |
| B + v1 | 36.11% | 12 | 39 | 39 | 50 | 979.3 |
| B + v2 | 40.63% | 13 | 47 | 48 | 36 | 929.4 |
| C, unchanged | 42.53% | 18 | 43 | 46 | 32 | 907.9 |
| C + v1 | 28.65% | 10 | 31 | 31 | 60 | 967.7 |
| C + v2 | 42.53% | 18 | 43 | 46 | 32 | 920.9 |

Critical support is the fixed ledger of source-backed safety-critical
requirements across all admitted branches. Condition support includes safety
requirements and explicit conditional triggers. These denominators deliberately
do not change when a different minimum method is selected. They include potential
branches, **not inferred advice applicability or safe-answer counts**. The
native-loss column uses the same all-requirement support ledger, including
optional and unsupported-question branches. Complete minimum methods remain
coherent, with all their own applicable conditions checked by v2.1.

## Gains, regressions and warning preservation

V1 changes support on three B rows positively and ten negatively; C has one
positive and seventeen negative rows (some changes affect optional branches).
The complete-context losses are S13-en/B, and S01-en, S03-en/pl/de,
S06-pl/de, S08-pl and S13-en/C. There are no complete-context gains;
all nine complete changes are fully paired in the external ledger.
Important lost critical support spans P03's manifest, P04 version/configuration
conditions, S05 mains values, S06 model/selftest/media/rollback requirements,
S08 triage, S11 model-correct firmware path and S13 version defaults/descendant
restriction. Lower lexical redundancy and greater section diversity therefore
did not imply more complete or reliable evidence. V1 is unacceptable.

V2 has **zero lost registered requirements, critical supports or conditional
supports in all 120 paired comparisons**. Full baseline bodies and source ranges
are retained, which also protects unregistered body content mechanically.
This is source-body preservation, not a guarantee that a model would understand
or obey every condition. No answers were generated or rescored in this study.

Only two B question rows gain any registered support:

- **S12-de:** minimum coverage 0 → 1/3 by delivering the initiating-session
  lifetime requirement; an optional checkpoint-tuning passage also becomes
  available. The 17 API bundle remains partial and returned metadata is missing.
- **P03-pl:** gains the source condition concerning minimal WAL level, outside
  this question's chosen minimum method. Minimum coverage remains zero.

All other B rows tie on registered support. All 60 C rows tie. No P02/P03 variant
becomes complete. Pilot minimum coverage is unchanged; the only minimum gain is
one PostgreSQL, German, multi-document development case. These narrow gains
do not generalize across language, source or chunker strata.

The external `comparison-v1/` contains all **420 arm/question rows**, a wide
60-question CSV, every paired gain/loss/tie, requirement IDs and critical-loss
lists, plus all strata. Its `gains-regressions.md` lists every support-changing
row for both versions. No adverse row or unsupported question is omitted.

## Split and workload strata

Cells are minimum coverage / complete count. Denominators count answerable
language variants, not independent families. Old sealed questions are now
development data. Full warning, cost, diversity and exposure strata are in JSON/CSV.

| Stratum | n | A | B | B + v2 | C | C + v2 |
|---|---:|---:|---:|---:|---:|---:|
| Pilot | 9 | 35.19% / 3 | 37.04% / 3 | 37.04% / 3 | 46.30% / 3 | 46.30% / 3 |
| Old sealed | 39 | 19.44% / 2 | 40.60% / 10 | 41.45% / 10 | 41.67% / 15 | 41.67% / 15 |
| EN | 16 | 20.31% / 1 | 51.04% / 5 | 51.04% / 5 | 50.00% / 7 | 50.00% / 7 |
| PL | 16 | 25.00% / 2 | 34.38% / 4 | 34.38% / 4 | 39.58% / 6 | 39.58% / 6 |
| DE | 16 | 21.88% / 2 | 34.38% / 4 | 36.46% / 4 | 38.02% / 5 | 38.02% / 5 |
| Single-document | 18 | 33.33% / 5 | 72.22% / 12 | 72.22% / 12 | 72.22% / 13 | 72.22% / 13 |
| Multi-section | 18 | 20.83% / 0 | 20.83% / 0 | 20.83% / 0 | 33.33% / 4 | 33.33% / 4 |
| Multi-document | 12 | 8.33% / 0 | 20.14% / 1 | 22.92% / 1 | 11.81% / 1 | 11.81% / 1 |
| Prusa | 24 | 17.71% / 0 | 22.92% / 0 | 22.92% / 0 | 30.21% / 5 | 30.21% / 5 |
| Pro Git | 12 | 50.00% / 5 | 75.00% / 9 | 75.00% / 9 | 75.00% / 9 | 75.00% / 9 |
| PostgreSQL | 12 | 4.17% / 0 | 38.89% / 4 | 41.67% / 4 | 34.72% / 4 | 34.72% / 4 |

## Budget, redundancy, diversity and latency

Exact repeated-source characters count overlap of visible ranges in the same
source, including structure-v2 related context. Repeated-shingle fraction counts
duplicate lexical triples among delivered fragments; neither metric recognizes
all translated equivalents or establishes that repetition is useless.

| Arm | Mean repeated source chars | Repeated shingles | Mean attribution chars | Mean sources / sections |
|---|---:|---:|---:|---:|
| A | 3.3 | 1.73% | 513.6 | 1.30 / 1.47 |
| B | 59.4 | 9.05% | 1,036.0 | 2.17 / 3.42 |
| B + v1 | 16.3 | 3.52% | 710.4 | 2.58 / 3.92 |
| B + v2 | 69.2 | 9.13% | 729.1 | 2.27 / 3.73 |
| C | 200.3 | 13.19% | 1,017.3 | 1.77 / 2.67 |
| C + v1 | 70.7 | 5.58% | 837.8 | 2.42 / 3.88 |
| C + v2 | 214.0 | 13.44% | 791.0 | 1.95 / 2.98 |

V2 cannot discard the baseline's redundant bodies. Extra budget sometimes buys
another overlapping fragment rather than a complete new proof. Reduced metadata
overhead alone is therefore not success. Since packing and compact attribution
are combined, even the small v2 gain cannot be attributed to optimization alone;
no claim of superiority over a simpler guarded metadata mechanism is made.

All experimental contexts satisfy 1,000 tokens per scope and 8,000 including
outer scope labels. V2 maxima are B 998 and C 996; p95 is B 996 and C 994.05.
The estimator remains `ceil(chars/4)`, not Luna tokenization. No tokenizer or
embedding service was contacted.

Selection+render warm latency uses ten alternating-order repetitions for every
question/arm, 600 samples per arm/mechanism. Final p50/p95 are B **2.13/2.59 ms**
and C **2.21/2.75 ms**, versus ranked_fill **0.093/0.160 ms** and **0.129/0.203 ms**.
This excludes source reconstruction, retrieval and generation. Absolute overhead
is acceptable, but the quality gain does not justify it. Timing samples are
environment-specific and not end-to-end or service throughput measurements.

# Restrictions and semantic uncertainty

All ten corpus restrictions, 329 uninspected High findings and other inherited
risks remain open. V2 retains the baseline restricted-region intersections:
B has one exposed question and C three. These are S16-de/B, and P02-en/S16-en/
S16-de in C, touching MINI+ page 45 and XL pages 81/83. A has one historical
intersection. They remain **unavailable as positive technical evidence**; nearby
text cannot establish graphical polarity, electrical terminal location or symbol
meaning. V2 adds no new restricted-region exposure, but does not remove the old
exposure. Both B/C retain 30 questions intersecting open page-risk records;
this is an exposure diagnostic, not a count of known wrong passages.

Source/offset matching mechanically establishes delivery of a previously authored
proof. Whether every admitted proof is semantically sufficient, cross-language
equivalent or correctly scoped remains provisional. Missing registered proof
does not mean all unregistered text is irrelevant. The previous answer-entailment
and applicability disputes remain unresolved; this study changes none of them.

# Independent validation protocol proposed for a later task

Do not spend a new holdout on the rejected implementation now. After a future
algorithm stabilizes on development data, freeze its code/settings/dependencies
and candidate-only interface before authoring or opening new evaluation results.

Propose **24 new questions from 24 genuinely new intent families**, one primary
language per family: eight EN, eight PL, eight DE, balanced across Prusa, Pro Git
and PostgreSQL. Reserve approximately eight single-document, eight multi-section,
four multi-document and four insufficient/unavailable tasks. Include explicit
prerequisite, warning and version-applicability obligations. New intents must not
be translations, numeric substitutions or close procedural rewrites of the old
20 families. Select new source sections/proof combinations and disclose shared
document/version dependencies. Any later translations are secondary dependent
diagnostics, not extra independent samples.

An independent author/domain reviewer should freeze questions, complete coherent
evidence alternatives, applicability branches, bounded absence rationales and
source/version spans before candidate retrieval. A second reviewer should check
every safety/version case and all unavailable-source decisions, then adjudicate
disagreements with recorded provenance. Do not call an exposed agent an independent
reviewer. Keep questions-only selection and curator scoring in separate processes.

Use paired B and C native K10 with the frozen selector, fixed .3 eligibility,
same scope/budget/attribution rules and all-question reporting. Predeclare minimum
coverage, complete-context count, fixed conditional-support ledger, direct
restricted exposure, source overlap, tokens and selection latency. Require a
material complete-context or essential-evidence gain without lost applicable
safeguards or increased restricted exposure; define the materiality threshold
before outcomes. Review all regressions, especially version conflicts. Report
family/source clusters and small denominators without claiming statistically
validated population superiority from a 24-question study. Retire that holdout
to development if its outcomes guide any further change. No questions were
generated, no holdout was opened, and no answer generation is part of this proposal.

# Artifacts, reproduction and tests

External package, outside Git and Obsidian:

`C:\Users\korne\.codex\visualizations\2026\11\15\01a1e0fc-bdd1-7270-b6a8-0c30a576f884\laew-complementary-selection-v1`

- `root-cause-v1/`: diagnosis, all historical stage checks and integrity receipts.
- `versions/v1/`, `versions/v2/`, `final-mechanism-freeze.json`: preserved code,
  tests, settings and iteration motivation.
- `v1-pilot-*`, `v1-all-*`, `v2-pilot-*`, `v2-all-*`: immutable selected texts,
  source identities/ranges, metrics, timing, provenance and separate scorer outputs.
- `comparison-v1/`: 60-question wide CSV; all 420 rows in JSON/CSV; all strata;
  every paired support change, loss and tie. `make_comparison.py` reproduces them.
- `tests-final.log`, final verification, code snapshots and package manifest:
  preservation, reproduction and audit. No saved Luna answers are included.

| Artifact | SHA-256 |
|---|---|
| Final mechanism freeze | `0a5e0b5b23aae4cfc167f7388a6e09e8d7ef68f12a1c2f1fb011065cefc136b6` |
| V1 full delivery manifest | `877c790dcd2c922e27640e5d4715c49db77cc705dd0bbe5b475ee4fb92070d13` |
| V1 full score manifest | `9bc26749040b1b1760c6a6ac4a13ad7be51d191a4dd59284d73761f29ab3356b` |
| V2 full delivery manifest | `3d3cc888cda7369a9a12e0b6c01aca29b8eab15cf867afb4c1f2d108f8bb829a` |
| V2 full score manifest | `0e45f503d7cb07a2a00cadba05b114a8ac4dcf5095e035d2d80819f95286242c` |
| Combined comparison manifest | `930e1e696965e33acaf85b9fc517d4369dcdd9a314272e1eed57858b03742fdf` |

Reproduction uses the repository venv and `scripts/run_isolated.py`:

```powershell
$config = '<external-package>\study-config.json'
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.complementary_context_study collect --config $config `
  --split all --version complementary-pack-v2 --output fresh-delivery
# Copy the retained run's work/fresh-delivery into a NEW external directory.
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.complementary_context_study score --config $config `
  --delivery '<copied-fresh-delivery>' --output fresh-score
```

`diagnose` reproduces the historical diagnosis separately. Selection invokes
`load_inputs(scoring=False)` and cannot open rubric/labels through that path;
only the separate scoring invocation loads them. Socket connections are blocked
throughout the study. Fresh output paths are required; preserve every original.

**127 tests passed, zero skipped**, using `scripts/run_isolated.py`. These include
26 synthetic selector contracts, six study integrity/acceptance checks (including
all 240 full-development version replays), existing source/label integrity,
v2.1 calibration, repaired synthetic applicability, rejected D1 and historical
selector/chunker regressions. No live service or model is used. An initial command
used an absolute `--output`, which the isolation runner correctly rejected before
execution; all study runs then used confined relative output plus verified copies.

New repository files are the two evaluation modules, their two test modules,
the root-cause report and this final report. All five initially dirty/untracked
files, including `docs/README.md` and the repaired scorer, remain byte-identical
to their initial snapshot. Final Git status lists these preserved changes plus
the six new files. No Git add, commit, push, reset or clean occurred. No production
code/configuration, frozen corpus/dataset or historical result was edited.

**Hard stop respected:** zero retrieval reruns, embeddings, Luna requests,
answer generation, LLM judges, model downloads, paid API calls, service changes,
deployments or future holdout questions. The final recommendation is rejection,
not a request to launch another model test.
