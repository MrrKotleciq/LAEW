---
type: report
title: Stage 2B.2 hybrid retrieval with RRF — Task 2
date: 2026-11-10
status: experimental-pending-task-3-approval
scope: isolated dense, FTS5 and RRF retrieval plus ranked_fill
---

# Stage 2B.2 — Hybrid retrieval with RRF, Task 2/3

**Recommendation: retain dense-only for the approved D10/M10/1000 validation
configuration. Do not adopt equal-weight RRF as the default experimental retrieval
policy or integrate it into production on these results.** RRF sometimes recovers
evidence at shallow depth, but provides no final-coverage gain over primary dense
K10 and causes substantial holdout v2 regressions. More backend candidates do not
solve the fixed-final-budget problem. Task 3 requires user approval.

## Implementation and review

Reviewed `lexical_experiment.py`, `evidence_selection.py`, both existing evaluators,
Chroma source reconstruction and scope checks, synchronization/freshness generation
locks, and the Task 1 report. Existing Chroma query and FTS5/tokenizer implementations
remain unchanged; native local Chroma Search API is not used. No infrastructure,
model, source allowlist, routing, Horizon/reranker or production index was changed.

`rrf_experiment.py` is a separate reusable component. Each ranking carries the same
corpus/scope/project Binding. The caller supplies canonical records from the
already-authorized scope, independently of relevance labels. Unknown IDs are
removed before rank assignment; scope/binding mismatches and conflicting text,
path or metadata for a known ID fail closed. Canonical comparison catches a stale
slot payload, but is **not** a replacement for a future dual-store generation barrier.
Global and Project are processed separately; no scores cross scope boundaries.

Dense eligibility remains cosine >=0.3. FTS5 contributes its literal matches with
native negative BM25 scores; cosine thresholds are never applied to BM25. The
unchanged native relevance gates and source authorization run before fusion.
Within each backend, repeated IDs contribute once, at their first eligible position;
rejected/duplicate hits do not leave rank gaps. RRF is
`1/(60+dense_rank) + 1/(60+lexical_rank)`, omitting an absent backend contribution.
Equal fused scores sort by stable chunk ID. Original cosine, BM25, backend ranks,
source and metadata remain attached; lexical-only evidence has `dense_score=None`.
Ranks, not incompatible scores, determine fusion. There are no weights, query
exceptions, language rules or parameter changes after scoring. Inputs are bounded
to 512 hits/backend and output to 128.

Lexical I/O/SQLite operational failure returns the exact eligible dense ordering
and original scores, with an explicit unavailable/fallback diagnostic. An empty
lexical match list is a normal result. Binding/payload errors and dense failures
surface rather than being hidden by fallback. Tests cover these distinctions.

The previous selector's `Candidate.cosine` contract cannot honestly represent
lexical-only evidence. Added experimental `ranked_fill`/`select_ranked_scopes`
entry points for **pre-vetted ordered pairs**, sharing the existing renderer and
scope allocator. They do not invent cosine values, re-sort RRF, or change the old
cosine-gated entry/defaults. Both retain provenance/citation/formatting overhead,
first-fragment clipping and later-fragment skipping. No public runtime/tool schema
or production RAG contract changed. Calling the pre-vetted entry is not itself
authorization; any future integration must enforce the caller contract below.

## Method and fair candidate limits

Protocol: `tools/hybrid/PROTOCOL.md`, fixed before scoring. Reuse Task 1's full
corpus/vector cache and final original-insertion-order dense/FTS5 rankings. Verify
their shared hash; do not reinterpret the earlier sorted-insertion sensitivity
run as the baseline. No new embedding/model calls or quality indexes are needed.
All labels, chunks and tokenizer files remain frozen.

**D** is retrieval depth per backend per scope. **M** is the final candidate cap
per scope for every method, including dense-only and BM25-only. Compare
`(D,M)=(5,5),(10,10),(20,20),(50,50),(20,10),(50,10)`. Counts are capped by available
eligible matches; there is no padding or cross-scope allocation of rank slots.
Report the authorized eligible union before final truncation, not just the best
fused candidates. At D10, mean union sizes are 14.6 legacy/13.3 v2 on holdout and
18.0 on stress, while each method still returns at most M10 per scope.

Four frozen datasets, both legacy/v2, plus the exact 1036-chunk legacy stress
corpus produce **3420 method/query/configuration rows**. For M10 only, run existing
ranked_fill at **1000 estimated tokens/scope** and the manifest's **8000 overall
RAG allocation**: **1710 selections/replays**. The overall cap includes outer scope
labels; inner attribution/separators count against each scope ceiling. No query
complexity heuristic or context-budget tuning is used.

Coverage is macro exact labeled-atom availability over answerable queries, with
source/section constraints. Complete evidence requires every atom. Qrel-irrelevant
document rates and no-labeled-atom rates are separate diagnostics; unlabelled
background is not necessarily useless. Costs/counts include unsupported queries.
Scope-local atom positions avoid pretending that hybrid scopes share a ranking.
These small authored datasets have correlated sources; no significance or answer-
quality claim is made.

## Candidate availability

Primary D10/M10 candidate atom coverage:

| Dataset | Chunker | Dense | FTS5 | RRF | Eligible union |
|---|---|---|---|---|---|
| baseline | legacy / v2 | 100% | 64.58% | 100% | 100% |
| hard | legacy / v2 | 100% | 81.82% | 100% | 100% |
| holdout | legacy | 96.43% | 75.60% | 94.64% | 96.43% |
| holdout | v2 | 100% | 77.38% | 96.43% | 100% |
| supplement | legacy / v2 | 100% | 84.38% | 100% | 100% |
| stress | legacy | 77.78% | 33.33% | 77.78% | 77.78% |

Holdout candidate complete evidence drops from dense 92.86→89.29% on legacy and
100→92.86% on v2. At D10, lexical retrieval adds no new labeled union evidence over
dense on these datasets; rank fusion can still discard dense evidence at M10.

| Holdout chunker | D=M | Dense coverage | FTS5 coverage | RRF coverage |
|---|---|---|---|---|
| legacy | 5 | 87.50% | 70.24% | 91.07% |
| legacy | 10 | 96.43% | 75.60% | 94.64% |
| legacy | 20 | 100% | 82.74% | 98.21% |
| legacy | 50 | 100% | 87.50% | 100% |
| v2 | 5 | 96.43% | 70.24% | 89.88% |
| v2 | 10 | 100% | 77.38% | 96.43% |
| v2 | 20 | 100% | 85.71% | 100% |
| v2 | 50 | 100% | 89.29% | 100% |

Near-complete K50 fixture availability is a small-corpus ceiling, not proof of
efficient evidence delivery or large-vault retrieval. M50 is not the validated
final-selection setting.

## Final ranked_fill evidence and context

Primary D10/M10, budget 1000/scope:

| Dataset/chunker | Final coverage dense / FTS5 / RRF | Complete dense / RRF | Mean tokens dense / RRF | Mean fragments dense / RRF |
|---|---|---|---|---|
| baseline legacy | 100 / 64.58 / 100% | 100 / 100% | 431 / 439 | 7.96 / 8.14 |
| baseline v2 | 100 / 64.58 / 100% | 100 / 100% | 450 / 461 | 8.36 / 8.57 |
| hard legacy | 100 / 81.82 / 100% | 100 / 100% | 707 / 881 | 8.15 / 7.77 |
| hard v2 | 100 / 77.27 / 100% | 100 / 100% | 800 / 883 | 5.85 / 6.15 |
| holdout legacy | 94.64 / 73.81 / 94.64% | 89.29 / 89.29% | 872 / 962 | 9.62 / 9.09 |
| holdout v2 | 96.43 / 72.02 / 89.88% | 92.86 / 82.14% | 982 / 975 | 6.81 / 6.75 |
| supplement legacy | 100 / 84.38 / 100% | 100 / 100% | 626 / 681 | 9.45 / 9.60 |
| supplement v2 | 100 / 84.38 / 100% | 100 / 100% | 854 / 846 | 8.50 / 8.45 |
| stress legacy | 77.78 / 33.33 / 77.78% | 66.67 / 66.67% | 915 / 972 | 8.00 / 8.75 |

RRF adds no final-coverage gain to primary dense. Legacy holdout cost rises 10.4%
without coverage gain. Hard legacy cost rises 24.7% despite selecting fewer, longer
fragments. Qrel-irrelevant fragment rates dense→RRF are holdout legacy 66.9→67.4%,
v2 67.0→69.0%, hard legacy 67.0→65.3%, hard v2 61.8→63.7%. A lower rate alone does
not prove better context utility. Holdout token p95 is 1033→1192 legacy,
1245→1216 v2; costs are chars/4 estimates, not tokenizer-exact or full prompt costs.

Increasing depth while retaining M10 is worse:

| Holdout | RRF D10 final coverage | RRF D20 final coverage | RRF D50 final coverage |
|---|---|---|---|
| legacy | 94.64% | 93.45% | 91.07% |
| v2 | 89.88% | 82.74% | 86.31% |

At D50/M10, stress RRF candidate coverage falls to 66.67% and final coverage to
33.33%, versus primary dense 77.78%. More available candidates can promote overlap
and consume budget without adding useful evidence.

## Multilingual, multi-document and named regressions

At primary D10/M10, holdout final cross-language coverage dense→RRF is legacy
89.29→89.29%, v2 **92.86→79.76%**. Multi-document final coverage is legacy
78.57→78.57%, v2 **85.71→73.81%**. Other primary fixture groups retain their dense
coverage; this does not establish general multilingual performance. Unsupported
candidate empty rate stays 25% on baseline and 0% on hard/holdout/supplement/stress.
No no-answer/sufficiency gate or answerability guarantee is introduced.

- **u17:** legacy D5 dense misses the atom; the union/RRF recover it, RRF rank 4.
  At primary D10 dense already has it, and RRF retains it at rank 3. V2 already has
  the atom at D5; this is not independent evidence of a universal hybrid gain.
- **u27:** at primary final candidate truncation, legacy and v2 lose one of two
  atoms compared with dense. Dense's context budget already loses that atom, so
  the final metric alone conceals the extra retrieval loss.
- **u22 v2:** one atom is lost at M10 rather than merely at the context budget.
- **u08 v2:** candidate evidence survives, but RRF order causes final coverage
  100→0% at the 1000-token budget. **u21 v2:** 100→66.67%; **u24 v2:** 100→50%, also
  context-budget losses. These explain the primary final v2 regression.
- **Known lexical cross-language failures:** fusion does not translate queries.
  It often retains their dense hits, but the u08/u21/u24 losses show that retained
  union evidence is insufficient when order and budget are applied.
- **s14:** in the small supplement all three methods retain the atoms. In stress,
  Task 1's exact cosine places the shared acceptance fragment at rank 66, lexical
  rank 1028, beyond every tested backend depth. Union availability stays 1/3. RRF
  keeps the prerequisite at ranks 3/6/26 for D=M5/10/50; at D50/M10 it loses even
  that atom. No fusion can recover an atom absent from its input union.

RRF60 favors agreement strongly within these depths: two rank-50 contributions
sum to 2/110, exceeding a single rank-1 contribution 1/61. This explains why weak
overlap can outrank strong dense-only multilingual evidence; it is not a reason
to tune the constant or add filename/query exceptions after inspecting labels.
Per-query positions, newly recovered/lost atoms, worsening ranks, native scores
and loss stages are retained in the details/summary artifacts.
At primary D10/M10, 54 of 161 answerable query/chunker pairs have at least one
worsened surviving atom position under RRF; lost atoms are recorded separately.
These source-correlated pairs are not independent statistical units.

## Latency, resources and validation

Fresh local dense/unchanged FTS5 indexes use cached vectors in temporary storage;
no model or production service is called. Twenty warm repetitions per operation,
28 global-scope holdout queries and four related stress queries, legacy only:

| Corpus / depth | Dense median ms | FTS5 median ms | Fusion-only median ms | Sequential hybrid median ms | Paired extra median ms |
|---|---|---|---|---|---|
| holdout D5 | 1.704 | .523 | .116 | 2.434 | .713 |
| holdout D10 | 2.015 | .593 | .223 | 2.966 | .922 |
| holdout D20 | 2.728 | .665 | .413 | 3.887 | 1.181 |
| holdout D50 | 4.594 | .678 | .532 | 5.859 | 1.272 |
| stress D5 | 1.736 | 1.839 | .104 | 4.009 | 2.303 |
| stress D10 | 1.831 | 1.882 | .192 | 4.394 | 2.553 |
| stress D20 | 2.062 | 2.050 | .365 | 4.830 | 2.726 |
| stress D50 | 2.818 | 2.318 | .864 | 6.216 | 3.479 |

These are medians of query medians, M10, excluding query embedding, final rendering
and network-server transport. Paired overhead uses each query's difference, so it
need not equal a difference between aggregate medians. Per-query p95 distributions
are retained. No claim is made about production latency or million-chunk scaling.

Additional FTS5 storage is 155648 bytes (holdout) / 1744896 bytes (stress).
Open/build costs are 24/104ms. The observed working-set step after adding FTS5 to
warm dense is approximately .80/.84 MiB, not an exact allocation bound. Fusion-only
separate tracemalloc peaks are at most 14940 bytes at D10 and 87284 bytes at D50.
Process lifetime peaks include cached JSON loading and are not fusion/index RAM.
No new dependency, model download, Docker service or inference was needed.

**1589 passed, 4 skipped, 2 deselected, 39 warnings**, full offline suite in
186.13s via `scripts/run_isolated.py`. All **190 primary dense controls** match the
old selector entry; independently, **186 frozen historical fixture controls**
match exact atom coverage, rendered estimated tokens and selected ID/order.
All **1710/1710 contexts** reached the real executor/llama.cpp payload serializer
with mocked transport, no tools/history and fixture-forced scopes; zero overall
RAG allocation violations. This verifies delivery, not routing or generated answers.

## Task 3 design constraints and files

Do not deploy RRF60/M10 on this evidence. Retain dense-only; keep RRF as an explicit
experimental control. Alternative fusion strategies would require a separately
declared experiment and broader independently judged natural multilingual/code
queries. Do not pick a winner solely from u17 or synthetic stress.

For Task 3, document/design rather than silently implement: one authorized scope/
project identity, shared source/chunker/tokenizer/model fingerprints, consistent
generation publication across Chroma and lexical stores, locking across retrieval,
delete/rename/reindex handling, stale/partial-generation rejection, tested rollback
and visible lexical-unavailable dense fallback. Matching hit payloads cannot detect
missing newly added records or prove whole-index freshness. No production
dual-index coordinator, transaction claim, switch or migration was implemented.

Changed existing experimental file: `laew/rag/evidence_selection.py`; its old
behavior is preserved. New code/tests: `laew/rag/rrf_experiment.py`,
`laew/eval/hybrid_rrf_benchmark.py`, `tests/rag/test_rrf_experiment.py`,
`tests/evaluation/test_hybrid_rrf_benchmark.py`. New protocol:
`tools/hybrid/PROTOCOL.md`. Documentation: this report and `docs/README.md` entry.
Artifacts use `docs/reports/hybrid-rrf-20261110-*`: input-state hashes, controls,
details, summary/query CSV, performance, regression log and final state/Git status.

Reproduce with `scripts/run_isolated.py --keep-diagnostics eval
laew.eval.hybrid_rrf_benchmark analyze --corpus <absolute Task1 corpus.gz>
--retrieval <absolute Task1 final details.gz> --output docs/reports/<details.gz>`;
`performance --corpus <absolute corpus.gz> --repeats 20`; `export --input
<absolute details.gz>`, each with an output path. Outputs stay in the printed
temporary run directory; only artifacts are copied back. Prior source, fixture,
tokenizer, report and working-tree changes are preserved. No commit/push or
production integration occurred. **Stop pending approval before Task 3.**
