---
title: Stage 2B.2 — Retrieval and context-budget bottleneck diagnosis
date: 2026-11-16
status: completed-reference-informed-development-diagnostic
scope: 60 exposed questions; verified saved vectors; no model inference
---

# Finding

Candidate retrieval is the largest **registered-proof completeness** limitation:
27/48 B/K10 and 27/48 C/K10 candidate pools lack a complete minimum method.
Selection is the largest immediately demonstrated improvement opportunity at the
fixed budget: B/K10 delivers 13 complete contexts although 20 fit; B/K20 can fit
24 but the unchanged selector still delivers 13. Simply increasing K produces
**zero additional complete contexts in either arm**.

The 1,000-token budget is not the dominant aggregate limit. It is decisive for
P03-en: the exact cheapest complete whole-chunk set costs 3,699 estimated tokens
in B and 4,768 in C/K20. The earlier claim that P03-en/B loses evidence during
selection is mechanically true, but is **not evidence that a better selector
could deliver the whole task at this budget**. Its maximum is still 2/6.

Recommend one future experiment: **evidence-aware ranking/selection on B**, with
whole-passages, original attribution and explicit version/condition preservation.
Its K10 oracle ceiling is +7 complete contexts (+14.58 percentage points); K20
offers a further +4 only if selection can exploit the larger pool. These are
optimistic reference-informed ceilings, not a predicted real-world gain. No such
selector, extraction mechanism or architecture is developed here. Production A,
development baseline B and comparison C remain unchanged; V1/V2 stay rejected.

# Integrity, restrictions and retrieval verification

Reviewed the six requested Stage 2B.2/3C.3 reports, source mappings, frozen native
traces/scores, context renderer and v2.1 reference registry. Verified the 777-file
restricted corpus, 201-member retrieval package (including saved vectors/index),
questions-only inputs, pilot v4, former sealed v3, rubric manifest and complete
calibration package before reuse. Reconstructed 2,171 legacy and 2,185 structure-v2
chunks with `embed=False`; all payload hashes, source identities and ranges match.
Reproduced 180 historical contexts byte-for-byte and all 540 calibrated stage
scores with the existing repaired evidence scorer.

All 4,316 unique saved vector keys resolve: 4,256 source inputs plus 60 queries.
Historical model: `laew-qwen3-embedding`, Qwen3-Embedding-0.6B Q8_0, 1,024 dimensions;
weight SHA-256 `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`.
Exact model-catalog identity and exact text key the read-only SQLite lookup.
No new embedding computation, tokenizer request, service access or inference occurred.
Cache misses fail closed at the embedding stop gate. Normalizing/reusing vectors
for cosine calculations is not embedding inference.

The authoritative retrieval pass performs 480 native searches: 60 queries x two
chunkers x K10/K20 x two repetitions. It uses a byte-verified disposable copy of
the frozen Chroma 1.5.9 cosine index and the unchanged search implementation.
Original indexes are never opened by a mutable client. All index vectors match
normalized cached vectors within 1.50e-8 per component. All 120 K10 rankings and
scores reproduce history exactly; every repeated native ranking is stable.

Maximum native-vs-float64 direct-cosine difference is 7.73e-07; the declared numeric audit tolerance is 2e-6.


Two tie effects were inspected and disclosed **before interpreting results**:

- S15-de/C: the K20 prefix changes the tenth ID among EN/PL/DE copies of the exact
  same anchor-only body and identical vector. K10 itself matches history. This is
  an insufficient-context question, excluded from positive completeness metrics.
- P01-de/B: native and exact K20 differ only at the twentieth boundary between
  identical anchor-only bodies/vectors. The native K10 prefix is unchanged.

The native outputs, distinct source identities and original ordering are retained;
no tie-breaking or ranking repair is introduced. `ranking-tie-review.json` binds
both cases to exact body hashes and cached vectors. For all 48 answerable variants,
the historical K10 prefix is preserved in K20. Eligibility remains cosine >=0.3;
there are zero lost registered requirements due to that threshold.

All ten source restrictions, 329 uninspected High findings and other inherited
risks remain open. Restricted component ranges cannot earn proof credit; all
112 reference atoms were checked to exclude them. No diagrams, unavailable facts,
source revisions, question wording, labels, rubric, historical scores or model
answers were changed. No saved model answer was read for this diagnosis.

# Candidate, actual and oracle results

Coverage is macro minimum-requirement coverage within one coherent v2.1 method.
All completeness counts below use the same **48 answerable variants** (16 intent
families). The other 12 variants have N/A positive technical recall. This is not
the historical full-span bundled-fact metric or an answer-quality evaluation.

| Configuration | Candidate evidence coverage | Actual delivered coverage | Oracle coverage | Actual complete contexts | Oracle complete contexts |
|---|---|---|---|---|---|
| B/K10 | 53.99% | 39.93% | 52.26% | 13/48 | 20/48 |
| B/K20 | 65.97% | 39.93% | 64.24% | 13/48 | 24/48 |
| C/K10 | 55.56% | 42.53% | 54.17% | 18/48 | 21/48 |
| C/K20 | 60.76% | 42.53% | 58.33% | 18/48 | 23/48 |


An exact reference-relative decomposition of incomplete contexts separates absence
of a complete candidate proof, inability to fit a candidate-complete proof, and
failure to select an available feasible proof. It is a diagnostic partition;
individual rows can also contain several simultaneous losses.

| Configuration | Candidate incomplete | Complete candidate but cannot fit | Fits but actual incomplete | Actual complete |
|---|---|---|---|---|
| B/K10 | 27 | 1 | 7 | 13 |
| B/K20 | 23 | 1 | 11 | 13 |
| C/K10 | 27 | 0 | 3 | 18 |
| C/K20 | 24 | 1 | 5 | 18 |

| Configuration | Coverage deficit: retrieval | Coverage deficit: whole-chunk budget | Coverage deficit: selection |
|---|---|---|---|
| B/K10 | 46.01% | 1.74% | 12.33% |
| B/K20 | 34.03% | 1.74% | 24.31% |
| C/K10 | 44.44% | 1.39% | 11.63% |
| C/K20 | 39.24% | 2.43% | 15.80% |


These percentage-point deficits telescope to the actual uncovered fraction.
They are conditional on the frozen proof registry, not independently validated
causal shares. All active essential proofs are represented somewhere in each
full frozen chunk index (zero index-representation-missing rows); the observed
candidate gaps are not caused by absent registered text in the indexed corpus.
This does not validate every unregistered passage or visual component.

K20 increases candidate coverage by 11.98 points in B and 5.21 in C; candidate
complete counts rise 21→25 and 21→24. Oracle complete counts rise 20→24 and 21→23.
Actual minimum coverage and complete counts do not change. B/K20's only delivered
registered-support gain is P04-en's optional 12+ configuration branch; no current
requirement, condition or critical-support loss occurs in either arm.

| Configuration | Complete candidate questions | Distinct complete registered proof bundles (sum) | Rows gaining support at ranks 11–20 | New requirement supports at 11–20 |
|---|---|---|---|---|
| B/K10 | 21 | 87 | 0 | 0 |
| B/K20 | 25 | 91 | 13 | 23 |
| C/K10 | 21 | 87 | 0 | 0 |
| C/K20 | 24 | 90 | 9 | 17 |


Proof-bundle sums count coherent admitted source alternatives within questions,
including translated alternatives; they are not independent questions. The rank
gain ledger includes optional/conditional requirements and all 60 variants.

# Exact oracle and budget accounting

The oracle is **curator-only diagnostic code requiring frozen reference labels**.
It cannot serve as a deployable label-free selector. Candidate K, source/version,
scope, .3 threshold, whole bodies and original attribution remain fixed. No new
passage, synthetic proof, source substitution, metadata compaction or clipping
is permitted. Project scope is empty; global scope has 1,000 estimated tokens and
the unchanged outer allocator has 8,000.

Each source atom is partitioned at all candidate coverage boundaries. Only
non-whitespace proof cells count. Multiple chunks can jointly complete an atom;
all atoms of one proof are conjunctive, admitted proof alternatives disjunctive.
Frozen complete methods and their conditional assumptions remain separate.
Unresolved applicability cannot become a complete method.

Exact dynamic programming retains the cheapest subset for each union of proof
cells. This is sufficient: subsets with the same proof union have identical future
utility, and future whole-fragment costs are positive and additive. A single
fragment's cost comes from the real renderer. Add seven separator characters
per item, subtract seven for a nonempty final set; cost is feasible iff total
characters <=4,000. Round `ceil(chars/4)` only after joining. Original outer scope
wrappers are separately bounded by 8,000. No state cap, heuristic pruning or
approximate optimality claim is used; the largest table has 528 states.

The unbounded-cost DP also proves the minimum complete cost, even above 1,000.
Every optimum and minimum-complete witness is rerendered and rescored against
source ranges. Reported lower and upper bounds coincide under these constraints.
`complete_registered_proof_bundles` counts distinct coherent unions of registered
proof alternatives, not redundant supersets of carrier chunks; complete methods,
missing atoms, minimal costs and witness IDs are recorded for every row.

| Question | Configuration | Minimum complete tokens | Body chars | Attribution + separators chars |
|---|---|---|---|---|
| P03-en | B/K10 | 3699 | 5600 | 9195 |
| P03-en | B/K20 | 3699 | 5600 | 9195 |
| P03-en | C/K20 | 4768 | 7082 | 11989 |


P03-en B's cheapest complete set is seven chunks; C/K20 requires eight. Attribution
and separators consume 62.15% and 62.87% of these minimum-cost complete renderings.
Even their bodies alone exceed 4,000 characters (1,400 and 1,771 estimated tokens),
so deleting all attribution would still not make those whole-chunk witnesses fit.
This body-cost statement concerns the minimum-total-cost witness, not a separately
optimized minimum-body-cost set. No span-extraction result is claimed. P03-de has
both missing candidate proofs and demonstrated inability to fit all available
requirements; C/K10 P03-en is also mixed. Missing proofs alone are never labelled
mathematically budget-infeasible.

# Failure classifications and ambiguity

`selection_lost` requires an actual feasible complete witness; `budget_infeasible`
requires all minimum evidence among candidates and a proven complete cost above
1,000. `retrieval_missing` records a missing registered complete method. `mixed`
combines candidate, recoverable selection or proven partial-budget losses.
`complete` concerns the admitted minimum method, not all optional branches.

Missing registered proof does **not** establish that every other passage is
irrelevant. A missing active requirement with partially overlapping registered
proof is conservatively `unresolved`, while its reference-only bottleneck and
individual factors remain visible. This deliberately avoids turning incomplete
span matching into a conclusive semantic retrieval failure. All domain,
cross-language and unregistered-equivalence judgments remain provisional.

| Configuration | retrieval_missing | selection_lost | budget_infeasible | mixed | complete | unresolved |
|---|---|---|---|---|---|---|
| B/K10 | 10 | 7 | 1 | 3 | 13 | 14 |
| B/K20 | 5 | 11 | 1 | 7 | 13 | 11 |
| C/K10 | 11 | 3 | 0 | 2 | 18 | 14 |
| C/K20 | 8 | 5 | 1 | 4 | 18 | 12 |


The external 60-row wide classification matrix and 240-row CSV/JSON include every
question/configuration, including N/A cases. The 12 non-answerable variants are
separately marked `unresolved` with an explicit epistemic/N/A reason, not counted
as retrieval failures. P04 needs the actual server major version; S14 lacks an
admitted exact torque; S15 lacks user push context; S16's graphical facts remain
restricted. Contextual clarification requirements are not positive evidence
retrieval hits. K20 does not make any unavailable fact available.

# Detailed focus cases

Cells show **candidate / actual / oracle minimum coverage**, not answer quality.
The separate external focus ledger includes missing requirement IDs, all branch
conditions, proof gaps, witness IDs and exact costs.

| Question | B/K10 | B/K20 | C/K10 | C/K20 |
|---|---|---|---|---|
| P02-en | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 33.33% / 33.33% / 33.33% | 33.33% / 33.33% / 33.33% |
| P02-pl | 0.00% / 0.00% / 0.00% | 66.67% / 0.00% / 66.67% | 33.33% / 33.33% / 33.33% | 66.67% / 33.33% / 66.67% |
| P02-de | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 33.33% / 33.33% / 33.33% | 33.33% / 33.33% / 33.33% |
| P03-en | 100.00% / 33.33% / 33.33% | 100.00% / 33.33% / 33.33% | 83.33% / 16.67% / 16.67% | 100.00% / 16.67% / 16.67% |
| P03-pl | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| P03-de | 16.67% / 0.00% / 0.00% | 33.33% / 0.00% / 16.67% | 0.00% / 0.00% / 0.00% | 50.00% / 0.00% / 16.67% |
| S07-en | 50.00% / 0.00% / 50.00% | 50.00% / 0.00% / 50.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| S07-pl | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| S07-de | 50.00% / 0.00% / 50.00% | 50.00% / 0.00% / 50.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| S11-en | 25.00% / 25.00% / 25.00% | 50.00% / 25.00% / 50.00% | 50.00% / 0.00% / 50.00% | 50.00% / 0.00% / 50.00% |
| S11-pl | 25.00% / 25.00% / 25.00% | 50.00% / 25.00% / 50.00% | 50.00% / 0.00% / 50.00% | 50.00% / 0.00% / 50.00% |
| S11-de | 25.00% / 25.00% / 25.00% | 50.00% / 25.00% / 50.00% | 50.00% / 25.00% / 50.00% | 50.00% / 25.00% / 50.00% |
| S12-en | 100.00% / 33.33% / 100.00% | 100.00% / 33.33% / 100.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| S12-pl | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% | 0.00% / 0.00% / 0.00% |
| S12-de | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% | 33.33% / 0.00% / 33.33% | 33.33% / 0.00% / 33.33% |
| S13-en | 100.00% / 100.00% / 100.00% | 100.00% / 100.00% / 100.00% | 100.00% / 100.00% / 100.00% | 100.00% / 100.00% / 100.00% |
| S13-pl | 0.00% / 0.00% / 0.00% | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% |
| S13-de | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% | 100.00% / 0.00% / 100.00% |


**P02:** B/K10 has zero complete minimum requirements in all languages. K20 helps
only Polish: B gains first-layer and need-based cleaning support (0→2/3); C gains
first-layer support (1/3→2/3). No configuration supplies the registered complete
sheet/bed check. C's partial EN/DE first-layer passages retain entailment/scope
uncertainty. No cleaning advice is inferred from candidate presence; all IPA,
water-cleaning and cool-surface/burn branches remain separately audited. B/K20
does not deliver its new Polish evidence. No P02 context becomes complete.

**P03:** B/en contains all six minimum requirements, but only two fit together at
1,000 tokens, exactly matching actual 2/6. Selection cannot solve its full task at
this budget. C/en K10 has 5/6 (retention missing), yet only 1/6 fits; K20 retrieves
retention and timestamps but still only 1/6 fits. PL remains 0 minimum coverage.
DE gains configuration support in B and configuration/manifest/retention in C,
but still lacks summary-range, backup-chain and WAL-history evidence. The former
P03 answer-entailment/checksum disputes are not re-adjudicated or relabelled here.

**S07:** B/en and B/de have the complete sensor-off loading proof among candidates
but lose it during selection; oracle recovers 1/2. The tube-maintenance proof is
missing. B/pl and all C variants remain 0/2 even at K20. Heat-before-feed and the
complete loading sequence cannot be replaced by generic nearby XL text. This is
a mixed retrieval/selection example, not a pure budget failure.

**S11:** the MK4S media/selftest half is missing from all tested candidate pools.
B's K20 retrieves the MMU connection warning in all three languages (1/4→2/4),
but actual delivery stays 1/4. C already has 2/4 in candidates; actual EN/PL is
0/4 and DE 1/4, with feasible recovery to 2/4. No pool supports the complete
cross-product procedure, so extra MMU passages do not repair model applicability.

**S12:** B/en and B/de are genuine selection losses: full PostgreSQL 17
start/stop APIs, initiating-session lifetime and byte-exact returned metadata fit
in 889 tokens at K10 and 827 at K20. Actual coverage stays 1/3 and 0/3. Polish B
has no minimum proof; C has none in EN/PL and only metadata in DE. C/K20-en adds
the old API reference only, which does not establish the target-17 procedure.

**S13:** B/en is complete. B/de has a full feasible proof (724 tokens) at both K;
B/pl acquires it only at K20, but neither is actually delivered. C has complete
11/17-default and valid-descendant evidence in all languages at both K, fitting
in 818 tokens, yet only EN is delivered complete. These are strong whole-chunk
selection examples with explicit version defaults and the pre-base-backup branch
prohibition preserved in the oracle proof.

# Split, language, source and question-structure strata

Each cell is candidate→actual→oracle coverage; actual→oracle complete counts follow
in parentheses. These are dependent language variants, not independent samples.

| Stratum | n answerable | B/K10 | B/K20 | C/K10 | C/K20 |
|---|---|---|---|---|---|
| pilot | 9 | 46.30%→37.04%→37.04% (3→3) | 55.56%→37.04%→46.30% (3→3) | 53.70%→46.30%→46.30% (3→3) | 64.81%→46.30%→51.85% (3→3) |
| former sealed development | 39 | 55.77%→40.60%→55.77% (10→17) | 68.38%→40.60%→68.38% (10→21) | 55.98%→41.67%→55.98% (15→18) | 59.83%→41.67%→59.83% (15→20) |
| en | 16 | 67.19%→51.04%→63.02% (5→7) | 79.17%→51.04%→75.00% (5→9) | 66.67%→50.00%→62.50% (7→8) | 70.83%→50.00%→65.62% (7→9) |
| pl | 16 | 39.06%→34.38%→39.06% (4→6) | 57.29%→34.38%→57.29% (4→7) | 48.96%→39.58%→48.96% (6→7) | 51.04%→39.58%→51.04% (6→7) |
| de | 16 | 55.73%→34.38%→54.69% (4→7) | 61.46%→34.38%→60.42% (4→8) | 51.04%→38.02%→51.04% (5→6) | 60.42%→38.02%→58.33% (5→7) |
| prusa | 24 | 34.38%→22.92%→34.38% (0→4) | 51.39%→22.92%→51.39% (0→7) | 39.58%→30.21%→39.58% (5→6) | 47.22%→30.21%→47.22% (5→8) |
| progit | 12 | 79.17%→75.00%→79.17% (9→9) | 83.33%→75.00%→83.33% (9→9) | 83.33%→75.00%→83.33% (9→9) | 83.33%→75.00%→83.33% (9→9) |
| postgresql | 12 | 68.06%→38.89%→61.11% (4→7) | 77.78%→38.89%→70.83% (4→8) | 59.72%→34.72%→54.17% (4→6) | 65.28%→34.72%→55.56% (4→6) |
| single_document | 18 | 75.00%→72.22%→75.00% (12→12) | 80.56%→72.22%→80.56% (12→13) | 75.00%→72.22%→75.00% (13→13) | 80.56%→72.22%→80.56% (13→14) |
| multi_section | 18 | 36.11%→20.83%→36.11% (0→4) | 51.85%→20.83%→51.85% (0→6) | 41.67%→33.33%→41.67% (4→5) | 46.30%→33.33%→46.30% (4→6) |
| multi_document | 12 | 49.31%→20.14%→42.36% (1→4) | 65.28%→20.14%→58.33% (1→5) | 47.22%→11.81%→41.67% (1→3) | 52.78%→11.81%→43.06% (1→3) |


All 60 questions are development data. The pilot has 9 answerable variants and
the former sealed split 39; languages have 16 each; source groups 24 Prusa,
12 Pro Git and 12 PostgreSQL; structures 18 single-document, 18 multi-section,
12 multi-document. No new holdout or generalization claim is introduced.

# Conditions, warnings and evidence types

The fixed all-branch ledger has 132 critical and 147 condition/critical support
instances per configuration across all 60 variants. These are potential branches,
not generated advice, inferred applicability or safe-answer counts.

| Configuration | Critical candidate / actual / oracle witness | Condition candidate / actual / oracle witness |
|---|---|---|
| B/K10 | 69 / 45 / 53 of 132 | 74 / 46 / 53 of 147 |
| B/K20 | 82 / 46 / 65 of 132 | 89 / 47 / 66 of 147 |
| C/K10 | 65 / 43 / 52 of 132 | 71 / 46 / 55 of 147 |
| C/K20 | 74 / 43 / 56 of 132 | 82 / 46 / 58 of 147 |

| Evidence type | Instances/configuration | B/K10 | B/K20 | C/K10 | C/K20 |
|---|---|---|---|---|---|
| essential | 132 | 78 / 58 / 73 | 90 / 58 / 85 | 79 / 60 / 75 | 87 / 60 / 80 |
| conditional | 42 | 19 / 10 / 3 | 23 / 11 / 5 | 20 / 12 / 8 | 23 / 12 / 6 |
| optional | 30 | 19 / 9 / 8 | 23 / 9 / 8 | 16 / 11 / 9 | 22 / 11 / 9 |
| alternative | 15 | 0 / 0 / 0 | 3 / 0 / 3 | 0 / 0 / 0 | 0 / 0 / 0 |


Type cells again use candidate / actual / oracle-witness support. Proofs retain
prerequisites such as initial selftest, same-server manifest, session lifetime,
heat-before-feed and valid timeline ancestry. The JSON also supplies a clearly
labelled statement-keyword prerequisite tag; that convenience tag is not a new
semantic annotation or an applicability decision.

| K10→K20 arm | Stage | Critical gains | Critical losses | Condition gains | Condition losses |
|---|---|---|---|---|---|
| B | candidate | 13 | 0 | 15 | 0 |
| B | actual | 1 | 0 | 1 | 0 |
| C | candidate | 9 | 0 | 11 | 0 |
| C | actual | 0 | 0 | 0 | 0 |


Candidate gains include P02 first-layer/IPA qualifiers, P03 configuration and
retention, S05 power/environment, S08 tube triage, B/S11 connection warnings and
B/S13 version/descendant constraints. None except B/P04-en's optional branch is
newly delivered. No regression is hidden by aggregate coverage.

The minimum-coverage oracle does **not** maximize all-branch warning preservation:
its cheapest tied witnesses can omit baseline optional/conditional content. All
such losses are retained in `oracle-paired.json`, including P03-en/B chain/checksum
support, P04 optional procedural branches and S08 wrench branches. P03's tied
2/6 optimum changes which two essentials are present. This is why these witnesses
are upper-bound diagnostics, not safe replacement contexts or selectors.

| Configuration | Oracle vs actual critical gains / losses | Oracle vs actual condition gains / losses |
|---|---|---|
| B/K10 | 15 / 7 | 15 / 8 |
| B/K20 | 27 / 8 | 28 / 9 |
| C/K10 | 15 / 6 | 17 / 8 |
| C/K20 | 19 / 6 | 20 / 8 |


# Additional bottlenecks and exposure

The three requested categories do not explain all engineering or evaluation risk:

- **Representation pollution:** anchor-only HTML chunks have no technical body
  but can rank highly and consume attribution/budget. This also explains both
  observed tie effects. Their counts below are exact text-pattern diagnostics;
  no semantic filter is implemented.
- **Serialization overhead:** average attribution is about 1,000 characters per
  delivered context. P03's repeated navigation metadata dominates its minimum
  complete cost. This is renderer/representation cost, not solely a too-small
  model context window. No D1 metadata experiment is revived.
- **Scope/version ambiguity:** other-product/version documents occupy candidates.
  These flags compare source identities with the chosen registered method;
  a comparative old-version passage or generic other-product advice is not
  automatically false or irrelevant. No source substitution earns proof credit.
- **Evaluation uncertainty:** partial-span equivalence, agent-authored labels,
  cross-language entailment and outstanding domain review limit causal certainty.
  The repaired answer scorer's unresolved claim annotations are a separate
  measurement limitation; no answer score is used as a retrieval result here.
- **Generation behavior:** prior 3C.3 reports document added unsupported claims
  and omissions despite useful context. That is a downstream issue outside this
  no-inference study; context completeness cannot certify answer correctness.

| Configuration | Anchor candidates / questions | Anchor selected | Mean sources in pool | Mean repeated source chars in pool | Mean selected attribution chars |
|---|---|---|---|---|---|
| B/K10 | 8 / 2 | 8 | 3.17 | 366.0 | 1036.0 |
| B/K20 | 9 / 3 | 8 | 4.53 | 905.2 | 1062.4 |
| C/K10 | 4 / 2 | 3 | 2.90 | 918.9 | 1017.3 |
| C/K20 | 12 / 4 | 3 | 3.83 | 2123.9 | 1047.3 |

| Configuration | Other-product document instances | Other-version document instances | Restricted candidate / delivered questions |
|---|---|---|---|
| B/K10 | 124 | 35 | 2 / 1 |
| B/K20 | 282 | 75 | 3 / 1 |
| C/K10 | 102 | 42 | 4 / 3 |
| C/K20 | 247 | 92 | 7 / 3 |


These diversity, redundancy and exposure statistics use all 60 variants. Repeated
source characters measure exact same-source range overlap, not cross-language
semantic duplication. More source diversity does not imply sufficient evidence.
K20 increases restricted candidate exposure B 2→3 and C 4→7 questions, while
actual exposure stays B=1, C=3. B delivers S16-de's restricted XL component;
C retains P02-en and S16-en/de exposure. Nearby text does not establish terminal
position, symbol meaning or graphical polarity. No restriction is cleared.

# Next engineering direction: one separate future experiment

Primary: **evidence-aware ranking/selection for B at the current 1,000-token
budget**, initially retaining the K10 pool and immutable attribution/source
identities. This has a demonstrated feasible ceiling of 13→20 complete contexts
and 39.93%→52.26% minimum coverage (+12.33 points), without requiring more vectors
or a larger final context. K20 can later supply an additional four feasible
complete cases (ceiling 24/48, 64.24% coverage), but its standalone actual gain is
zero. A future mechanism must discover relevance without reference labels and
preserve applicable warnings, complete procedures and version boundaries; the
oracle is not that mechanism.

Complexity is medium: roughly 3–7 engineering days for a bounded prototype and
offline instrumentation, plus domain review/evaluation time (planning estimate,
not measured labor). No numeric expected real-world gain is justified; a result
from zero up to the +7 K10 oracle ceiling is possible, and regressions remain a
material risk given rejected V1/V2. Main risks are semantic ranking errors,
cross-language scope mistakes, losing safeguards, runtime cost and overfitting
these 20 exposed/dependent intent families.

| Direction | Complexity | Measured opportunity / reason for priority |
|---|---|---|
| Larger candidate pool only | Low | B +11.98 / C +5.21 candidate-coverage points; zero actual complete gain. Supporting factor. |
| Evidence-aware ranking/selection | Medium — primary | B/K10 +7 feasible complete contexts; +12.33 coverage points. |
| Multi-stage or section-aware retrieval | High | Candidate incompleteness remains 27/48 at K10; potential is large but delivered benefit unmeasured. |
| Source-faithful passage extraction | Medium–high | P03 whole-chunk minima far above budget; no span-extraction feasibility or general gain measured. |
| Improved budget allocation | Medium | Only one active scope; general scope redistribution has no demonstrated benefit; P03 is exceptional. |
| No change | None | Valid production decision pending validation, but leaves seven demonstrated feasible B/K10 completeness losses. |


# Artifacts, reproduction and validation

External versioned package (large/private outputs outside Git and Obsidian):

`C:\Users\korne\.codex\visualizations\2026\11\16\01a1e32c-6862-77e0-b517-a3b766a652aa\laew-retrieval-budget-v1`

- `retrieval/`: 240 candidate/actual traces, 120 ranking audits, cache/index-vector
  verification, native/exact membership audit, integrity manifest.
- `analysis-v3/`: authoritative 240-row diagnosis, 60-question CSV coverage,
  exact oracle witnesses/costs, all strata, paired K and oracle warning changes,
  tie review and historical integrity receipts. Earlier analysis versions retain
  identical aggregate quality results; v2 corrects mixed-loss classification and
  v3 adds witness cost decomposition and complete warning gain/loss ledgers.
- `report-v2/`: authoritative report, 60-row wide classification matrix and detailed focus ledger.
- `study-config.json`, initial/final preservation receipts, code snapshots,
  test logs and package manifest: provenance and reproduction.

The initial cross-session sandbox temp copy could not be recovered; collection
was repeated and copied before the same shell exited. Earlier attempt logs are
retained; only the verified authoritative output is interpreted. No embedding
work was repeated or introduced. Disposable index clones are not scientific
inputs and need not be copied into the final package.

Reproduce with the repository venv and **fresh** output paths:

```powershell
$pkg = '<external-package>'
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.retrieval_budget_diagnostics retrieve `
  --config "$pkg\study-config.json" --output fresh-retrieval
# In the SAME shell call, copy retained work/fresh-retrieval JSON files to a NEW external directory.
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.retrieval_budget_diagnostics analyze `
  --config "$pkg\study-config.json" --retrieval '<copied-fresh-retrieval>' --output fresh-analysis
# Copy retained work/fresh-analysis to a NEW external package directory.
.\.venv\Scripts\python.exe -B scripts/run_isolated.py --keep-diagnostics pytest `
  tests/evaluation/test_retrieval_budget_diagnostics.py -q
```

`LAEW_RETRIEVAL_BUDGET_ROOT` enables all frozen acceptance checks; its package
contains `retrieval/` and `analysis-v3/`. Socket connections are forbidden by the
study guard in both computational modes. Tests compare exact DP against exhaustive
enumeration, joined partial atoms, coherent methods, active/unresolved conditions,
restricted proof exclusion, token boundaries, cache-miss stopping, all 240 rows,
native ranking/score identity and oracle bounds/monotonicity. **80 tests passed,
zero skipped**, through `scripts/run_isolated.py`, including 19 new diagnostic
checks and existing scorer/applicability/dataset/renderer regressions. An initial
broader test command pointed an existing fixture's environment variable at
`run-v2` instead of its parent, causing one missing-file failure (79 passed).
Correcting that environment path produced the final 80/80 result without edits
to tests or frozen inputs. See `tests-final-v2.log` and `final-verification.json`
for the authoritative test and preservation receipts.

Repository additions: `laew/eval/retrieval_budget_diagnostics.py`,
`laew/eval/retrieval_budget_report.py`,
`tests/evaluation/test_retrieval_budget_diagnostics.py`, and this report.
Existing dirty files are preserved byte-for-byte; final Git status is saved
externally. No production file or existing selector was edited. No Git add,
commit, push, reset or clean ran. No new benchmark questions, holdout, model
answers, Luna requests, LLM judges, embeddings, model downloads, service changes
or deployment occurred. The diagnostic oracle is the only new optimization code.

| Integrity anchor | SHA-256 |
|---|---|
| Frozen retrieval package | `4bdbeed19cf75a4e435dc1d5ee1111cf26736c29f1ed3436acd6b99d52b5aad5` |
| v2.1 rubric manifest | `36f985c702203012166f99b5a53850acea6e77f5d80ef25c0514dcdec870cee3` |
| Saved vector cache | `ffb4fab8b37f5c8e8bb40c4238da5218cfb6215cabb53a310744fc9372615408` |
| This study's native retrieval manifest | `fd20e4b8569df5a1ddf00a46e7e70ec2c93545f92bcd3b42684b47255cd1a742` |
| Authoritative analysis-v3 manifest | `01f7dee6dc337a2be41f8f25a1a861f4d4e52974a70cc9dfd2610d79314bf113` |

**Hard stop:** diagnostic study complete. The recommendation authorizes no new
algorithm development or deployment. No future holdout is generated.
