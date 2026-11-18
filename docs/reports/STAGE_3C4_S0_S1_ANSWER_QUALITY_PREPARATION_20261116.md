---
title: Stage 3C.4 — S0/S1 paired answer-quality validation preparation
date: 2026-11-16
status: offline-prepared-source-owner-review-and-live-authorization-pending
scope: existing exposed development questions and frozen B/C contexts only
---

# Readiness and decision

The offline experiment package is prepared and mock-tested: **12 questions,
24 identical question/arm pairs, 48 proposed GPT-5.6 Luna attempts**. No live
request, warmup, inference probe, model catalog request, retrieval rerun,
embedding, judge or production change occurred.

**Live execution is not yet approved or ready to launch.** Exact source revisions
and applicability remain external to the prompt, and historical internal passage
continuity remains ambiguous. Source-owner acceptance of all 24 selected contexts
and explicit new user authorization are required. Neither gate is marked passed.
Do not repair ambiguities by adding source text or changing S1. This is exposed
development evaluation preparation, not independent validation or deployment.

External versioned package, outside Git and Obsidian:

`C:\Users\korne\.codex\visualizations\2026\11\16\01a1e54d-b062-7051-b312-13db5172bf29\laew-s0-s1-quality-v1`

# Historical integrity and model-visible attribution

Inspected the fixed-body report and its FUTURE_QUALITY_PROTOCOL, the boundary
audit/specification, the original Luna pilot and repaired-scorer adjudication
reports. Verified 17 manifest/receipt entries, including parent serialization,
frozen input contracts, preceding studies, 777 corpus files (774 copies), saved
retrieval/traces, sanitized questions, datasets, rubric/calibration and historical
live/evaluation packages. Saved answers were hash-checked as manifest members,
not read as answer content. Existing source restrictions and judgments stand.

All **120 B/C contexts**, **441 passages** and **313,599 selected body characters**
were checked against saved S0/S1 serializations and immutable source contracts.
There are zero changed bodies, selected IDs, order, ranges, ownership bindings,
source revisions or candidate identities. Only tags/backlinks rendering differs.
The original scope/global wrapper is retained. No evidence is added using savings.

S1 preserves the rendered document filename, section label/path, GLOBAL KNOWLEDGE
ownership, @knowledge alias, type/status, fragment separators, source citation
labels and every selected condition/warning character. It does not supply a
complete model-visible registry of immutable source IDs, revisions, hashes,
full applicability or source offsets. Full document titles need not occur in
the attribution; the visible filename is not a complete source identity.
Preserving a sidecar cannot prove the model understands version applicability.

| Risk | Original contexts affected | Model-visible limitation |
|---|---:|---|
| R01 | 120 | Exact immutable revision/hash/applicability are sidecar-only |
| R02 | 0 | No observed same-filename/different-revision collision; existing S1 rejects such a fixture |
| R03 | 17 | Several PostgreSQL major versions delivered together |
| R04 | 60 | Every C context contains structure-v2 multi-range or synthetic related-context material |
| R05 | 60 | Prusa handbook revision and full hardware/firmware applicability absent from attribution |
| R06 | 96 | Removed navigation identifiers may still influence interpretation |
| R07 | 61 | Different passages share filename/section locators without exact inline offsets |
| R08 | 4 | Existing restricted-region intersections, unchanged and ineligible for positive proof credit |
| R09 | 0 | No primary historical clipping observed; clipping guard retained |
| R10 | 6 | P04 deliberately lacks the target major version |
| R11 | 37 | Several Prusa products delivered together |
| R12 | 30 | Pro Git translations have distinct commits, not synchronized revisions |

Counts are contexts, not doubled format rows. R03 affects exactly P03-de,
P04-de/en/pl, S04-de/en/pl, S12-de/en and S13-de/en (exact B/C cells in JSON).
R08 affects P02-en and S16-de/en. All 60 question IDs are explicitly enumerated
for every applicable risk in `provenance-risk-register.json` and
`PROVENANCE_AUDIT.md`; `provenance-audit.json` records both visible attribution
strings and separate external fields for every passage.

There are 149 primary passages with multiple mapped source ranges. Keeping their
synthetic labels and related context preserves the historical body but does not
certify continuous source prose or consecutive procedural steps. The PostgreSQL
17 archiving snapshot (REL_17_10) and WAL snapshot (REL_17_STABLE at its pinned
commit) remain different source revisions despite the same major-version hint.
Missing warnings outside delivered bodies stay missing. P03/S12 scope disputes,
all ten restrictions and the 329 uninspected High findings remain unresolved.

# Frozen subset and paired controls

Fixed input-hazard slots select these twelve families, then ascending family IDs
receive DE/EN/PL cyclically. Original wording is copied from sanitized questions.
No saved answer, expected S1 success or scoring outcome determines a slot.
Historical reports have been read, so selection is explicitly exposed development
design, not blind preregistration or a new holdout.

| Original ID | Main input-based rationale |
|---|---|
| P01-de | Small Git metadata saving, identity/precedence, multilingual sources |
| P02-en | Same-type sheet replacement, conditional prerequisites and incomplete evidence |
| P03-pl | High PostgreSQL metadata overhead, backup dependencies and retention |
| P04-de | Unknown server version and conditional recovery startup warning |
| S04-en | High PostgreSQL savings, soft limit and archive-failure condition |
| S06-pl | Multi-section firmware procedure, upgraded-model applicability and rollback |
| S10-de | Zero-saving Git control and submodule-publication prerequisite |
| S11-en | Multi-document/two-device firmware paths and disconnection warnings |
| S12-pl | PostgreSQL 11-to-17 API/session/returned-metadata migration |
| S13-de | PostgreSQL 11/17 timeline defaults and valid descendants |
| S14-en | Exact torque unavailable; uncertainty instead of an invented number |
| S16-pl | Graphical evidence unavailable; position/symbol cannot be reconstructed |

Every question uses B and C, each with S0 and S1: 48 attempts without retries.
There are four questions in each language. Alternate B-first/C-first blocks and
format order within each arm; S0 and S1 each run first in 12 pairs, six per arm.
Pair members are adjacent. Selection and order are deterministic and documented.

The exact historical generation prompt/settings are frozen, with no rubric or
review facts in transmitted payloads. Every request uses a fresh empty executor,
one original user message, no history/previous-response reference, no tools,
memory or project context, and store=false. The original 300-word guideline and
omitted provider defaults for temperature, seed, top-p, reasoning effort and
max_output_tokens remain omitted; deterministic sampling is not claimed.

# Execution guard and evaluation

The evaluation-only runner uses one fixed SQLite ledger, FULL synchronization,
transactional reservation before dispatch, a 48-attempt hard cap, schedule and
canonical payload hashes, unique question/arm/format identities, exact order,
zero adapter retries and no redirects. An uncertain or failed request blocks
all subsequent dispatches, including after restart. A completed prefix resumes
only at the next request. Crash-after-completion-before-save remains uncertain;
no automatic replacement is permitted. This is local at-most-once dispatch.

Requested provider/model and terminal server alias must be exactly
chatgpt/gpt-5.6-luna. Registration is pinned. Model mismatch/change, missing or
inconsistent usage, unexpected tools/refusal, auth/rate/transport errors,
timeouts and the 90-minute wall ceiling fail closed. Response/HTTP request IDs,
token counters and latency are retained without credentials/raw reasoning.
Missing HTTP IDs stay null. A receive guard of 12,000 input/4,096 output tokens
stops further calls; it is not a hard generation limit for the completed call.
No immutable server snapshot beyond the alias is asserted.

`run_authorized` has no live CLI and requires a separate scoped authorization
object plus source-owner acceptance. Preparation does not access credentials or
perform provider preflight. Mock tests intercept Requests and block sockets.
The initially empty ledger has zero reservations and is preserved at a fixed
package path for any later separately authorized run.

Evaluation uses unchanged rubric v2.1 and repaired applicability scorer
`47bbe6152657c336b1d319739569cf4585dc9c3c0f01a6fe8dd8fc0ef30e3d2c`.
The generator manifest is sealed before rubric material is loaded into a separate
review-only directory. All nine requested dimensions, explicit condition
activation, quote-bound exhaustive claims, restricted-region subtraction,
citations and paired gains/regressions are specified in EVALUATION_PROTOCOL.md.

Correct-but-ungrounded claims, missing evidence, generation omissions, citation
errors, activated safeguard omissions and unresolved scope are separate fields.
The strict scorer still leaves unregistered substantive additions unresolved;
overview ratings cannot convert them into automatic verified claims. No semantic
judge is added. Failure/uncertainty denominators and all pairs are retained.

The blank local HTML/JSON manual form uses Pair-XX and X/Y. The curator key is
outside the HTML; exact contexts and rubric criteria are review-only. Context
length/navigation may reveal the format, so this is label blinding only. Reviewer
identity, human/agent origin, expertise and prior exposure must be recorded.
Neither an independent reviewer nor independent validation is claimed here.

# Workload, artifacts and verification

Proposed future workload: **48 attempts**, about **59,034 input text tokens**
(S0 31,310; S1 27,724) and **14,400–43,200 output tokens** as a planning range.
The paired input saving is about 3,586 estimated tokens. Combined planning range:
about 73,434–102,234 tokens. Reasoning is included in output. Estimates use the
historical chars/4 convention, exclude unknown protocol overhead and are not a
model tokenizer or a precise ChatGPT plan-percentage prediction.

Exact requests and settings are under generator-only; review-only contains the
original rubric, source atoms, 24 source units, restrictions and blank forms.
README, EVALUATION_PROTOCOL, REPRODUCE.ps1, subset/cost/audit tables, code snapshots,
runtime pins, manifest receipts and logs make the package reviewable offline.
The mutable future ledger is excluded from immutable file-member sealing; its
initial empty hash is separately recorded. All other package members are sealed
by artifact-integrity.json.

Generator manifest SHA-256:
`60d9310f935e80b7dbde14c5a02c3e220b7d55d627d9e1011b7a2e0f896e4217`.
Exact requests.json SHA-256:
`ca1008e5644cfec1d1c97586988218e3746e1af4b1c603b0f59365fa35f7685f`.

**147 tests passed, zero skipped**, through scripts/run_isolated.py. Coverage
includes all frozen contexts/body/range identities, exact paired payloads and
isolation, no rubric leakage, counterbalancing, persistent caps, durable
reservation visible from another connection, concurrent/restart/crash handling,
no hidden retries or forced continuation, model/usage errors, answer-review
binding and artifact tampering. Syntax and git diff --check also passed.

The initial broad run found one overly broad blinding assertion (S04 was mistaken
for the S0 treatment label), corrected in the new test, and a preexisting
30-ms timeout-test race. The historical test now cancels deterministically after
its first delivered delta; no historical runner or production behavior changed.
Original frozen test copies remain untouched. Failure logs are retained.

This task adds four repository files: this report, serialization_quality_runner.py,
serialization_quality_study.py and test_serialization_quality.py. It also modifies
only the deterministic timeout fixture in test_real_world_live_pilot.py. All
**17 preexisting changed/untracked files**, including docs/README.md, retain their
original hashes; Git HEAD and index are unchanged. Final status and exact receipts
are in the external package. No Git add, commit, push, reset or clean ran.

The requested pause was observed when the 5-hour window reached 2% remaining;
work resumed after the account window reset. No reset credit was consumed.

**Hard stop:** offline preparation is complete. Do not launch Luna until a source
owner accepts model-visible attribution and the user separately authorizes the
exact controlled 48-attempt experiment.
