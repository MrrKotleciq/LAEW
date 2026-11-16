---
title: Stage 2B.2 — Complementary context selection, pre-implementation diagnosis
date: 2026-11-15
status: development-diagnosis-before-selector-implementation
scope: frozen 60-question development data; no model execution
---

# Findings

The six requested research reports, the original novelty experiment, production
renderer, attribution, candidate traces, source mapper and repaired v2.1 scorer
were inspected. All 60 questions are exposed development data. Historical sealed
denotes the old split, not a fresh holdout. B is the primary development baseline;
C is the chunking comparison; production A remains unchanged.

Before selector implementation, verified the 777-file restricted freeze, 201
retrieval artifacts, trace manifest, sanitized questions, pilot/sealed dataset
manifests and the calibration package. Reconstructed source chunks with
`embed=False`, checked frozen hashes and source ranges, reproduced all 180 exact
historical rendered contexts and all 540 calibrated stage scores with the repaired
scorer. No saved Luna answers were read by the study. The scorer repair changes
answer applicability, not evidence scoring. Semantic judgments remain provisional.

Source-bearing diagnostics and verification receipts are in the external package
`C:\Users\korne\.codex\visualizations\2026\11\15\01a1e0fc-bdd1-7270-b6a8-0c30a576f884\laew-complementary-selection-v1\root-cause-v1`.

| Failure mode | Observed cause and selector limits |
|---|---|
| Absent registered proof | B has 103 and C 104 unsupported requirement instances across answerable rows, including optional/conditional branches. This is absence of a complete admitted proof, not proof of irrelevant text. Selection cannot invent the missing evidence. P02/B has zero minimum coverage in every language; P03 PL/DE has substantial candidate gaps. |
| Present but discarded | B loses 38 and C 32 supported requirement instances between native candidates and context. These counts include optional/conditional requirements and correlated languages. P03-en/B has complete raw minimum evidence but selected coverage is 2/6; C goes from 5/6 to 1/6. |
| Redundant passages | Mean repeated source characters are B 59.4, C 200.3. Structure-v2 repeats related context; legacy has overlapping fragments. Translations can repeat meanings without identical text; lexical methods cannot reliably identify that equivalence. |
| Attribution overhead | Mean attribution is B 1,036.0 and C 1,017.3 characters per context. P03-en has repeated navigation tags; B spends 1,938 characters on attribution. This is material budget cost. Compact-only D1 was rejected because its changed greedy admission displaced later useful fragments. |
| Conditions/prerequisites | Whole-source bundles often cross fragments. Missing evidence includes summary retention, configuration identity, restore WAL/history and model/version prerequisites. A warning word does not establish applicability. All admitted procedure branches require separate coverage checks, even for unsupported positive-recall questions. |
| Different sections/documents | P03 needs WAL settings plus backup dependencies. S07 needs loading plus tube maintenance. S11-en K10 is entirely MMU3 in both B/C: the absent MK4S half is a retrieval problem. S13 requires distinct PostgreSQL versions; translated or version-different passages are not interchangeable. |
| Similarity without information gain | Ranked fill spends budget on near-equivalent configuration/identity passages, product-neighbor advice and repeated old-version sections. Higher cosine is not additional necessary evidence. |

Across all 60 questions, mean context size is B 922.2 and C 907.9 estimated
tokens. Raw complete counts (pilot/sealed) are B 4/17 and C 3/18; selected counts
are B 3/10 and C 3/15. These are v2.1 minimum criteria, not historical full-span
scores. Candidate availability is an upper bound, not a promise that whole
complementary fragments fit within 1,000 tokens.

# Technical hypothesis frozen before implementation

Test a bounded, joint subset optimizer over the same eligible native K10.
Whole fragments preserve local procedure context; no sentence extraction,
warning-keyword priority or inferred dependency graph is introduced. Original
cosine, marginal lexical information and modest section complementarity determine
utility. Exact subset enumeration avoids greedy packing mistakes at K10.
Only discovery tags/backlinks may be removed from copied attribution; all source,
scope, section, type/status and source/version identity remain bound and auditable.

This differs from both prior mechanisms: novelty used greedy token-set Jaccard;
D1 changed metadata but retained greedy ranking. Here selection optimizes the
complete feasible bundle. Compact attribution is a supporting budget change,
not a sufficiency or safety claim. Its contribution must not be mistaken for a
proven benefit of the optimizer alone.

Begin with one fixed implementation, synthetic tests, then pilot diagnostics
and all 60 questions. If joint selection displaces existing requirements or
warnings, allow one motivated refinement: constrain the chosen subset to retain
all baseline-delivered bodies. That conservative candidate-only constraint can
preserve unknown prerequisites without reading rubric labels. It may retain
redundancy or prevent improvements; reject rather than waive that limitation.
No parameter sweep, question-specific rules or label changes are planned.

All ten corpus restrictions, 329 uninspected High findings and other source risks
remain open. No production edits, embedding, retrieval, answer generation, Luna
calls or holdout creation are involved. Existing working-tree changes are pinned
for preservation. The user explicitly authorizes this new development study;
historical reports' stop recommendations remain records of their original scope.
