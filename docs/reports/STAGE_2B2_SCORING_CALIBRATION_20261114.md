---
title: Stage 2B.2 — Evidence and answer scoring calibration
date: 2026-11-14
status: calibrated-offline-agent-review-pending-human-adjudication
scope: evaluation methodology only; no retrieval or live answer execution
---

# Result

The calibrated pilot has **3/9 minimum-sufficient selected contexts in each of
A, B and C**, compared with the preserved historical **0/9 full-reference
contexts**. All nine newly complete question/arm rows concern P01: three language
variants in three arms. Its delivered identity passages already explain
repository-specific configuration and overriding global identity. Requiring the
`.git/config` filename and an additional system-level precedence explanation was
unnecessary for this question. P02 and P03 still lack complete selected evidence.

This is **non-blind methodological calibration after observing sealed results**,
not improved retrieval, blind validation or independent human validation. Rules
were source-authored and hash-frozen before the new arm scores were calculated.
The same rules apply to every arm and EN/PL/DE variant. No rule was changed to
improve a revised score. Original sources, questions, labels, traces, scores,
the previous audit and its diagnostic results remain unchanged.

The implementation is ready for **reviewer-assisted semantic scoring and offline
use**. Domain/bilingual adjudication of the agent-authored judgments remains
necessary before treating them as accepted reference criteria. The separate
live pilot still requires the runtime guard, telemetry and authorization from
the earlier protocol. No live pilot was executed or enabled by this task.

# Versions and artifact locations

Historical reports remain authoritative records of their own versions:

- [Evidence audit v1](STAGE_2B2_EVIDENCE_AUDIT_20261114.md).
- [Original answer evaluation protocol](STAGE_3C3_ANSWER_EVALUATION_PROTOCOL_20261114.md).

This document is their **evaluation-scoring addendum**, not a replacement of
their frozen artifacts, prompts, provider configuration or execution gates.
The future answer evaluator should use the v2.1 requirements described here
instead of interpreting every old bundled fact as universally mandatory.
The old 36-row form remains historical; the new blank review template is
`blank-answer-review-v2.1.json` and contains no generated answers.

The versioned curator-only package is outside Git and Obsidian:

`C:\Users\korne\.codex\visualizations\2026\11\14\01a1da01-8abc-7562-a1bb-4ff142d78912\laew-scoring-calibration-v2`.

| Artifact | Purpose |
|---|---|
| `rubric-v2.1.json` | Shared EN/PL/DE family requirements, applicability, complete methods, invariants and minimum answers |
| `fact-classification-v2.1.json` | Every one of the 46 original facts mapped to classified components |
| `source-atoms-v2.1.json` | 112 exact, source/version-bound evidence atoms; includes original spans for provenance |
| `MINIMUM_ANSWERS_AND_FACT_RUBRIC_V2_1.md` | Readable requirements for all 20 families and 60 variants |
| `requirement-change-log-v2.1.json` | Each conditional/optional/alternative requirement, source proofs and rationale |
| `calibrated-per-question-v2.1.json` | All 180 rows, three stages, original/v1/calibrated scores and evidence distinctions |
| `calibrated-summary-v2.1.json` | Split/arm/language aggregates with denominator caveat |
| `complete-context-changes-v2.1.json` | Every complete/incomplete change; no selective omission |
| `software-atom-original-ownership.json` | Exact AsciiDoc original-line ownership, including the added on-demand alternative |
| `blank-answer-review-v2.1.json` | 36 future-answer review records with empty answers and separate dimensions |
| `input-integrity.json`, `validation.json`, manifests | Trust anchors, checks, preservation and implementation snapshots |

The initial v2 authoring freeze is preserved. A **pre-rescoring v2.1 addendum**
adds the actual `summarize_wal` and `wal_summary_keep_time` definition atoms:
an identity-free enabling sentence or numeric default must not earn credit for
the wrong parameter. Neither v2 nor v2.1 arm metrics had been computed when this
source-identity correction was frozen. Effective rubric manifest SHA-256:
`36f985c702203012166f99b5a53850acea6e77f5d80ef25c0514dcdec870cee3`.

# Requiredness and minimum-answer semantics

The 46 original facts are decomposed into **73 requirements**. Requiredness has
four values; safety-critical is an **orthogonal flag**, not permission to ignore
a warning outside one categorical bucket.

| Classification | Treatment |
|---|---|
| Essential | Every complete method must cover it. |
| Conditional | Mandatory when its explicit procedure/situation trigger applies; an unknown trigger is unresolved, never automatically waived. |
| Optional | Its omission does not reduce minimum completeness. If asserted, it must still be correct and grounded to earn a fully grounded answer. |
| Alternative | Required only for a chosen complete method. One complete valid method suffices; incompatible partial methods cannot be combined to manufacture completeness. |
| Safety-critical flag | An applicable missing warning/constraint prevents a pass. Correct units, polarity, versions, dependencies and product scope remain enforced. No safety-critical requirement is classified optional. |

For future answers, applicability comes from the question-fixed scenario and
exhaustive semantic review of what the answer actually advises. Reviewed
procedure triggers activate relevant conditions; a false declaration cannot
silently override an annotated cleaning action. Changing a question-fixed
condition or selecting a contradictory method rejects the review as invalid.
Unresolved applicability prevents a complete pass.

For **retrieval-only scoring**, the answer does not exist. Therefore each
complete method states its assumptions about which procedures are advised.
For example, P02's no-cleaning-procedure path does not assume the sheet is clean:
it still requires need-based cleaning assessment, a fitted sheet/debris-free bed
and first-layer checks. It does not offer cleaning instructions. The IPA and
water-cleaning paths add their applicable method and safety evidence. All path
scores and assumptions are retained, even when the aggregate chooses one
sufficient path. The actual answer cannot borrow that path if it advises a
different procedure.

The scorer does not require every valid solution, exact wording, all console
output, an entire unrelated table, or optional procedural explanations. It does
require a complete admitted proof for each active technical proposition. There
is no character-overlap cutoff, keyword shortcut or score-based rule selection.

# All-family minimum sufficient answers and corrections

Exact source-backed components, original-fact mappings, canonical technical
invariants and all three question variants are in the external rubric. The
following table summarizes their minimum scope, rather than prescribing an
exact reference response.

| Family | Minimum sufficient requirements and calibration |
|---|---|
| P01 | Local name/email in the intended repository and precedence over conflicting global identity. Filename/system-level tutorial optional. Identity passages explicitly support project override. |
| P02 | Debris-free bed, mounted sheet, first-layer observation/Live Z as needed and need-based cleaning. Cleaning instructions activate cool-surface/burn conditions; IPA advice activates its concentration/sanitizer qualifiers. Routine solvent use and full recalibration are not mandatory. |
| P03 | Enable summaries, use the same-server prior manifest, retain the complete summary interval, plan beyond the fourteen-day dependency despite the ten-day default, preserve compatible backup ancestry for reconstruction plus WAL/history. Checksum-change and restore-execution details apply to those discussions. Exact deletion/failure timing is never inferred. |
| P04 | Establish actual major version before selecting a recovery-file procedure. Optional version explanation must preserve the 11/12+ boundary; advising 12+ configuration activates normal-settings/startup conditions. Clarification can be sufficient. |
| S01 | Purging-volumes directionality and dark-to-light contamination; no mandatory numeric examples. If example numbers are used, they cannot become guaranteed settings. |
| S02 | Correct remote-branch deletion and explanation of reference removal versus object retention/garbage collection. Console output is unnecessary; no indefinite-recovery promise. |
| S03 | Correct Windows/Linux settings and conversion directions. No full configuration tutorial or unrelated solution enumeration. |
| S04 | Soft checkpoint-related limit and failed-archiving exceedance. Other example causes optional. Recommending an increase activates the recovery-time caveat; a hard disk-cap claim remains wrong. |
| S05 | Complete environmental and mains values with indoor/non-condensing/product qualifiers. Radio specifications, dimensions, contacts and serial-label placement are not required evidence. |
| S06 | Model applicability and one valid selftest/model-selection remedy after the upgrade, initial-selftest prerequisite, correct FAT32/BBF media and rollback startup entry. The final Flash UI label is optional for this entry-procedure question. Model and prerequisite warnings stay mandatory. |
| S07 | Complete sensor-off loading sequence and conditional tube maintenance/replacement. The sensor-on branch and purchase instructions are unrelated. Heat-before-feed remains required. |
| S08 | Debris/wear maintenance, compressed-air cleaning/replacement as needed, and main-tube blockage triage. Four-tube count is descriptive. Wrench size applies when giving nut-loosening instructions; no invented torque or complete external repair procedure. |
| S09 | One valid flow control plus persistence into later jobs; one documented cracking remedy is sufficient. A material list and both menu/command controls are unnecessary. PLA advice activates its heat limitation. |
| S10 | Complete nested initialization and one protective publication method: check or on-demand. Both are not required. Dependency availability before parent publication remains essential. On-demand is admitted with its command and explicit ordering/failure explanation, not merely its ambiguous one-line label. |
| S11 | Separate model-correct files/media, initial selftest, MMU micro-USB/own firmware, preserved power/MMU connection while flashing and no simultaneous device USB connections. These warnings are not relaxed. |
| S12 | Target 17 start/stop APIs, initiating-session lifetime and byte-exact returned metadata with empty-map condition. Repeating the obsolete API name and optional checkpoint tuning is unnecessary. |
| S13 | Distinct 11/17 defaults and choosing a valid current/descendant timeline. The prohibition on a branch predating the base backup stays mandatory. |
| S14 | Explain that the exact manufacturer torque is not established here; seek the applicable specification. No inferred number or world-absence claim. |
| S15 | Clarify intended remote, destination and local source; defer a definitive command. A clearly hypothetical template is optional. |
| S16 | State that position and symbol cannot be established from text-only material; request original-diagram/qualified review. No electrical-location or symbol-shape inference. |

Not every shorter-source proposal changes a score. S06's nearby downgrade
callout remains a review candidate, rather than being credited automatically.
The calibration keeps the proven complete older-firmware passage. S10's added
on-demand proof has exact frozen normalized offsets and original AsciiDoc-line
ownership. Any inherited nearby location reference is a section anchor;
`software-atom-original-ownership.json` provides exact new line ownership.

# Four evidence distinctions

The unchanged historical source-span score is reported independently of the
new requirement score:

1. **Full registered fact/span coverage:** original full-span/coherent-set rules.
2. **Minimum sufficient evidence:** one whole source-grounded semantic proof
   bundle for every active requirement in a complete method.
3. **Partial evidence:** some non-whitespace overlap with a required atom, but
   no complete admitted proof. Partial text does not automatically satisfy a fact.
4. **Missing essential evidence:** no admitted proof or partial atom for an
   active essential/conditional/method requirement.

Every atom has source identity, frozen revision, normalized hash, exact Unicode
offsets, excerpt hash, original location and semantic rationale. Multiple atoms
inside a proof are conjunctive. Alternative proof bundles are disjunctive.
Version-mismatched sources, wrong offsets, derived annotations and restricted
regions cannot earn credit. An excerpt that drops a number, negation, prerequisite
or parameter identity is insufficient even if its surrounding words match.

The diagnostic distinguishes registered-fact coverage from minimum sufficiency
per requirement/method in its row records. It never overwrites the original
score. P04/S14/S15/S16 retain **N/A positive technical retrieval recall**.
Their epistemic clarification requirements do not create positive evidence hits.

# Answer evaluation implementation and limits

`laew/eval/scoring_calibration.py` implements `score_evidence`, `score_answer`,
source validation and reviewed technical invariants. It imports no provider,
embedding service or retrieval execution path. It consumes already-attributed
source ranges and curator-only rubric data.

**Semantic equivalence is reviewer-assisted, not guessed from strings.** A human
or accurately disclosed agent annotates the actual answer with exact quote
offsets, correct/incorrect/unresolved semantic verdicts, requirement IDs,
canonical checked fields, source-proof IDs and procedure triggers. Nontechnical
segments must also be marked so an extra unreviewed claim cannot escape the
review. Reviewer ID/origin, exhaustive-review attestations and the answer hash
are mandatory. A short paraphrase can pass; a long wrong answer cannot gain
credit merely by containing expected words.

Deterministic checks reject wrong reviewed versions, quantities/units,
polarity, product applicability and dependencies even if a verdict is marked
correct. Equivalent supported units can normalize to the same physical value;
dimensions never disappear. Scope inherited explicitly from the question can
be recorded in reviewed fields without forcing redundant version prose.
Every asserted optional claim is still reviewed. Unknown extra technical claims
remain unresolved until grounded/adjudicated; the system does not automatically
call them true or false.

Outputs separate:

- factual correctness: correct, incorrect or unresolved;
- minimum completeness and missing active requirements;
- applicable critical omissions and conservative safety pass;
- grounding in **delivered** evidence, independently of reference correctness;
- a minimum-answer pass versus a fully grounded-answer pass.

A correct fact without delivered support may pass correctness and minimum
completeness but fails fully grounded-answer scoring. An incomplete answer can
remain factually correct. Proper epistemic clarification can pass unsupported
questions without inventing technical evidence. A fabricated technical conclusion
cannot pass merely by being labelled uncertainty.

This layer **does not automatically parse arbitrary prose or detect whether a
reviewer has mislabelled a sentence**. Exhaustive claim identification, entailment,
correct annotation of triggers and adjudication remain human/agent review tasks.
The synthetic tests demonstrate behavior with manually authored semantic
annotations; they are not evidence of a general automatic natural-language
judge. Citation accuracy, language and conciseness retain separate manual
dimensions in the new blank review template.

# Original, previous diagnostic and calibrated results

The original baseline and v1 diagnostic are preserved. All **540 original stage
scores** (180 rows × raw/eligible/selected) were reproduced exactly before
comparison. New scoring reused the same trace ranges and contexts.

**Denominators differ:** historical recall averages bundled reference facts;
calibrated coverage averages active minimum-answer requirements. These columns
are different estimands, not a retrieval-improvement percentage. Complete-case
counts still use the unchanged 9 answerable pilot and 39 sealed variants, but
their definition of sufficient evidence is explicitly versioned.

| Split | Arm | Original selected recall | V1 diagnostic recall | Calibrated minimum coverage | Original → calibrated complete |
|---|---|---:|---:|---:|---:|
| Pilot | A | 13.0% | 13.0% | 35.2% | 0/9 → 3/9 |
| Pilot | B | 14.8% | 14.8% | 37.0% | 0/9 → 3/9 |
| Pilot | C | 13.0% | 13.0% | 46.3% | 0/9 → 3/9 |
| Sealed | A | 11.5% | 11.5% | 19.4% | 2/39 → 2/39 |
| Sealed | B | 32.1% | 33.3% | 40.6% | 10/39 → 10/39 |
| Sealed | C | 37.2% | 37.2% | 41.7% | 13/39 → 15/39 |

Raw complete counts change from A/B/C = 0/3/1 to 3/4/3 on pilot, and 8/15/18
to 8/17/18 on sealed. Eligible results equal raw results. Selected gains are
exactly P01 EN/PL/DE in all arms and S08 EN/PL in C. S08's complete triage answer
does not need the descriptive tube count or a nut-loosening tool specification
when it does not give those disassembly steps. If it gives them, that requirement
is activated and remains checked.

The remaining six incomplete pilot variants are P02 and P03. They still lack
core source support, not merely optional details. The sealed source/family
correlations and post-result exposure remain unchanged; this calibration does
not support new superiority/generalization or deployment claims.

# Validation, preservation and readiness

**76 tests passed**, with no skips, through `scripts/run_isolated.py`. Nineteen
calibration checks cover short correct paraphrases, a complete alternative
method, optional omissions, incorrect longer answers, version/unit/polarity
errors, equivalent unit normalization, applicable/unknown safety conditions,
missing required facts versus factual errors, unsupported extra claims,
appropriate clarification, source integrity and the real all-family rubric.
The other 57 checks cover the prior diagnostics, frozen dataset integrity,
zero-network payload preparation and existing selector/chunker behavior.

Before use, the 777-file source freeze, both dataset manifests and the previous
66-file audit package were verified. Before rescoring, all 201 historical
retrieval artifacts were checked. All 112 atoms are source/version bound and
exclude the ten restricted components. All 329 uninspected High findings and
other open source risks remain open. No new visual/diagram interpretation or
independent human validation is claimed.

Changed repository files for this task are the new scoring module, focused
tests, this report and one additive documentation-index entry. The six existing
dirty/untracked files were verified unchanged and snapshotted before that index
addition; the five non-index files remain byte-identical. The initial index
content is preserved with only the new entry added. Git status, snapshots,
hashes, test log and reproducibility checks are in the external package. No Git
add, commit, push, reset or clean was used.

To repeat, copy the authoring scripts into a **new external package**, run
`prepare_rubric.py`, `prepare_source_identity_addendum.py`, `rescore.py` and
`render_review_material.py` with the repository venv. Existing outputs must not
be overwritten. Preserve pinned source/scorer hashes. The scripts are offline;
the test command is recorded in `validation.json` and uses the isolation runner.

Remaining review concerns are the agent's P01 cross-language entailment
judgment, conditional-boundary decisions in P02/P03/S04/S08, all admitted
alternative-method equivalences, bundled fact decomposition, bounded absence
and version/domain judgments. These require explicit reviewer provenance and
adjudication. Genuinely new generalization claims require a new holdout.

**Stop after calibration.** No A/B/C configuration, context selection,
production code/settings, embeddings, indexes or frozen documents were changed.
No Luna, live answer or LLM-judge call occurred. Technical methodology preparation
is complete; the next step is human acceptance/adjudication of this rubric before
the separately gated future live test.
