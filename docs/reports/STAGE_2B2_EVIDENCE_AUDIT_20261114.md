---
title: Stage 2B.2 — Post-result evidence audit and answer preparation
date: 2026-11-14
status: conditionally-ready-preparation-only
scope: offline agent audit; no answer generation or independent human validation
---

# Finding and decision

The pilot's **0/9 complete selected contexts in every arm survives the diagnostic**.
Full-span matching under-credits some sufficient passages, but that alone does
not explain the pilot failures. Retrieval and context selection both lose
required evidence. Keep production legacy / cosine / K2 / top2 / 500 unchanged.

Recommendation: **conditionally ready for a descriptive 36-attempt pilot** after
rubric/domain adjudication, a mock-tested dispatch budget/telemetry wrapper,
explicit live authorization and a fresh OAuth catalog preflight. Preparation
is complete; live execution is not ready now. No provider, keyring, OAuth
refresh, answer generation, LLM judge, embedding computation, index mutation or
retrieval rerun was used for this audit. The embedding service was separately
checked at the user's request and was healthy; its preparation is unnecessary.

# Inputs, integrity and provenance

The exact benchmark specification is
[STAGE_2B2_REAL_WORLD_RAG_BENCHMARK_SPEC_20261111.md](STAGE_2B2_REAL_WORLD_RAG_BENCHMARK_SPEC_20261111.md).
The R3D admission report, R3F completion report, dataset/retrieval report,
pilot v4, sealed v3, frozen source originals/maps, traces, analysis, regression
records and zero-network payload replay were inspected.

Before scoring, verification passed for all **777 frozen files**, all **16 pilot
and 10 sealed manifest members**, all **201 retrieval artifact members**, and
the questions-only input manifest. Trust anchors remain:

| Artifact | SHA-256 |
|---|---|
| Source freeze manifest | `5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19` |
| Pilot v4 manifest | `9060c3027424da26c5c49888cea62d423a7df543242258f8eb0629c58360bcf6` |
| Sealed v3 manifest | `4f19aba5f77f8012d74bdfdfc7305cdbba330672fa82138c8b108480eec9e437` |
| Retrieval artifact manifest | `4bdbeed19cf75a4e435dc1d5ee1111cf26736c29f1ed3436acd6b99d52b5aad5` |
| Trace manifest | `e91d52ea4209fc44dc32faaa22ad5e8adda13367939f6e21fc3db20116cb342a` |

All **81 reference spans** were re-extracted against the frozen originals and
source maps and matched their source identity, revision, offsets and hashes.
Software passages underwent the existing AsciiDoc/HTML fidelity checks. For PDF
spans, this repeats mapped-text integrity and inherits prior visual QA; it is
not a fresh visual review of every span. Current targeted raster inspection
covered MINI PL PDF 18/42/43/44, MK4S EN 6 and MK4 DE 32. Only publisher prose,
table cells and callouts were used. No unavailable diagram meaning was inferred.
All ten restricted components and 329 uninspected High findings remain open.

This is **one agent's post-result review**. EN/PL/DE question meanings were
compared, but no independent bilingual/domain approval or reviewer agreement
was invented. The agent has seen sealed results. Any later correction is a
transparent post-result correction; new generalization claims require a genuinely
new holdout with new intent families and no tuning on these failures.

Artifacts are outside Git and Obsidian:
`C:\Users\korne\.codex\visualizations\2026\11\14\01a1da01-8abc-7562-a1bb-4ff142d78912\laew-evidence-audit-v1`.
They include exact historical score copies, per-family findings, every stage's
per-question diagnostics, source checks, proposed evidence refinements,
correction proposals, blinded answer review templates, generator-only payloads,
reproduction scripts, test logs and integrity receipts. Source-bearing excerpts
and real-world questions are kept out of the repository.

# Original versus diagnostic metrics

The historical scorer and label files are unchanged. The audit exactly
reproduced every original stage score for **180 question/arm rows**.
The diagnostic applies 13 explicitly authored, hash-pinned fact-specific
subspan refinements within original source spans. Every retained fragment must
be visible, conjunctions remain conjunctions, and original coherent alternative
sets remain separate. No shorter span is selected automatically from overlap.
These are agent-proposed sufficiency judgments, not approved corrected gold.

Examples: omit console output from a branch-deletion command; retain the MK4S
product identity plus complete environmental/power rows instead of its whole
specification table; retain the XL sensor-off loading branch rather than also
requiring sensor-on instructions. Conditions, units and product identity remain.

| Split | Arm | Original raw recall | Diagnostic raw recall | Original selected recall | Diagnostic selected recall | Original / diagnostic selected complete |
|---|---|---:|---:|---:|---:|---:|
| Pilot | A | 14.8% | 14.8% | 13.0% | 13.0% | 0/9 / 0/9 |
| Pilot | B | 38.9% | 38.9% | 14.8% | 14.8% | 0/9 / 0/9 |
| Pilot | C | 31.9% | 34.1% | 13.0% | 13.0% | 0/9 / 0/9 |
| Sealed | A | 26.9% | 26.9% | 11.5% | 11.5% | 2/39 / 2/39 |
| Sealed | B | 46.2% | 51.3% | 32.1% | 33.3% | 10/39 / 10/39 |
| Sealed | C | 55.1% | 56.4% | 37.2% | 37.2% | 13/39 / 13/39 |

Eligible metrics equal raw metrics. The sole selected gain is **S05-en/B,
power-supply fact F2**. Other refinements expose additional raw evidence in
P02-de/C, S05-en/C, S05-de/B and S07-en/de/B without making selected contexts
complete. Complete raw counts also remain unchanged.

Across original missing-fact cases, the diagnostic classifies 165 as no
registered evidence retrieved, 60 as context-selection/budget loss, 67 as partial
evidence needing semantic/domain review, and one as mechanical under-credit
under the proposed refinement. Another 36 unsupported question/arm rows have
positive recall N/A. These are correlated fact × language × arm counts, not
independent samples. Missing registered evidence does not establish that every
retrieved sentence is irrelevant; unjudged alternatives remain unjudged.

Visible non-whitespace character fractions are provided only to prioritize
review. A 90% fragment can omit a negation, condition or number. No overlap
threshold is presented as semantic sufficiency. The diagnostic remains
conservative and does not exhaust all valid alternatives.

# All-family evidence audit

The external `family-audit.json` and `evidence-review.html` contain all 60
variants, exact source excerpts/versions, fact-level alternatives and paired
stage metrics. The following findings apply across each family's EN/PL/DE
variants unless a language-specific case is named.

| Family | Finding and remaining adjudication |
|---|---|
| P01 | Local identity commands, repository scope and precedence are supported. Repeated identity passages consume selected context while scope is missing. Git Configuration supplies omitted source alternatives. Whether coherent sets may mix equivalent language editions needs adjudication. The note that the dataset executes no commands is provenance, not a graded answer warning. |
| P02 | Conditional cleaning, cool-surface/burn warning and first-layer/Live Z after a sheet change are supported. The first-print IPA directive on PDF 18 must not become mandatory solvent use on every replacement. Whole preparation/table spans include unrelated material. No full recalibration or numeric offset is required. |
| P03 | All six dependency/configuration/restore facts have source support. B's English raw evidence is complete but selected loses four facts; C also loses retention in raw. Ten-day default versus fourteen-day basis is retention planning, not an exact failure deadline. REL_17_STABLE WAL versus REL_17_10 backup compatibility still needs domain review. |
| P04 | Runtime major version is missing. Ask for it and give safe version-conditional explanation. Positive recall remains N/A; conditional facts are still graded in answers. No unconditional recovery-file edit. |
| S01 | Native text supports directional purging and dark-to-light contamination. 100/60 mm³ are illustrative, not guaranteed settings. Screenshots are unnecessary evidence. |
| S02 | Command and garbage-collection interpretation have authentic EN/PL/DE alternatives. Console output is not required. Merge/team agreement are already stated prerequisites. |
| S03 | Windows `true` and Linux/macOS `input` conversion directions are supported. Other configuration strategies remain unjudged until grounded alternatives are admitted. |
| S04 | Soft limit, failed archiving and recovery-time caveat are supported. F2 bundles several conditions; a soft-limit sentence alone is insufficient. Review whether the optional tuning caveat should be mandatory for a narrow answer. Never advise deleting needed WAL. |
| S05 | Native table confirms exact environment and power values. Whole-table/serial-label requirements are overbroad for these facts. Actual workshop measurements remain unknown. |
| S06 | Model/selftest and FAT32/BBF/rollback facts are supported. C's English selected context loses initial selftest. A local page-32 downgrade callout is omitted from alternatives, but does not name Flash, so it cannot automatically replace the full existing F2. MK4S is not an interchangeable model. |
| S07 | Sensor-off sequence and conditional tube replacement are supported. Sensor-on branch is over-required. Loading and tube maintenance still require distant sections. |
| S08 | Four tubes, compressed air, wear, 10 mm wrench and stuck-filament triage are supported. External full hotend repair/torque instructions are not established. Correlated with S14. |
| S09 | Native MK3S flow controls and persistence into later jobs are indispensable; generic ABS advice is not an equivalent source. Keep ASA/ABS scope and PLA heat limitation. |
| S10 | Nested initialization and `check` publication guard are supported; `on-demand` remains optional. Polish source contains English fallback publication text; assign language per passage. Its older recursive-clone text is not automatically an after-clone nested-update alternative. |
| S11 | Separate MK4S/MMU3 files/connections and disconnection/simultaneous-USB warnings are supported. Seven spans across two manuals expose budget losses. Do not discard warnings to obtain a complete score. |
| S12 | 11 versus 17 APIs, initiating session and byte-exact returned files are supported. The new-API paragraph includes unnecessary checkpoint tuning; the session span also includes an unrelated label explanation, still conservatively unrefined here. C English loses metadata in raw and favors old-version context. |
| S13 | Version-specific timeline defaults and valid-descendant restriction require complementary 11/17 evidence. Versions are not interchangeable alternatives. Correlated with P04/S12. |
| S14 | M3x12/loosening is present; exact manufacturer torque is not established. Preserve prior all-24-source inspection and require independent bounded-absence review. Do not infer a number or world absence. |
| S15 | A generic push example does not identify the user's remote/source/destination. Request missing context; any template must be explicitly hypothetical. |
| S16 | Explicit XL PDU/graphical restrictions block terminal position and drawn symbol. Nearby labels cannot establish either. Qualified original-diagram review remains outside supported scope. |

No draft technical statement was conclusively falsified in this review.
Source-grounded shortcomings concern evidence granularity, omitted alternatives
and rubric scope. `label-correction-proposals-v1.json` proposes P01 alternative
sources and operational-note cleanup plus review of S06's local callout.
These proposals are **not applied or rescored**. Accepted changes require a new
complete dataset version, parent hashes, exact diff/reason, reviewer provenance
and rescoring all arms separately from the original baseline.

# All five B-to-C regression cases

| Case | Source-grounded classification |
|---|---|
| P01-en | Raw loses F2/F3: B complete → C incomplete. Both selected contexts retain only identity F1. Missing scope/precedence is a retrieval loss in C and a selection loss in B, not removed by subspan refinements. |
| P01-de | Same raw loss. B selected includes an earlier scope fragment but lacks complete repository-specific scope/precedence. Selected scores stay tied. |
| P03-en | B raw complete → C raw misses retention F4. Selected B has F2/F5, C only F2. C retrieves chain evidence but does not deliver it; separate raw retention loss and selection loss. |
| S06-en | Both raw complete. B selected has F1; C selected has neither fact because initial-selftest text is absent and F2 lacks the complete file/procedure bundle. Page-32 alternative is a review proposal, not permission to award missing facts. |
| S12-en | B raw has metadata F2, C raw does not. Selected both score zero; C selected mainly supplies old-version passages. Partial 17 API/session content in B merits further fact-granularity review. |

# Methodology and Stage 3C.3 preparation

The scorer already unions visible ranges across chunks, ignores whitespace-only
gaps, preserves coherent alternatives, excludes unsupported positive recall
and separates raw/eligible/selected evidence. Trace source IDs and frozen hashes
bind versions. It does not semantically judge equivalent sources, guarantee
real evidence-language necessity, or independently validate bounded absence.
Strict same-language evidence sets can exclude otherwise compatible translated
passages; retain that as unresolved review, not a retrieval optimization target.

Historical zero-network replay verified exact context delivery for 180 rows.
The new pilot builder additionally captures **36 actual first-dispatch OAuth
payloads** using fixture credentials and intercepted transport. It includes the
existing executor's static wrapper, fresh empty history, no tools, disabled
project-language instruction and the exact frozen selected contexts. It stops
before HTTP or any generated response. A separate generator directory contains
only requests/plan/manifest; gold, notes and review materials are excluded.

See [the final answer protocol](STAGE_3C3_ANSWER_EVALUATION_PROTOCOL_20261114.md)
for exact instructions, manual scoring, execution order, costs, guard requirements
and reproduction commands. All-incomplete pilot contexts make this primarily a
study of safe partial answering and uncertainty, not a fair test of fully
informed technical answering. Do not enrich contexts with gold or silently
drop difficult questions. A future oracle-context study would be a separate
experiment.

# Validation and repository state

**57 tests passed** through `scripts/run_isolated.py`, including source/version
matching, overlap unions, conjunctive fragments, coherent alternatives,
unsupported N/A, frozen dataset integrity, leakage rejection, exact first
dispatch, 36-request counterbalancing and existing selector/chunker regressions.
The initial focused run passed 22 tests and skipped three corpus-dependent
checks; the final run supplied the frozen paths and passed all 57 without skips.

Initial Git status was clean. Added files are the two evaluation-only modules,
their focused tests, this report and the final answer protocol; the documentation
index is updated. No production code/configuration or historical report was
changed. `validation.json`, source snapshots, a private diff and final Git status
are in the external artifact directory. No Git add/commit/push/reset/clean ran.

The exact next decision is to assign/approve domain and bilingual adjudication
of the pilot rubric and evidence proposals, then authorize implementation of
the evaluation-only dispatch guard/telemetry preflight. Live approval must name
the existing ChatGPT registration, public-content transmission and plan-usage
allowance for **36 maximum attempts**, with no retries or sealed calls.
