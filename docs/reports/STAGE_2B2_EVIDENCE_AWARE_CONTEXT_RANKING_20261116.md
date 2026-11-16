---
title: Stage 2B.2 — Evidence-aware context ranking v1
date: 2026-11-16
status: rejected-development-experiment
scope: frozen native K10; 60 exposed questions; no model execution
---

# Decision

**Reject the experimental mechanism for further validation/deployment in its
current form.** Query-associated role signals recover a narrow partial-evidence
gain for B, but no additional complete context; the C comparison still loses
critical prerequisites and complete contexts. Do not promote the algorithm,
create a holdout or start another tuning round from this result.

Final B rises **39.93%→42.01%** minimum coverage, keeps **13/48 complete** and has
zero lost registered requirements across all 60 questions. Its only gains are
the same complete XL loading requirement in S07-en/de (one dependent intent
family). This recovers about **16.90% of B's macro coverage gap** to its 52.26%
K10 oracle, but **0 of the 7 additional complete contexts** in the 20/48 ceiling.
That ceiling is an optimistic label-informed upper bound, not an expected gain.

Final C falls **42.53%→39.41%** and **18→15 complete contexts**. Initial selftest
and media proofs disappear in S06-pl/de. A lower count of filename conflict flags
does not establish preservation of the actual model-specific technical evidence.
Production A is unchanged; B remains the development baseline and C the comparison.
The final selector also introduces a new restricted-region exposure in S16-de
for both B and C (page 83 is replaced by page 81), despite unchanged counts of
exposed questions. This is an additional acceptance failure for the primary B.

# Historical integrity and controlled sequence

Reviewed the retrieval/budget diagnosis, both rejected complementary experiments,
their root-cause report, rubric v2.1, source mapper, original renderer and frozen
native traces. Verified the 777-file restricted corpus, 201-member historical
retrieval package, question/dataset and calibration manifests, the full prior
budget-study manifest, and the four pinned V1/V2 full delivery/score manifests.
Reconstructed both frozen chunkers with `embed=False`, matched text/source/ranges,
replayed 180 historical contexts and reproduced all 540 calibrated stage scores.

All 60 variants are exposed development data from 20 dependent intent families.
48 are answerable (9 pilot + 39 former sealed); 12 have N/A positive technical
recall. They remain included in safety-branch, cost, exposure and paired ledgers;
missing unavailable facts never become retrieval failures. No question, label,
rubric, historical result or source restriction was changed.

The design/settings document preceded synthetic tests and implementation. The
initial selector passed 24 synthetic contracts, was hash-frozen, collected and
scored on the 12 pilot variants in separate processes, then on all 60 unchanged.
The pilot kept B's coverage, and C traded some P02 support without completeness
gain. Full initial B rose to 41.67% but lost S05-en power evidence; C fell to
35.42%, lost five complete contexts and increased restricted exposure 3→4.

Exactly **one refinement** was justified in writing before rerunning: replace
coarse role-signature protection with verbatim risk-clause protection. Objective,
weights, lexicon, threshold, K and budget did not change. The refined code passed
26 synthetic tests, was hash-frozen before its pilot, and then ran the same full
dataset. Its final implementation was frozen with a rejection decision. The
second permitted refinement was deliberately unused; there was no parameter
sweep, question-ID rule or attempt to force S12/S13 improvements.

# Algorithm and limitations

`query-role-cover-v1-r1` is evaluation-only code with no production caller. Its
only inputs are query text, the original cosine-scored authorized candidates and
ordinary source/section metadata. It has no file access, additional retrieval,
reference IDs, proof registry, saved answers, human annotations, API or model.
Collection invokes `load_inputs(scoring=False)`; evaluation reads v2.1 only in a
separate process after immutable selection outputs are sealed. The input-isolation
acceptance check succeeds with deliberately nonexistent rubric/dataset paths.

Unicode-normalized query terms use a six-character prefix for longer ordinary
words; technical identifiers remain intact. Pool-local IDF weights content-token
matches in body, section and filename. A small fixed EN/PL/DE alias lexicon
recognizes generic technical operations; it contains no API replacement facts,
correct procedures or expected answers. In overlapping 320-character windows,
query-token/operation association gates weak roles: configuration, procedure,
dependency, constraint, retention and maintenance. A warning keyword alone in an
unrelated passage earns no role reward. Neither roles nor their absence establish
semantic relevance, warning applicability or safe procedure completeness.

Explicit product/version cues from filenames are rewarded when named in the
query; apparent conflicts receive a .35 feature multiplier. This is incomplete
surface evidence: it can miss product names without digits, version aliases,
cross-version explanations and implicit prerequisites. No identity is rewritten,
no wrong-version passage is accepted as registered proof, and no source is
authorized by the heuristic. Candidates remain in the original single scope.

At K10 enumerate at most 1,023 nonempty whole-candidate subsets and maximize:

```text
.45 * weighted query-token coverage
.30 * query-associated role-feature coverage
.15 * explicit requested product/version-feature coverage
.10 * query-aligned cosine relevance, exact-body duplicates credited once
-.06 * high lexical overlap among same-source candidates
-.04 * fraction of the unchanged context budget used
```

Feature coverage credits the greatest original cosine among its carriers. Pool
normalizers are fixed before subset comparison. Role features combine a query
token/operation with a lexical role; the objective has no document-count or
section-diversity bonus. It can retain one sufficient section. Whole original
bodies and **all original attribution, tags/backlinks included**, are preserved.
Character costs come from the real renderer; include all seven-character
separators and round `ceil(chars/4)` after joining. Eligibility stays >=.3,
global budget 1,000 and overall allocation 8,000, with empty project scope.

The final guard protects baseline-covered requested identity features and exact
same-source surface clauses containing dependency/constraint cues, technical
identifiers/options or numerical units, when the baseline candidate has query
association and no explicit filename conflict. Another whole chunk can cover
the same clause; every baseline body is **not** unconditionally retained. The
initial duplicate-replacement contract and 48 changed final contexts demonstrate
that this is not the former all-baseline-body constraint under a new name.

Fallback uses runtime evidence only: insufficient query alignment, an already
clipped baseline, no feasible protected subset, or predicted utility improvement
below .025. No new clipped procedure is produced. Ties prefer fewer rendered
characters then the lower native subset mask; output stays in native order.
The finite search is bounded by K10 and existing character/query limits, with
no state cap, learned model or hidden tuning. Pairwise overlap is a weak lexical
redundancy proxy, not semantic equivalence across languages.

The new mechanism differs from rejected lexical-diversity V1/V2: its reward is
query-token/operation/role coverage, its guard is selective exact text coverage,
and it retains full metadata. It neither rewards generic source/section diversity
nor requires all baseline bodies. Its failure still demonstrates the limits of
light lexical role inference in technical, multilingual and versioned material.

# Full 60-question results

Minimum coverage and complete counts use the same 48 answerable variants. Critical
and condition support are fixed all-branch ledgers over all 60: 132 and 147
potential supports. They do not infer advice, actual answer applicability or safe
answer counts. Every admitted minimum method retains its own v2.1 conditions.

| Arm/mechanism | Minimum coverage | Complete /48 | Critical /132 | Condition /147 | Candidate supports lost |
|---|---|---|---|---|---|
| B | 39.93% | 13 | 45 | 46 | 39 |
| B-query-role-cover-v1 | 41.67% | 13 | 46 | 47 | 36 |
| B-query-role-cover-v1-r1 | 42.01% | 13 | 47 | 48 | 37 |
| C | 42.53% | 18 | 43 | 46 | 32 |
| C-query-role-cover-v1 | 35.42% | 13 | 38 | 40 | 42 |
| C-query-role-cover-v1-r1 | 39.41% | 15 | 40 | 42 | 36 |

Chosen-method active supports below use only the 48 answerable variants. Conditional/critical denominators can change with the coherent method selected by v2.1; the fixed all-branch table above remains the primary preservation ledger. These are method-scenario conditions, not observed advice.

| Arm/mechanism | Essential hit / active | Conditional hit / active | Critical hit / active |
|---|---|---|---|
| B | 46 / 120 | 3 / 3 | 39 / 105 |
| B-query-role-cover-v1 | 48 / 120 | 3 / 3 | 40 / 105 |
| B-query-role-cover-v1-r1 | 48 / 120 | 3 / 3 | 41 / 105 |
| C | 48 / 120 | 3 / 3 | 37 / 105 |
| C-query-role-cover-v1 | 38 / 120 | 4 / 6 | 32 / 107 |
| C-query-role-cover-v1-r1 | 43 / 120 | 4 / 6 | 34 / 107 |


The final B gain is two instances of one registered essential/critical loading
requirement; all other B registered supports tie. Final C gains three support
instances and loses seven (four critical, six conditional-ledger losses). Its
net critical count conceals four lost requirements, so rejection is not based
on net aggregates alone. Minimum-method completeness is separate from optional
branches: losing S08 wrench advice support does not reduce its no-disassembly
minimum denominator, but remains a recorded conditional loss.

# Every final registered gain and regression

| Question | Arm | Gains | Losses | Critical losses |
|---|---|---|---|---|
| P02-pl | C | P02.ipa_qualifiers, P02.water_fallback | — | — |
| S01-en | C | — | S01.purging | — |
| S06-pl | C | — | S06.initial_selftest, S06.media | S06.initial_selftest, S06.media |
| S06-de | C | — | S06.initial_selftest, S06.media | S06.initial_selftest, S06.media |
| S07-en | B | S07.loading | — | — |
| S07-de | B | S07.loading | — | — |
| S08-pl | C | S08.tube_count | S08.wrench | — |
| S08-de | C | — | S08.wrench | — |


These eight rows are the entire final support-change ledger. All other 112
question/arm comparisons tie on every registered requirement, including the
12 unsupported variants in each arm. Initial-version changes, critical losses,
all cost/exposure deltas and unchanged rows remain in the external paired files.

**S07:** B/en and B/de recover the complete sensor-off loading proof, including
its heat-before-feed prerequisite. Tube maintenance is still missing from K10,
so coverage rises 0→1/2 but completeness remains false. PL and C do not gain.

**S12:** no final gain. B/en and B/de have candidate-complete feasible evidence
(prior oracle: 889 tokens) but remain 1/3 and 0/3 delivered. Their original
11/17 passages carry protected surface content and explicit query-mentioned
versions; conservative clause/identity protection plus the same full attribution
leaves no sufficiently higher-utility admissible change. The mechanism cannot
infer which API/session/returned-metadata propositions form the right procedure.
Initial B/de's partial session gain did not survive the protection refinement.

**S13:** no final gain. Feasible 11/17 evidence fits in 724 B / 818 C tokens, but
only EN remains complete. Protecting generic baseline history/version clauses
does not discover the distinct default/valid-descendant proof bundle. Fallback
and guard constraints leave the baseline choices, rather than consulting the
available reference-informed witnesses.

**S11:** no final support change. Missing MK4S media/selftest candidate evidence
remains absent; extra MMU material cannot establish the cross-product procedure.
The initial C/de loss of its MMU firmware-path proof is prevented in the final
version. Filename relevance still does not validate device applicability.

**P02:** B remains 0 minimum coverage; C retains 1/3 in every language. C/pl adds
IPA qualifiers and the water-cleaning branch without losing registered support,
but no complete sheet/bed/first-layer minimum emerges. This conditional support
does not mean that an answer advised cleaning or that unavailable graphics
became valid evidence. Existing unregistered entailment disputes stay open.

**P03:** no final registered support change and no complete context. The previous
exact whole-chunk budget result remains: B/en needs 3,699 tokens for all six
requirements. Query-aware ranking cannot solve it at 1,000; C/en K10 also lacks
the full candidate proof. No extraction, larger K or larger budget is tried.

**Critical failure S06:** the refined guard retains its detected surface clauses,
but replaces the complete firmware chunk with another overlapping chunk that
does not cover the full registered initial-selftest/media bundle. Exact preservation
of a few risk-looking sentences is not preservation of every technical condition
or required local scope. Source/model filename matches and role similarity are
therefore insufficient safeguards. S01/en similarly loses purging explanation
despite retaining other matching operation vocabulary.

# Language, source and question-structure strata

Cells are minimum coverage / complete count. The former sealed split is exposed
development data. Languages and connected families are dependent observations;
no population superiority, confidence interval or independent validation is claimed.

| Stratum | n answerable | B | B final | C | C final |
|---|---|---|---|---|---|
| pilot | 9 | 37.04% / 3 | 37.04% / 3 | 46.30% / 3 | 46.30% / 3 |
| former sealed | 39 | 40.60% / 10 | 43.16% / 10 | 41.67% / 15 | 37.82% / 12 |
| en | 16 | 51.04% / 5 | 54.17% / 5 | 50.00% / 7 | 46.88% / 6 |
| pl | 16 | 34.38% / 4 | 34.38% / 4 | 39.58% / 6 | 36.46% / 5 |
| de | 16 | 34.38% / 4 | 37.50% / 4 | 38.02% / 5 | 34.90% / 4 |
| prusa | 24 | 22.92% / 0 | 27.08% / 0 | 30.21% / 5 | 23.96% / 2 |
| progit | 12 | 75.00% / 9 | 75.00% / 9 | 75.00% / 9 | 75.00% / 9 |
| postgresql | 12 | 38.89% / 4 | 38.89% / 4 | 34.72% / 4 | 34.72% / 4 |
| single_document | 18 | 72.22% / 12 | 72.22% / 12 | 72.22% / 13 | 69.44% / 12 |
| multi_section | 18 | 20.83% / 0 | 26.39% / 0 | 33.33% / 4 | 27.78% / 2 |
| multi_document | 12 | 20.14% / 1 | 20.14% / 1 | 11.81% / 1 | 11.81% / 1 |


# Version/product, restrictions and fallback audit

Two applicability diagnostics are deliberately separate. Filename-conflict flags
use only the declared runtime heuristic. Other-product/version document counts
compare selected source identities with the complete frozen family proof registry;
they are source-neighbor diagnostics, not automatic factual-error counts. Some
other-version documents are legitimate comparative context. Neither method can
certify every assertion inside a passage. Exact v2.1 proof scoring never credits
the wrong source/version for a required proposition.

| Arm | Changed /60 | Fallback /60 | Filename conflicts before→after | Other-product docs before→after | Other-version docs before→after | Restricted questions before→after |
|---|---|---|---|---|---|---|
| B | 20 | 40 | 26→17 | 47→36 | 5→4 | 1→1 |
| C | 28 | 32 | 20→10 | 28→24 | 5→1 | 3→2 |


All final fallbacks are the fixed insufficient-predicted-gain criterion, not label
feedback. B has zero final registered losses, including version requirements;
C loses the S06 prerequisites despite improved filename flags. Counts of exposed
questions hide a **new page-81 XL restricted region in S16-de/B and C**, replacing
page 83. C also removes the historical MINI+ page-45 exposure in P02-en. Thus
fewer exposed C questions do not demonstrate region-level nonregression. This
new region is an acceptance failure even though S16 has N/A positive recall.
Existing B/C restrictions remain unavailable as
positive evidence. All ten corpus restrictions, 329 uninspected High findings
and other source risks stay open. Initial C's increased exposure remains an
explicit failure of the initial mechanism, not retrospectively relabelled away.

# Tokens, overhead, redundancy and latency

All measurements below use all 60 variants. Latency is selection+render only:
ten warm alternating baseline/experimental repetitions per question/arm, 600
samples per arm. Feature computations are repeated, not cached across calls.
There is no retrieval, embedding, tokenizer, provider or end-to-end timing claim.

| Arm/mechanism | Mean estimated tokens | p95 / max tokens | Mean attribution chars | Repeated source chars | Repeated shingles | p50 / p95 ms |
|---|---|---|---|---|---|---|
| B | 922.2 | 996.0 / 1000 | 1036.0 | 59.4 | 9.05% | 0.095 / 0.156 |
| B-query-role-cover-v1 | 883.8 | 996.0 / 1000 | 971.7 | 36.3 | 6.56% | 14.141 / 17.407 |
| B-query-role-cover-v1-r1 | 904.1 | 996.0 / 1000 | 999.0 | 62.7 | 7.86% | 13.999 / 18.044 |
| C | 907.9 | 995.0 / 999 | 1017.3 | 200.3 | 13.19% | 0.131 / 0.196 |
| C-query-role-cover-v1 | 867.8 | 995.1 / 998 | 971.1 | 134.3 | 8.61% | 14.796 / 18.953 |
| C-query-role-cover-v1-r1 | 882.0 | 995.0 / 997 | 993.7 | 154.2 | 9.46% | 14.983 / 18.062 |


The final absolute overhead is roughly 14–15 ms at median versus 0.10–0.13 ms
for ranked_fill in this environment. Complexity/latency is bounded and modest
relative to generation, but it buys no complete-context gain and does not justify
promotion. Redundancy reduction cannot substitute for technical sufficiency.

# Separate anchor-only diagnostic

The diagnostic removes only exact anchor-only HTML bodies from the already frozen
K10 pool and replays **unchanged ranked_fill**; it changes no corpus, index, score,
attribution or threshold. The detector is a syntax pattern, not a semantic HTML
classifier. It is separate from the query-role objective and is not promoted.

| Arm | Minimum coverage | Complete /48 | Critical /132 | Condition /147 | Mean tokens | Restricted questions |
|---|---|---|---|---|---|---|
| B | 39.93% | 13 | 45 | 46 | 920.2 | 1 |
| C | 42.53% | 18 | 43 | 46 | 909.2 | 3 |


Anchor filtering has zero registered evidence, completeness or warning effect
in either arm on this dataset. Anchor pollution is real, but removing it alone
does not recover the demonstrated complete-context gap.

# Interpretation and stop

A label-free selector can recover **some partial B evidence without registered
warning/version losses** here, but this experiment does not recover any of the
seven feasible additional complete B contexts. Its narrow S07 gain is not a
general-purpose improvement, and the same algorithm remains unacceptable on C.
Weak lexical roles cannot establish technical dependencies or source/version
entailment. Strengthening conservative guards prevents some losses and also
blocks useful rearrangements. Neither an unprotected span nor a filename conflict
proves that the text can safely be discarded.

Reject both the initial and refined mechanism. Do not tune more weights, add
question-specific exceptions or consume an independent holdout now. The proposed
future ~24 genuinely new intent families remain uncreated; they belong only
after a different experimental mechanism is stable and separately frozen.
No architectural implementation, extraction experiment or new inference follows
from this report. Keep A/B/C and all historical artifacts unchanged.

# Artifacts, reproduction and validation


External package: `C:\Users\korne\.codex\visualizations\2026\11\16\01a1e32c-6862-77e0-b517-a3b766a652aa\laew-evidence-aware-context-v1`.

- `DESIGN_V1_BEFORE_EVALUATION.md`, `initial-freeze.json`, `versions/initial/`:
  initial rationale, settings, source and synthetic tests before pilot scoring.
- `REFINEMENT_1_BEFORE_RERUN.md`, `refinement-1-freeze.json`,
  `versions/refinement-1/`, `final-freeze.json`: the only refinement and final stop.
- `initial-pilot-*`, `initial-all-*`, `r1-pilot-*`, `r1-all-*`: sealed selection
  inputs/outputs, query-only feature profiles, latency samples, separate scoring,
  all requirement and restriction changes. The pilot summary's `/all` historical
  baseline includes all 60 originals; compare its `/split/pilot` cells to the
  pilot experiment. Full-study `/all` cells share identical 60-question coverage.
- `comparison-v3/`: authoritative all 540 combined rows, a 60-question wide CSV, every initial
  and final gain/loss/tie, applicability/exposure audit, and this report. The
  earlier report drafts are retained: v2 corrects region-level exposure and v3
  adds chosen-method active support. No selection or evidence score is changed.
- `analyze_results.py`, `reproduce.ps1`, code snapshots, preservation receipts,
  test logs and package integrity manifest: reproducibility.

Reproduce in a **fresh** external directory using `reproduce.ps1`. Its offline
launcher loads a hash-pinned selector snapshot without editing the checkout;
scoring and tests use the isolated runner, copying retained score outputs within
the same shell session. The authoritative collection and scoring runs both used
the isolated runner. Collection requires a hash-matching freeze. The initial code
is retained byte-for-byte; final collection uses `query-role-cover-v1-r1`. The
selector never opens the rubric; scoring is another process. Network connections
are blocked throughout collection/scoring. No saved Luna answer is read.

**92 tests passed, zero skipped**, through `scripts/run_isolated.py`: 26 synthetic
selector contracts, five immutable study acceptance checks and 61 existing
scorer/applicability/dataset/renderer checks. Acceptance replays all 240 initial
and final query-role selections, checks pilot/full equality, exact original
bodies/source attribution/scores, budgets, protected clauses, all loss ledgers
and label-free loading with missing reference paths. No failing test was waived.

Repository additions: `laew/eval/evidence_aware_selection.py`,
`laew/eval/evidence_aware_study.py`, `tests/evaluation/test_evidence_aware_selection.py`,
`tests/evaluation/test_evidence_aware_study.py`, and this report. Existing 15 dirty
files are preserved byte-for-byte. Final hashes and Git status are in
`final-verification.json` and `git-status-final.txt`. No Git add, commit, push,
reset or clean ran. No production code, provider, selector setting or service
was edited. No embedding, retrieval rerun, model download, LLM reranker, API use,
answer generation, judge, holdout or deployment occurred.

| Integrity anchor | SHA-256 |
|---|---|
| Prior bottleneck-study manifest | `c5a96d10822d5d6f7559b8e0985d7758eb9864d0038c734dca8dcb73d76c1917` |
| Effective rubric manifest | `36f985c702203012166f99b5a53850acea6e77f5d80ef25c0514dcdec870cee3` |
| Initial selector source | `68a966d3e0f653a283b8afce84eccdcc4648c606e9a4da3f0da4082193df7951` |
| Final selector source | `431145d42aad8ac76dbc64142a9bf00f34b5f14f83233174aea7f74e907764c7` |
| Initial all-question delivery | `fad91fd471528f863856ff2a4326d2fdd9ea515dbd3a6be988aee24b4e4157b9` |
| Final all-question delivery | `e11c63308ea93a0616a21f232843ae803f3c7273bb64f4fc9231233d2304c1f2` |
| Final all-question scores | `2ec1b2e2a0199e06dd8db7ed75f343106c3a0df8e4c6982f6a2ea6f9c8c3c3f0` |

**Hard stop respected:** frozen diagnostic implementation, rejection recommendation,
no deployment, no new benchmark question, no generated model answer.
