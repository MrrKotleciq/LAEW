---
title: Stage 2B.2 — Proposed source-evidence boundary specification
date: 2026-11-16
status: post_result_agent_boundary_review
scope: review specification only; no runtime implementation or rubric changes
---

# Purpose and status

This specification defines what reviewers should preserve in a source-faithful
evidence passage. It does not implement a selector, extractor, renderer or semantic
classifier. Every new requiredness judgment has origin
`post_result_agent_boundary_review`. Independent domain validation is pending.
Rubric v2.1 and all historical labels/results remain immutable.

A sufficient evidence set supports every essential requirement of one coherent
question-scoped method, including its applicable dependencies and safeguards.
It need not reproduce an entire manual or every alternative procedure. Evidence
for API names, session rules or a file inventory is distinct from a runnable
procedure. The response scope must be explicit before judging completeness.

# Requiredness vocabulary

| Status | Review rule |
|---|---|
| `mandatory` | Removing the text loses a requested proposition, its subject, applicability, condition, unit, negation, dependency or applicable safety qualification. |
| `optional` | Omitting the text leaves the selected propositions and method valid. Examples, repeated explanations and unselected alternatives can qualify; adjacency alone does not decide. |
| `conditionally_mandatory` | Preserve the text whenever its documented trigger is active in the question, selected action or asserted explanation. Record the trigger and its evidence. |
| `unresolved` | Applicability, entailment, boundary or necessary dependency cannot be established. Do not silently treat unknown as false or label the set technically complete. |

Mechanical proof-span presence and a semantic sufficiency judgment are different
claims. A registered proof can pass v2.1 while a stronger executable-procedure
interpretation remains unresolved. Conversely, a whole-paragraph closure can be
overconstrained without changing the frozen proof's historical score.

# Rules for reviewing boundaries

| ID | Topic | Proposed rule |
|---|---|---|
| EB01 | Definitions and identifiers | Retain an unambiguous subject, definition and parameter/API identity. A heading is mandatory only if the body and attribution cannot establish that identity. A free-floating default or “this parameter” needs its antecedent. |
| EB02 | Configuration scope | Preserve allowed configuration locations and access restrictions when configuration is requested or instructed. Do not infer restart/reload semantics from a location-only statement. |
| EB03 | Conditions and negations | Preserve the complete condition–consequence relation, its polarity and limiting scope. A condition may be in a neighboring sentence. Never keep an action while deleting its qualifying “if,” “unless,” “not” or “only.” |
| EB04 | Warnings | Preserve every warning governing the selected action or claimed outcome. Warnings for unselected alternatives are conditional, not universally mandatory merely because they are adjacent. Unknown trigger applicability remains unresolved. |
| EB05 | Ordered procedures | A runnable procedure needs the required sequence, intervening operations, success checks, prerequisites and completion safeguards. Never splice start and stop around omitted work, renumber partial steps, or imply consecutive execution of disjoint ranges. |
| EB06 | Contract evidence | API/session/return-value evidence may be quoted without the entire execution runbook if it is explicitly presented as contract evidence. It must not be advertised as a complete executable migration or procedure. |
| EB07 | Product and version | Bind each passage to the exact source identity, revision and immutable snapshot hash. Keep version-dependent alternatives separate. Similar wording from another product or version cannot substitute. Do not infer the release in which an API changed from only two endpoint-version snapshots. |
| EB08 | Numerical values and tables | Keep units, comparison operators, defaults and the conditions governing numerical values. Preserve table headers, row identity and product scope. Implicit units become mandatory when giving an otherwise unitless value; an unrelated unit-default sentence is not automatically required for an explanation containing no such value. |
| EB09 | Cross-document dependencies | Retain the conjunction of prerequisite sources and the dependency relation. A manifest is not backup data; reconstruction ancestry does not replace recovery WAL/history. Do not collapse different source revisions into one generic citation. |
| EB10 | Adjacent explanation | Retain antecedents and clarifications that change the selected proposition. An explanation of why a rule exists can be optional when the complete direct rule is retained. Review adjacency; do not automatically include or discard an entire paragraph. |
| EB11 | Omitted alternatives | Record the omitted branch and why its trigger is inactive. Do not omit a branch solely to meet a token budget. The absence of an answer means action-dependent triggers cannot be inferred automatically. |
| EB12 | Separate passages | Preserve each exact source range, its order, source ownership and a visible passage boundary. Mark excerpts as independent. Numbered excerpts also need an explicit incomplete-procedure notice. A visible gap prevents a continuity claim but does not certify that a model will respect it. |
| EB13 | Citations | A full source ID, exact revision and full snapshot hash may appear once per source if every passage remains unambiguously assigned to it and carries exact offsets. Short aliases require a complete supplied registry. Never rely on basename or a bare offset alone. |
| EB14 | Offset semantics | Declare zero-based, half-open Unicode-code-point offsets in the immutable normalized LF text. These are not PDF byte offsets, browser UTF-16 positions or raw HTML byte offsets. Original-location anchors and parent excerpts are provenance links, not invented exact offsets for newly narrowed clauses. |
| EB15 | Restricted/graphical material | Restricted or unavailable visual components cannot earn textual proof credit. Do not infer diagram position, shape, polarity or unavailable values from neighboring prose. Existing restrictions remain open. |
| EB16 | Missing context | Distinguish text absent from the candidate pool from text available in the frozen source for review. A source-reference witness does not establish retrieval availability. Do not silently fetch, append or credit missing neighboring ranges. |
| EB17 | Uncertainty | Record incomplete equivalence, applicability and boundary judgments explicitly, with a reviewer question. Mechanical source matching is not independent semantic validation or answer correctness. |

# Application to the disputed cases

**P03:** preserve the enabling parameter definition; same-server manifest;
complete prior-start/new-start LSN scope; retention identity, dependency interval
and ten-day default; supplying backup ancestry; checksum caution when discussing
the reconstruction tool; recovery WAL/history; and the explicit safeguard against
removing a still-required ancestor. The audited reconstruction-aware witness also
keeps the full wait/catch-up qualification for summary availability.

The fixed question uses `wal_level=replica`; the proposed minimum enables
summarization. Minimal-WAL, disabled-summarizer, zero-retention and manual-deletion
alternatives are not being advised. Their safeguards remain conditional. Implicit
minutes are required for unitless numeric settings; this witness instead retains
the explicitly unit-bearing default and qualitative retention rule. A recovery
execution procedure would additionally require signal-file and execution scope;
the original question asks for configuration and retained files.

**S12:** API identity, initiating-session lifetime/abort behavior and the complete
returned-file mapping/empty-field/byte-preservation constraints are mandatory.
Same-connection stop is a genuine dependency when giving invocation guidance.
Privileges, actual file copying, primary/standby WAL-switch behavior, archive
waiting and timeout validity conditions govern a runnable procedure or those
specific operational claims; they are not automatic closures of every API-name
or metadata sentence. The question's “porting a script” wording makes the
name-only versus script-contract expectation a priority domain-review issue.
The stronger invocation excerpt is not a complete backup procedure.

**S04:** the original question asks whether `max_wal_size` is a hard bound while
archiving fails. Its two-sentence source proof explicitly names the parameter,
automatic-checkpoint context, soft limit and failing-archive exception. Default,
configuration-location and entire-paragraph closures are not necessary for that
explanation. Increasing the limit activates the crash-recovery caveat. The audit
does not recommend increasing a value or infer that doing so repairs archiving.

# Serialization and budget contract

Use the existing estimator, `ceil(total_characters / 4)`, after joining the
complete context. Count attribution, ranges, separators and notices. Character
savings are additive; separately rounded token differences need not be.

The historical 1,000-token comparison is a **per-scope** budget. The existing
global section wrapper belongs to the separate 8,000-token overall allocator.
Report both costs when a witness is near the boundary. A fixture that fits the
former must not be called a sub-1,000-token entire enclosing section.

Distinguish metadata removal, citation grouping, exact same-source overlap
removal, synthetic payload removal and actual source-body extraction. Hold the
body fixed when claiming a citation-only saving. Never deduplicate equivalent
text across different source identities by string equality alone.

# Review and future implementation gate

The compact review package contains exact excerpts, 37 proposed decisions,
alternative response scopes, fixed witnesses, costs and blank reviewer fields.
Its proposals are post-result agent review, not independent human validation.
The independent reviewer must record identity, origin, proposal exposure,
decision, rationale and any changed source ranges. No field defaults to approval.

These rules are sufficiently explicit for reviewing static witnesses and a
future fixed-body citation experiment. They do not yet define a trustworthy
label-free semantic boundary detector. Do not implement or deploy such a detector
from a three-family, reference-informed review. The independent approximately
24-family holdout remains reserved and uncreated.
