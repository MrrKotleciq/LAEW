---
title: Stage 2B.2 — Query decomposition and combined feasibility results
date: 2026-11-16
status: completed-authorized-development-study-reject-current-decomposition
scope: all 60 exposed questions; 41 authorized new query embeddings; production unchanged
---

# Decision

**No change to A/B/C. Reject this conservative question-focus decomposition.**
It discovers zero new candidate-complete cases at equal total raw budgets, loses
complete cases and technical prerequisites, and yields zero newly complete
coherent extracted sets. A larger 20-per-query pool has small partial coverage
gains but no additional complete case, plus one new restricted B region.
These results do not reject query decomposition in principle. They reject the
tested frozen syntax/focus mechanism, merge and raw-budget allocation on these
exposed development questions. No post-result rule tuning was performed.

Source-faithful extraction has measurable cost potential but no demonstrated
complete-case gain beyond existing whole-chunk feasibility. Its incremental
reference ceiling is at most one P03-en case per B/K10, B/K20 and C/K20 pool;
that case has no demonstrated coherent 1,000-token witness. A combination has
**zero measured new complete contexts** in every separately evaluated extraction
library. No numerical gains are added across overlapping cases or libraries.

The one primary next-step recommendation is **no new architecture engineering
experiment yet**. Resolve the source-boundary/domain judgments first, especially
P03/S12/S04. This is the permitted no-change outcome. Repeated lexical selectors,
this decomposer, FTS5/RRF or a costly CPU reranker do not have supporting evidence
for another implementation/tuning round. If research continues, narrower evidence
boundaries need independent domain agreement before a label-free extractor is
engineered; the current oracle is not one.

# Authorization, embedding identity and measured cost

The initial cache inspection found exactly 41 missing unique focused inputs.
Offline source extraction, workload counts and the question-only freeze were
finished first. The user then explicitly authorized generation and continuation.
All 41 texts were submitted exactly once in six requests, without probes, corpus
re-embedding, model answers or an LLM judge. The job used the user-prepared local
service; no service was started, restarted, downloaded or reconfigured.


| Measurement | Value |
|---|---|
| Model | laew-qwen3-embedding; Qwen3-Embedding-0.6B Q8_0; 1,024 dimensions |
| Verified exact GGUF SHA-256 | 06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439 |
| New inputs / requests | 41 / 6 |
| Estimated chars/4 / actual server prompt tokens | 3189 / 3419 |
| Measured warm job time | 0.956 seconds |
| Observed server settings | pooling last; 2 slots; ctx 16384; batch 1024; ubatch 1024 |
| Original native control rows | 240/240 exactly equal |
| Logical searches / physical calls including repeat audits | 846 / 1132 |
| Distinct first-search time sum | 18.149 seconds; excludes model/loading/source checks/repeats |



The current model catalog differs only in its server-supplied `created` timestamp.
Exact weight SHA, alias, Q8_0 metadata, last-token pooling and 1,024 dimensions
were separately verified. This drift is explicit in `embeddings-authorized/`;
the historical SQLite was not rekeyed or modified. New vectors use a separate
catalog-bound cache. This is not a model substitution. The user-prepared settings
differ from the earlier suggested slot/context values; inference semantics and
model identity were preserved. Local sandbox loopback access required tool-level
escalation; the user's authorization covered this job. No rejected approval or
pending computation remains. No further embedding computation is required.

# Frozen deterministic design and fair comparisons

`explicit-question-focus-v1` consumes only the original question string and
imports only `re`. It has no reference, source, answer or failure inputs. It splits
explicit interrogative clauses at question/semicolon/newline boundaries and
conjunctions/commas before interrogatives, groups contiguous excess clauses to
at most four foci, and retains the original search. Each focused embedding is
the full original question plus `Requested part: <request clause>`. This retains
products, versions, conditions and negations, but is a syntactic emphasis
mechanism rather than verified atomic semantic decomposition. No LLM service,
question-specific runtime rule or hidden dependency knowledge was introduced.

Twenty variants split: EN six, PL eight, DE six. Forty use exactly the original
query. Enumeration/auxiliary-interrogative and implicit-dependency omissions
remain: S06/en model/media/entry, S10/en populate/publish, P02/en implicit checks,
and some `does/should/can` multi-part requests remain bundled. P03's configuration,
retained files and retention can share a focus; no four-part factual reference
decomposition was hardcoded. Full scope can dilute focus and does not prove
correct attachment of conditions to focused operations. All 60 plans and the
post-freeze limitation audit remain available, including cross-language asymmetry.

The equal10/equal20 conditions allocate exactly 10/20 **total raw result slots**
across all searches, original first. Merge round robin, retain native order,
apply cosine >=0.3 per search and deduplicate exact chunk IDs only. There is no
backfill, RRF, source/text/language dedup or reference-aware merging. Duplication
therefore reduces unique pools; this is part of the tested mechanism's cost.
Chunking, embedding model, cosine/index, scope and restrictions remain unchanged.
The optional expanded condition requests 20 per query, explicitly spending
68.33% more raw slots than single K20. Its gains are not pure decomposition gains.
Query vectors are shared across chunkers/budgets. A byte-verified disposable copy
of the original Chroma index was used; original indexes were never opened mutable.
Every distinct native search was repeated once and stable; all 240 original
K10/K20 control rankings, scores, source identities and ranges reproduce exactly.

# Candidate results

Positive coverage and completeness use 48 answerable variants. All 60 are retained
in costs, paired safety/restriction ledgers and diagnostics. Languages/families
are dependent; there is no significance or generalization claim.


| Arm | Condition | Candidate complete before→after /48 | After coverage | Complete gains | Complete losses | Duplicate / raw slots (60) | Unique eligible (60) |
|---|---|---|---|---|---|---|---|
| B | equal10 | 21→18 | 48.78% | 0 | 3 | 113/600 | 487 |
| B | equal20 | 25→24 | 59.90% | 0 | 1 | 237/1200 | 963 |
| B | expanded20perquery | 25→25 | 66.32% | 0 | 0 | 753/2020 | 1267 |
| C | equal10 | 21→21 | 51.91% | 0 | 0 | 114/600 | 486 |
| C | equal20 | 24→23 | 58.33% | 0 | 1 | 231/1200 | 969 |
| C | expanded20perquery | 24→24 | 61.81% | 0 | 0 | 751/2020 | 1269 |



Single-query coverage is B/K10 53.99%, B/K20 65.97%, C/K10 55.56%, C/K20 60.76%.
The increased-budget condition raises B/K20 by only 0.35 points and C/K20 by
1.04 points, with complete counts unchanged at 25 and 24. No new complete set
is attributable to this decomposer, including with the larger budget.

Equal-budget complete losses are B/K10 P03-en and S12-en/de; B/K20 S13-pl;
C/K20 P03-en. C/K10 keeps its complete count but loses partial configuration,
WAL and MMU connection/path evidence. B's only new requirement family is partial
P03-pl summarizer configuration. Expanded C additionally gains P03-pl summarizer/
minimal-level support and S12-en metadata, still without a complete method.
P02 and S07/S11 remain incomplete. The full ledger includes all gains/losses/ties,
not just complete-case deltas or net warning totals.


| Arm/condition | Requirements gained/lost | Critical gained/lost | Condition gained/lost | Restricted questions /60 | New restricted rows |
|---|---|---|---|---|---|
| B/equal10 | 2/18 | 1/12 | 1/13 | 2 | 0 |
| B/equal20 | 2/12 | 1/9 | 1/9 | 3 | 0 |
| B/expanded20perquery | 2/0 | 1/0 | 1/0 | 4 | 1 |
| C/equal10 | 0/12 | 0/10 | 0/10 | 4 | 0 |
| C/equal20 | 0/15 | 0/7 | 0/9 | 7 | 0 |
| C/expanded20perquery | 4/0 | 3/0 | 3/0 | 7 | 0 |



Expanded B adds the restricted MK4S PDF-page-19 component to **S07-en** candidates.
No extraction witness credits it. This is candidate exposure, not a new production
or answer exposure; it remains an acceptance concern. All ten restrictions and
unresolved visual facts stay open. Product/version proof credit always requires
the exact frozen source identity; old APIs or another printer cannot substitute.
`unregistered_scope_neighbors` records every off-registry candidate/source for
all 360 comparisons. Such neighbors can be comparative context and do not
automatically establish factual product/version errors. Domain/bilingual
equivalence and partial registered proofs remain unresolved agent judgments.

# Extraction interaction: separate coherent libraries


| Arm/condition | Candidate availability upper /48 | Whole-chunk oracle /48 | Sentence feasible /48 | Paragraph feasible /48 | Minimal-span feasible /48 | New complete extracted sets vs same-budget single |
|---|---|---|---|---|---|---|
| B/equal10 | 18 | 18 | 18 | 18 | 18 | 0/0/0 |
| B/equal20 | 24 | 23 | 21 | 21 | 21 | 0/0/0 |
| B/expanded20perquery | 25 | not computed >20 | 22 | 22 | 22 | 0/0/0 |
| C/equal10 | 21 | 21 | 19 | 19 | 19 | 0/0/0 |
| C/equal20 | 23 | 23 | 21 | 21 | 21 | 0/0/0 |
| C/expanded20perquery | 24 | not computed >20 | 22 | 22 | 22 | 0/0/0 |



Availability upper counts ignore source coherence/citation cost. The extracted
counts are constructive, source-exact lower bounds under the three separate
agent-reviewed envelope libraries; they are not label-free runtime gains.
Reference-informed library rules, citation model, missing closure ambiguity,
scope corrections and prior failed runs are documented in the extraction report.
No library is mixed with another or with a baseline fallback to inflate a bound.
The increased-budget whole-chunk oracle is deliberately uncomputed when pools
exceed its 20-candidate diagnostic bound; this does not affect candidate/extraction
results. No exact minimum is claimed for that missing cell.

No condition yields a newly available complete coherent extraction compared with
its corresponding original K10/K20 library, and **zero demonstrated cases require
both mechanisms**. Equal20 loses one extraction-complete case per arm (B S13-pl,
C S04-pl); the latter is a source-closure loss despite candidate-count accounting.
There is no new complete-proof availability to add to extraction's old ceiling.

The original incomplete-context partition remains: missing candidate proof affects
27/35 (77.14%) of incomplete B/K10 contexts and 27/30 (90%) of C/K10; at K20 it
affects 23/35 (65.71%) and 24/30 (80%). These are reference-relative bottlenecks,
not independent causal shares. This mechanism fails to repair them. Forty unsplit
variants are unchanged; split variants can lose prerequisites because duplicate
focused searches consume slots while the original query's depth is reduced.

P03-en is still the only extra candidate-complete case beyond the whole-chunk
budget ceiling. Necessary body text costs 499 tokens; coherent complete witnesses
cost 1,335–1,411, including exact versions, warnings and citation separators.
Feasibility below 1,000 remains unresolved; it is neither established nor proved
impossible. S13 fits 345–346 and S06 461–521 tokens, but both already had feasible
whole-chunk proofs. P02 missing sheet/bed proof, S07 tube proof, S11 MK4S-side
prerequisites and the 12 clarification/unavailable variants remain unresolved.
S12's frozen rubric-complete B packets fit whole chunks, while stricter complete
operational scope is absent from candidates; no old label was silently revised.
Retrieval completeness never certifies answer correctness.

# Architecture comparison and single recommendation

| Direction | Measured opportunity | Cost/risk and decision |
|---|---|---|
| Existing B/C | Reproducible original baselines | **Retain; production A unchanged** |
| Query decomposition | Zero new complete candidate sets; regressions at equal raw budgets | 41 query vectors, 101 vs 60 searches per chunker/condition; reject tested mechanism |
| Source-faithful extraction | S13/S06 token savings; no added complete case beyond whole oracle; P03 unresolved | Domain-sensitive scope, source/citation handling; review boundaries before runtime engineering |
| Combination | Zero new complete coherent sets in every library | Added complexity without measured completeness benefit; do not prioritize |
| Semantic reranking | Existing candidate order gaps remain | Prior BGE/GTE CPU K20 median overhead 27.74/12.44 s and regressions; absent candidates stay absent |
| Hierarchical/section-aware | Missing section discovery remains a bottleneck | Prior routing lost valid candidates, depended on distractor layout, showed no long-document gain; no automatic promotion |
| Larger context | Coherent P03 witnesses fit above 1,000 | Cannot repair absent candidates; no generation-quality evidence; not a default change |

**Primary recommendation: no architecture change or new engineering experiment
now.** Domain/source-boundary adjudication is the next prerequisite. This rejects
the tested mechanism, not the general research topics. Do not repeat rejected
FTS5/RRF, lexical/redundancy selector objectives or this focus strategy under new
names. A future genuinely different mechanism needs a frozen development result
before the approximately 24 new intent-family holdout is created. That holdout
was not generated here; all present questions remain exposed development data.

# Reproduction, tests and preservation


External package: `C:\Users\korne\.codex\visualizations\2026\11\16\01a1e47e-cedb-70e1-a4df-b6d1aa1ea057\laew-fine-evidence-v1`.




`decomposition/` preserves the pre-label mechanism/workload freeze;
`embeddings-authorized/` records the exact approval, weight/catalog compatibility,
six dispatch receipts, 41 vectors and job snapshot. `decomposition-retrieval/`
has sealed native rankings, 240 controls, search receipts and provenance;
`decomposition-scores/` has all 360 reference evaluations and complete extraction
witnesses. `completed-reports/` has the all-60 CSV, every requirement/safety/
restriction gain/loss/tie, language strata and nonadditive combined bounds.
Original pre-authorization reports and all rejected/intermediate runs remain
preserved. The main extraction oracle is `analysis-v3/`.

Reproduce offline with `scripts/run_isolated.py --keep-diagnostics eval
laew.eval.decomposition_retrieval_study collect --package <package> --output fresh`,
then `score --package <package> --retrieval <saved-collection> --output fresh`.
Collection reuses the 41 approved cached vectors and performs no new inference.
Copy retained work outputs into fresh external directories in the same shell
call. `laew.eval.fine_evidence_report --completed --package ... --output fresh`
rebuilds these final reports. Do **not** rerun the authorized embedding job for
reproduction; use its sealed cache. Socket access is blocked in offline analysis.

Tests and integrity receipts are recorded in `final-verification.json`; relevant
new contracts and frozen retrieval/scoring acceptance use `scripts/run_isolated.py`.
No original sources, questions, rubric, saved A/B/C or rejected results changed.
No production RAG, model answer, Luna inference, LLM judge, corpus rebuild,
independent holdout or Git add/commit/push/reset/clean occurred.
