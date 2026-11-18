---
title: Stage 2B.2 — Source-faithful evidence extraction feasibility
date: 2026-11-16
status: offline-reference-informed-feasibility-bound-not-a-runtime-extractor
scope: 60 exposed development questions; 48 answerable; extraction offline; 41 query embeddings separately authorized
---

# Decision and evidential limits

**Retain A/B/C; reject the tested query-focus decomposition and do not prioritize
their combination.** The separately authorized 41-query embedding job and full
retrieval comparison are complete in the companion decomposition report. No
equal-budget or increased-budget condition discovers an additional complete
candidate set; every extraction library has zero newly complete combined sets.
The primary next-step recommendation is no new architecture engineering until
source-boundary/domain judgments are resolved. Earlier pre-authorization
recommendations are preserved externally as history, not current advice.

Extraction saves tokens in proven source-bound examples, but the incremental
complete-case ceiling beyond whole chunks is only one P03-en case in B/K10,
B/K20 and C/K20, and zero in C/K10. P03-en requires at least 499 body tokens
before scope/citations; a complete conservative witness costs 1,335 minimal-span,
1,337 sentence or 1,411 paragraph tokens. The global coherent minimum is only
bounded at **499–1,335** under the most permissive admitted library. Fitting all
six requirements below 1,000 is unresolved, not proved feasible or impossible.
This diagnostic does not establish a label-free extractor or answer correctness.

# Verification and isolation

Read the requested retrieval/budget, evidence-aware ranking, complementary
selection, v2.1 calibration and scorer-repair/adjudication reports, plus CPU
reranking, FTS5/RRF and hierarchical dense studies. Verified the 777-file frozen
corpus, 201-member historical retrieval package, trace manifest, sanitized
questions, both datasets, rubric and calibration manifests, and the complete
parent budget-study package before source analysis. Reconstructed both chunkers
with `embed=False`; historical context replay matches all 180 contexts byte for
byte, and all 540 v2.1 stage scores reproduce. Source mapping includes visible
related context, normalized Unicode offsets, versions and full hashes.

All 112 registered atoms remain source-bound and exclude ten restricted source
components. The 329 uninspected High findings and inherited source risks stay
open. No original A/B/C, rejected selector, frozen question/source/rubric, index
or saved result changed. No model answer was read or generated. The question-only
decomposition was collected and hash-frozen in a separate `scoring=False`
process before this reference-informed analysis. Rubric labels are used only
in curator extraction/scoring processes, never as decomposition input.

# Three separate extraction libraries

1. **Sentence:** complete source sentences plus explicit local scope closures.
   Fenced listings and tables stay whole. Sentence-boundary detection is a
   conservative Markdown heuristic; semantic minimality remains unresolved.
2. **Paragraph/list unit:** blank-line paragraph/list-item units with the same
   mandatory closures; complete fenced listings and table runs stay whole.
3. **Minimal span:** complete registered spans with mandatory parameter,
   condition, warning, table-header/product-row and procedural-scope closures.
   No paraphrase, unit removal, negation removal or synthetic procedure.

Each result uses one library exclusively. They are not mixed into a best-of
upper bound. Dependencies and rationales are frozen in `scopes-v3/`; they are
agent-authored review assumptions, not a working label-free extraction policy.
Parameters retain definitions/defaults/units and applicable limitations. Restore
dependencies retain checksum cautions and WAL/history/dependency-tracking scope.
Firmware and loading packets retain their prerequisite/completion sequences.
S13 retains both complete version-specific paragraphs and ancestry prohibition.

Every substantive envelope character must be covered by the union of already
eligible, unrestricted candidate source ranges. Missing adjacent text is never
fetched or credited. An envelope touching a restricted component is rejected.
Source identity and full revision establish document scope; substantive parameter
definitions remain body evidence. Each source is cited with its full normalized
SHA-256 and revision; every fragment carries exact Unicode offsets. Source order
and explicit `[separate source passage]` separators prevent presenting disjoint
passages as consecutive steps. No spans from different versions are substituted.
The immutable source manifest resolves citations to original locations, URLs,
page/line maps and document applicability. This is a proposed diagnostic renderer,
not the original production renderer or a metadata-only selector revival.

A disclosed **strict-v1** sensitivity also required every section-heading body
inside candidate ranges, although ordinary source/section metadata already
supplies that scope. This overconstraint created artificial heading-availability
gaps. Its rules and all outputs are preserved. The main scope rule removes only
that requirement; substantive closures are unchanged. This revision occurred
after observing strict-v1 and is not blind validation.

A subsequent scope-retention acceptance test found an oracle bug: one packet
could incidentally cover another registered proof without that proof's declared
neighboring scope. The corrected v3 optimizer rejects every such union. Scope
rules and decomposition were not tuned. All pre-correction v1/v2 outputs remain
preserved and explicitly unvalidated as coherent witnesses; `analysis-v3/` is
authoritative. This mechanical correction leaves aggregate completeness/cost
findings unchanged but is necessary for the witness safety claim.

# Complete-context and coverage measurements

Counts use 48 answerable variants from 16 dependent families. The other 12
variants remain in exposure, cost and ambiguity ledgers with N/A positive recall.


| Configuration | Actual | Whole-chunk oracle | Sentence witness | Paragraph witness | Minimal-span witness | Proof-only complete upper bound |
|---|---|---|---|---|---|---|
| B/K10 | 13 | 20 | 18 | 18 | 18 | 21 |
| B/K20 | 13 | 24 | 22 | 22 | 22 | 25 |
| C/K10 | 18 | 21 | 19 | 19 | 19 | 21 |
| C/K20 | 18 | 23 | 22 | 22 | 22 | 24 |


| Configuration | Candidate coverage | Sentence coverage | Paragraph coverage | Minimal-span coverage |
|---|---|---|---|---|
| B/K10 | 53.99% | 43.40% | 43.40% | 45.49% |
| B/K20 | 65.97% | 57.29% | 57.29% | 60.42% |
| C/K10 | 55.56% | 49.31% | 49.31% | 50.35% |
| C/K20 | 60.76% | 56.25% | 56.25% | 57.29% |



These extraction counts are **constructive lower bounds within conservative
envelope libraries**, not replacement-selector results and not global optima.
They can be lower than the whole-chunk rubric oracle because the added source
coherence closures are stricter than the frozen registered minimum. This does
not overturn historical rubric completeness. It exposes a boundary judgment to
review. No fallback to another library or baseline witness inflates these counts.

The proof-only upper bound allows zero citation overhead and no neighboring
context. Every reference-complete extraction must contain one whole registered
proof for every active requirement; unioning those atoms gives a necessary body
cost. This is deliberately optimistic and never called safe evidence. Missing
registered proof does not prove that all unregistered equivalent text is absent.
All such equivalence and partial-span disputes remain open.

The optimizer exhausts all unions of admitted proof packets, keeping source
interval geometry rather than pruning by proof masks: grouped citations make
costs nonadditive. The finite-library optimum is exact, including above-budget
minimum-complete witnesses. This does **not** prove a global semantic optimum
over arbitrary excerpts. No heuristic state cap or statistical claim is used.

# Whole chunks, source attribution control and focus cases

The serialization control rerenders the **same original minimum-complete whole
chunk witness** using grouped source ranges/citations; it is not newly optimized.
It removes synthetic chunk context/navigation and same-source overlap. It is
not an attribution-only control. Therefore
token reductions must not all be attributed to finer evidence boundaries.


| Question | Pool | Original whole | Same witness grouped citation control | Necessary body floor | Sentence complete | Paragraph complete | Minimal-span complete |
|---|---|---|---|---|---|---|---|
| P03-en | B/K10 | 3699 | 1324 | 499 | 1337 | 1411 | 1335 |
| P03-en | C/K20 | 4768 | 1468 | 499 | 1337 | 1411 | 1335 |
| S06-en | B/K10 | 755 | 606 | 265 | 521 | 521 | 461 |
| S12-en | B/K10 | 889 | 456 | 137 | scope gap | scope gap | scope gap |
| S13-en | B/K10 | 724 | 445 | 244 | 346 | 346 | 345 |
| S13-en | C/K10 | 818 | 523 | 244 | 346 | 346 | 345 |



**P03-en:** B/K10 and K20 have all six requirements; C gets the missing retention
proof only at K20. All three complete pools have the same source-level extraction
costs. At 1,000 tokens the conservative libraries retain 4/6 requirements, versus
2/6 for B's whole-chunk oracle and 1/6 in C/K20. These are partial coverage gains,
not complete answers. P03-pl remains missing all registered minimum proof;
P03-de has mixed retrieval and budget/scope gaps. An exhaustive search within
this library cannot settle whether a less conservative, domain-approved boundary
could fit all six requirements.

**S12:** B/en and B/de already have whole-chunk rubric-complete witnesses at
889 tokens (827 at K20). The stricter migration packets also require source
prerequisite/start/stop invocation scope, including same-session and primary/
standby switch conditions. Those complete closures are absent from these pools,
so no extraction witness is claimed. The API/session/byte-exact metadata atoms
alone cost 137 tokens, but are not a complete operational migration procedure.
This is an unresolved scope-closure issue, not a newly absent registered fact or
proof that a safe compact explanation is impossible. C lacks the registered
target-17 procedure; compacting old-version text cannot repair it.

**S13:** both complete source paragraphs preserve 11/17 defaults, explicit
current/target timeline behavior and the pre-base-backup branch prohibition.
They fit in 345–346 tokens with full source hashes/revisions. Their whole-chunk
witnesses already fit at 724 B / 818 C tokens: this is a cost reduction, not an
additional feasible complete case. B/pl still needs K20 to obtain the proof.

**P02:** no pool supplies the complete sheet/bed proof. B/K20-pl and C/K20-pl
contain 2/3 minimum requirements; other variants have less. Need-based cleaning,
same-sheet first-layer scope, IPA qualifiers, water fallback and burn conditions
remain separate. Adjacent diagrams and unadjudicated semantic extensions earn
no credit. Compression never repairs an absent registered requirement.

**S06:** the B/en complete source packet fits in 461–521 tokens, preserving
model/selftest/media/rollback scope and complete selected update steps. This was
already a 755-token feasible whole-chunk case. All language/configuration
prerequisite losses/gains remain in the full ledger.

**S07/S11:** complete tube-maintenance or MK4S-side evidence remains missing.
Expanded XL loading retains heat-before-feed and purge-completion scope; MMU3
packets retain correct firmware identity, power, single-device USB and completion.
Some of those source closures are outside candidate ranges and are rejected.
No generic product neighbor or compressed MMU procedure fills the missing side.

# Safety, ambiguity and bounds audit

`complete-gains-regressions-ledger.json` includes every gain, loss and tie for
all 60 questions × four pools × three libraries, including optional/conditional
branches. Critical/condition denominators are fixed source requirements, not
observed advice or safe-answer counts. A minimum method can omit an unadvised
branch, but any supplied source packet retains its mandated local safeguards.
No semantic warning detector, independent bilingual adjudication or automated
answer correctness evaluation is claimed. Source identity validates which
snapshot supplied text; it does not certify every unrelated assertion in it.

Every admitted best-budget and minimum-complete witness is exact source text.
Restricted-region exposure is zero in extraction witnesses in all libraries.
Candidate restrictions remain unchanged and are recorded separately; rejected
packets never clear a restriction. S14 torque, S15 target context and S16 visual
facts remain unavailable; P04 still requires actual server major version.
All 12 N/A variants remain unresolved on positive technical retrieval metrics.


| Pool | Library | Critical /132 | Conditions /147 | Mean fragments /60 | Mean citation+gap chars /60 | Rows with rejected closure | Complete admitted set >1000 /48 |
|---|---|---|---|---|---|---|---|
| B/K10 | sentence | 45 | 46 | 1.23 | 118.5 | 33 | 1 |
| B/K10 | paragraph | 45 | 46 | 1.23 | 118.5 | 33 | 1 |
| B/K10 | minimal-span | 47 | 48 | 0.85 | 102.4 | 33 | 1 |
| B/K20 | sentence | 62 | 64 | 1.97 | 173.4 | 27 | 1 |
| B/K20 | paragraph | 62 | 64 | 1.97 | 173.4 | 27 | 1 |
| B/K20 | minimal-span | 65 | 67 | 1.27 | 143.1 | 27 | 1 |
| C/K10 | sentence | 47 | 48 | 1.67 | 145.8 | 35 | 0 |
| C/K10 | paragraph | 47 | 48 | 1.67 | 145.8 | 35 | 0 |
| C/K10 | minimal-span | 48 | 49 | 1.03 | 116.2 | 35 | 0 |
| C/K20 | sentence | 58 | 60 | 1.87 | 165.6 | 31 | 1 |
| C/K20 | paragraph | 58 | 60 | 1.87 | 165.6 | 31 | 1 |
| C/K20 | minimal-span | 59 | 61 | 1.27 | 137.6 | 31 | 1 |



Critical and condition omissions in an oracle-selected subset remain visible;
the aggregate objective maximizes minimum-method coverage and does not certify
every possible optional branch. A whole-chunk rubric-complete case rejected by
these closures needs domain review rather than relabeling the old result.

# Combined potential and architectural decision

The companion completed decomposition report provides the final equal-budget,
increased-budget, safety/version and combined tables. Missing candidate proof
accounts for 77.14% / 90% of incomplete B/C K10 contexts, but the tested syntactic
focus mechanism adds no complete pool and introduces regressions. No extraction
library gains a newly complete combined set; no proven case requires both tested
mechanisms. Bounds are not summed across overlapping cases or libraries.

Retain existing B/C and production A. The primary next step is no new architecture
engineering experiment before source-boundary/domain adjudication. The measured
token savings justify that review, not deployment. Previous CPU reranker latency/
regressions, rejected FTS5/RRF and lexical selectors, and hierarchical routing's
layout sensitivity remain reasons against automatic complexity. Larger context
can hold a 1,335-token P03 witness but cannot supply absent candidates. None of
these findings certifies answer correctness, significance or generalization.
The independent ~24-family holdout remains uncreated.

# Artifacts and reproduction


External package: `C:\Users\korne\.codex\visualizations\2026\11\16\01a1e47e-cedb-70e1-a4df-b6d1aa1ea057\laew-fine-evidence-v1`.




- `analysis-v3/per-question.json` and CSV: all 240 pool/question rows, whole
  costs, body-cost floors, three separate libraries, best-budget and unbounded
  complete witnesses, full attribution, offsets, supports and rejected closures.
- `analysis-v1/`, `analysis-v2/`, `scopes/`, `scopes-v2/`: preserved
  pre-correction runs; coherent-witness claims there are unvalidated.
- `reports-final/`: all-60 wide CSV, complete gains/regressions/ties, safety/condition
  and language ledgers, source-bound boundary review queue and combined limits.
- `decomposition/`: question-only freeze, all 60 plans and exact 41 pending inputs.
- `inspection/`, `scopes-v3/`, snapshots, logs and integrity manifests:
  source/proof provenance and validation. All semantic review origins are agent.

Use `.venv/Scripts/python.exe -B scripts/run_isolated.py --keep-diagnostics eval
laew.eval.fine_evidence_study` with modes `prepare`, `inspect`, `scopes`, `analyze`;
pass `--config <package>/study-config.json` and a fresh relative `--output`.
Analysis additionally takes `--scopes <package>/scopes-v3` and `--decomposition
<package>/decomposition`. Copy retained outputs from the runner's `work` directory
to a fresh external directory in the same shell call. The report module accepts
`--package` and a fresh relative `--output`. It never contacts an embedding service.
The pre-authorization extraction validation had **67 tests passed, zero skipped**, through `scripts/run_isolated.py`,
covering the new oracle/decomposition contracts, all frozen witness source ranges,
mandatory-scope retention, source/version/restriction behavior, exact prior budget
oracles and v2.1 calibration. Initial development failures and the transient
sandbox standard-library read failure are preserved in logs; the final complete
run passes. `git diff --check` passes. Final file inventory, checksums and Git
status are in the package's final validation receipt. Repository changes comprise
six evaluation-only modules, two test modules, these two reports and two additive
documentation-index entries. No production file changed; the initial working
tree was clean. No Git add, commit, push, reset or clean was executed.

The completed authorized comparison, final test count and full file inventory are recorded in the companion report and final validation receipt.
