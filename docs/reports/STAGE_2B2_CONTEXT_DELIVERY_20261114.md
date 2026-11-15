---
title: Stage 2B.2 — Lightweight compact-attribution delivery experiment
date: 2026-11-14
status: rejected-experiment-original-live-configurations-retained
scope: frozen-candidate pilot replay; no sealed diagnostic or live inference
---

# Decision

**Reject compact-attribution-v1 (D1) as a replacement for the planned live
study's delivery configuration.** It reduces metadata overhead and adds a small
amount of useful evidence, but no complete pilot context is gained. In two
unsupported/clarification cases, B-D1 loses source support for the conditional
PostgreSQL 12+ procedure and startup warning. Larger admitted early fragments
can displace important later fragments under unchanged greedy ranked-fill.

The final proposed three configurations remain **original A, original B and
original C**, with the existing byte-identical 36-request offline fixture
package. No new 36-request package is needed for a rejected delivery change.
This decision does not authorize or execute the separately gated live pilot.

# Inspected implementation and root causes

Read the [scoring calibration](STAGE_2B2_SCORING_CALIBRATION_20261114.md),
[evidence audit](STAGE_2B2_EVIDENCE_AUDIT_20261114.md),
[dataset/retrieval report](STAGE_2B2_REAL_WORLD_DATASET_AND_RETRIEVAL_20261113.md)
and [answer protocol](STAGE_3C3_ANSWER_EVALUATION_PROTOCOL_20261114.md).
Inspected the frozen native candidates, existing ranked-fill renderer and scope
allocator, source-range mapper, executor/OAuth first-dispatch construction and
the previously prepared request package.

The current context builder counts attribution against the per-scope budget,
then fills in cosine order. It admits whole later fragments or skips them;
only the first fragment may be clipped. Selection is not an optimizer over
complementary facts. Its metadata attribution repeats source/section information,
tags, backlinks and type/status on every fragment.

In the pilot P03-en context, PostgreSQL document tags contain a long navigation
anchor list. This is document discovery metadata, repeated on every fragment,
not the requested technical evidence. B's two fragments spend **1,938 of 3,643
characters** on attribution; C spends **2,238 of 3,969**. This is a concrete,
query-independent reason to test smaller attribution.

Other limitations remain: multi-section requirements need several fragments;
structure-v2 repeats related-context excerpts; multiple translated identity
passages can concentrate the budget on equivalent information; lower-ranked
eligible evidence can be skipped when a larger fragment does not fit. Raw K10
evidence therefore does not establish delivered-context completeness. P02 also
has genuine candidate-pool gaps, which attribution changes cannot repair.

# One mechanism, isolated from production

`laew/eval/compact_context_delivery.py` implements only a **metadata projection**:
copy each candidate with `tags` and `backlinks` omitted, then call the unchanged
existing selector, scope allocator and renderer. Source bodies, filename, scope,
section path/header, type/status, scores and order are preserved. There is no
content deduplication, passage extraction, quota, new ranker or budget change.
Removing navigation metadata does not remove or rewrite publisher warnings.

The selector accepts candidates and existing selection settings only. It cannot
read questions, reference labels, answer facts or rubric requirements.
`compact_delivery_replay.py` is a separate, selection-only driver. It loads
frozen documents with `embed=False`, reproduces chunk serialization against
frozen hashes, verifies every native candidate and its exact source ranges,
and reproduces all 36 historical pilot contexts byte-for-byte before creating
experimental contexts. It opens no vector index and performs no retrieval.

| Variant | Historical comparator | Chunker | Native K | Policy | Scope budget |
|---|---|---|---:|---|---:|
| A-D1 | A | legacy | 2 | top2 | 500 estimated tokens |
| B-D1 | B | legacy | 10 | ranked_fill | 1,000 estimated tokens |
| C-D1 | C | structure-v2 | 10 | ranked_fill | 1,000 estimated tokens |

All retain cosine eligibility 0.3, historical chunking and 8,000 overall
allocation, including enclosing labels. Per-scope budget includes fragment
attribution but excludes the enclosing knowledge label, exactly as before.
The estimate remains `ceil(chars/4)`; actual Luna tokens are not measured.

The mechanism was selected from pilot metadata inspection, not sealed outcomes.
Synthetic checks ran first. A design declaration was recorded before pilot
quality scoring; after reviewing the pilot, the unchanged implementation and
settings were frozen as rejected. No second mechanism or parameter sweep was
attempted. The optional sealed diagnostic was **skipped** because the pilot
already exposed the adverse selection effect. No new sealed outcome informed
the choice, tuning or rejection.

# Pilot comparison under unchanged v2.1

The v2.1 rubric and scoring module were hash-checked and never edited. Context
selection writes an integrity-protected trace in one process; only afterward
does a separate scoring process read the rubric. Historical calibrated scores
were reproduced exactly from the same selected source ranges. All experimental
source ranges remain within the visible eligible native candidate pools.

| Comparator → variant | Minimum evidence coverage | Complete contexts | Critical source support across all admitted branches |
|---|---:|---:|---:|
| A → A-D1 | 35.2% → 35.2% | 3/9 → 3/9 | 10/51 → 10/51 |
| B → B-D1 | 37.0% → 38.9% | 3/9 → 3/9 | 14/51 → 14/51 |
| C → C-D1 | 46.3% → 48.1% | 3/9 → 3/9 | 13/51 → 15/51 |

The last column measures source support for all registered safety-critical
requirements, including conditional branches. It does **not** assert that
every branch applies to an answer, or that any generated answer is safe/unsafe.
The flat B aggregate hides gains and losses in different questions. P04 still
has positive technical retrieval recall N/A and is excluded from the 9-case
coverage/completeness denominator; its conditional explanation evidence is
nevertheless audited.

All three P01 variants remain complete. P02 and P03 remain incomplete in every
arm. P03-en/B gains the summarizer requirement and its optional default-off
detail, raising its minimum coverage from 2/6 to 3/6. P03-en/C gains chain support
and the associated conditional checksum-limit source, raising coverage from
1/6 to 2/6. Neither gain assembles the whole required evidence set.

| Mean over 12 pilot questions | A → A-D1 | B → B-D1 | C → C-D1 |
|---|---:|---:|---:|
| Estimated context tokens | 442.4 → 389.3 | 920.8 → 914.9 | 967.3 → 936.9 |
| Attribution characters | 633.6 → 288.2 | 1,186.4 → 697.7 | 1,219.9 → 901.8 |
| Delivered body characters | 1,131.9 → 1,264.6 | 2,480.3 → 2,942.3 | 2,630.3 → 2,825.2 |
| Unique attributed source characters | 1,131.9 → 1,264.6 | 2,447.3 → 2,942.3 | 2,216.6 → 2,395.4 |
| Repeated same-source characters | 0 → 0 | 33.0 → 0 | 209.8 → 228.6 |
| Distinct sources | 1.33 → 1.42 | 2.33 → 2.83 | 2.25 → 2.50 |
| Distinct source/section pairs | 1.42 → 1.50 | 2.83 → 3.33 | 2.58 → 2.83 |

Greater source diversity is not a semantic complementarity guarantee. The
redundancy measure counts exact repeated source ranges, not translated or
paraphrased duplicates. D1 does not deduplicate content; C's absolute repeated
source text increases as more related-context text is delivered. Source bodies
are unchanged apart from the historical renderer's permitted first-fragment
prefix clipping, whose visible ranges are mapped exactly.

Selection/render timings exclude source loading, retrieval and model calls.
For each of 36 pilot pairs, 20 warm repetitions alternated baseline/experimental
order: 1,440 timed selections total. Median milliseconds are A 0.0310→0.0355,
B 0.1204→0.1070 and C 0.1524→0.1500. Corresponding p95 values are
0.0525→0.0548, 0.1727→0.1698 and 0.2005→0.2223. These tiny local timings do
not establish production or model-response latency improvements.

# Complete regression and availability analysis

There are no pilot complete-to-incomplete or minimum-coverage regressions.
There are exactly **two requirement-support regression cases**, both B-D1:

| Case | What changed | Meaning |
|---|---|---|
| P04-pl | The late `postgresql-17-recovery-config` range `[1158,1845)` is displaced by `postgresql-17-continuous-archiving` `[35666,36633)`. | Normal 12+ settings remain in `[360,1356)`, but `recovery.conf` startup prohibition `[1358,1412)` is lost. |
| P04-de | The same late recovery-config range is displaced by continuous-archiving `[34599,35219)`. | The same conditional normal-settings-plus-startup-warning proof becomes incomplete. |

P04-en/B-D1 gains that conditional proof; P03-en/B-D1 gains summarizer support.
Those gains offset the two critical-support losses numerically. They do not
erase the regressions. A correct major-version clarification can still answer
P04, but if the future answer gives a 12+ procedure, the startup condition remains
mandatory under v2.1. Losing the supplied warning matters even though the
question's minimum clarification score is N/A for retrieval recall.

P03-en/C-D1's chain/checksum support is the only other requirement gain. All
remaining pilot question/variant pairs have unchanged registered requirement
support. Optional and alternative requirements are included in the detailed
gain/loss file rather than hidden behind aggregate recall.

Availability flags must also be compared against their baseline. The absolute
experimental exposure flag for **P02-en/C-D1, MINI PDF 45** was already present
in historical C. Selected bodies and source ranges in this case are identical;
only metadata rendering is smaller. Its explicit unavailability notices remain
verbatim. There are **zero new restricted-region exposure cases**. This existing
notice is not technical evidence or a new graphical interpretation. All ten
restrictions and 329 uninspected High findings remain open.

The experiment shows a reusable failure mode: a cost reduction can admit an
earlier long fragment that was previously skipped, which then crowds out a
later warning. D1 preserves individual admitted bodies but does not preserve
the baseline's evidence set. Repairing that behavior would be a separate
selection change, outside this one-mechanism experiment. No such repair was
implemented or tuned here.

# Final three-arm live study and fixtures

Retain exactly the existing configurations:

| Live configuration | Chunker | Native K | Selector | Scope budget | Delivery |
|---|---|---:|---|---:|---|
| A | legacy | 2 | top2 | 500 | Historical attribution |
| B | legacy | 10 | ranked_fill | 1,000 | Historical attribution |
| C | structure-v2 | 10 | ranked_fill | 1,000 | Historical attribution |

Use the unchanged v2.1 evaluation rubric. The canonical first-dispatch package
remains `laew-evidence-audit-v1/generator-only` in the external artifact root.
Its manifest and all **36 requests** were verified unchanged. D1 is not silently
renamed B/C or substituted into any request. Experimental pilot contexts are
retained for review, but no new 36-request live fixture package was generated.
The separately gated attempt limit, telemetry, provider preflight, reviewer
acceptance and live authorization requirements remain in force.

The generator payload contains the unchanged question plus source context and
shared instructions, with no extra questions, gold labels, rubric requirements
or reviewer notes inserted as evidence. A synthetic compact-context check also
verifies the real first-dispatch serializer preserves the context and warning
with fixture credentials and intercepted transport: zero network/model calls.

# Tests, integrity, reproduction and changed files

**85 tests passed**, without skips, using `scripts/run_isolated.py`: nine new
checks for complementary-warning delivery, unchanged bodies/attribution,
no-metadata baseline identity, budgets/order/scores, top2 bounds, eligibility,
scope/duplicate guards, honest clipping, first dispatch, and greedy displacement;
plus the 76 existing calibration, scorer, dataset, selector and chunker checks.
No live service or real credentials were used.

The external experiment directory is:

`C:\Users\korne\.codex\visualizations\2026\11\14\01a1da01-8abc-7562-a1bb-4ff142d78912\laew-context-delivery-v1`.

It contains the design declaration, immutable rejected-mechanism freeze,
pilot delivery traces/integrity, metrics/timing, all per-question v2.1 scores
and regressions, baseline-versus-experimental availability comparison, exact
final live-study plan, code snapshots, initial/final Git state, test log and
validation receipt. Historical corpus/dataset/trace/calibration/package hashes
are rechecked; scoring and original request fixtures are unchanged.

The two new evaluation-only modules are `compact_context_delivery.py` and
`compact_delivery_replay.py`; focused tests and this report are added. The
documentation index receives one additive entry. All nine initially modified/
untracked files were snapshotted; the eight non-index files remain byte-identical
and initial index content is preserved. Production code/configuration, existing
evaluation modules and every historical output remain unchanged. No Git add,
commit, push, reset or clean ran.

To reproduce, use a new external output location with the current pinned code:

```powershell
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.compact_delivery_replay `
  --corpus 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-freeze-v1' `
  --run 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-retrieval-20261113-v2\run-v2' `
  --trace-sha 'e91d52ea4209fc44dc32faaa22ad5e8adda13367939f6e21fc3db20116cb342a' `
  --split pilot --output pilot-delivery
```

Copy retained output into the external package within the same shell invocation,
verify its manifest, then use the preserved `score_delivery.py --split pilot`
in a fresh sibling package to apply the unchanged v2.1 rubric. Latency samples
will vary; selected text, source ranges and quality metrics are deterministic.
Do not overwrite this experiment or use sealed outcomes to tune a replacement.

**Hard stop respected:** no embeddings, index creation/modification, new
retrieval, Luna call, live answer, LLM judge, provider access or production change.
This remains exploratory evidence from an already-observed pilot. No independent
human validation or generalization claim is made.
