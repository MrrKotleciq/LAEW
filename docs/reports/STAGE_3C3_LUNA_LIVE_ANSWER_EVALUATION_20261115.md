---
title: Stage 3C.3 — Luna frozen-context live answer pilot
date: 2026-11-15
status: completed-provisional-agent-review-human-adjudication-pending
scope: 36 authorized attempts; 12 pilot questions; original A/B/C only
---

# Result and development decision

Better delivered evidence helped selected answers, but higher retrieval recall
did not produce uniformly more reliable answers. **B is the preferred next
development baseline**, with C retained as a challenger. B produced the most
correct, minimally complete, fully context-grounded answers in this sample:
**A/B/C = 3/12, 5/12, 4/12**. C produced more minimally complete answers, but
additional unsupported claims prevented that lead from becoming a grounding
lead. Keep production A unchanged.

These are provisional, non-blind **agent_review** judgments under the unchanged
v2.1 rubric, not independent human validation. Four shared intent families with
three language variants support descriptive paired observations only. No
statistical significance, population superiority or deployment conclusion is
claimed. One response per question/arm cannot isolate sampling variability.

# Execution and integrity

Executed exactly **36 Responses POST attempts**, all completed, with zero
retries, failures, excluded answers, warmups, inference probes or judge calls.
The window was **18:09:16.662–18:16:17.599 UTC** on 2026-11-15
(19:09–19:16 Europe/Warsaw), lasting **420.936 seconds**. The existing LAEW
ChatGPT OAuth registration pseudonym was `d8011d147da35092`. All 36 terminal
server events reported `gpt-5.6-luna`; the server supplied no separate immutable
snapshot identifier. Catalog access was checked non-generatively before
preparation and again immediately before execution. No other provider or API
key fallback was used.

The persistent SQLite guard commits a unique question/arm reservation with
`synchronous=FULL` before dispatch. It enforces 36 total reservations, original
sequence, no outstanding uncertain request, no repeated transport dispatch and
an experiment-wide stop. Interrupted reservations cannot be reused. HTTP
adapter retries are explicitly zero; redirects, continuations and forced-final
requests are blocked at the POST boundary. A 120-second cancellation watchdog
also respects the remaining 90-minute experiment ceiling. Auth, usage, model,
integrity, refusal, tool and transport failures stop subsequent requests.
The ledger is now closed with `PILOT_COMPLETE_NO_FURTHER_GENERATION`.

Each request used a fresh executor, empty history, no tools/workers, no project
scope, and the original question/context. Actual serialization was checked
against the original first-dispatch payload before reservation. Gold labels,
reference facts, review notes and scorer state were not generator inputs.
The six predeclared arm orders were repeated twice; each arm occupied each
execution position four times.

Verified before generation: 777 corpus files; pilot v4's 16 manifest members;
sealed v3's 10 members for preservation only; 201 historical retrieval members;
66 audit members; 47 calibration members; 41 rejected-delivery experiment
members; original generator/trace manifests; 112 source/version-bound atoms
across 24 source units; pinned runtime, builder and scorer code. All **36
original payloads were reproduced exactly offline**. No D1 context was used.
Trust anchors and individual verification receipts are in the external package.
No embedding, index rebuild, retrieval run, model download or service restart
was required or performed.

Generation retained the frozen stream/store/tools/include settings. Temperature,
seed, top-p, reasoning effort and output-token limits were omitted and therefore
provider defaults; they were not silently fixed or claimed reproducible. The
300-word target remained a prompt guideline. Recorded whitespace word counts
range from 58 to 243, median 120. Encrypted reasoning, credentials and raw
protocol/header dumps were not stored.

# Provisional answer quality

All denominators below are **12 completed answers per arm**. “Fully grounded”
means every substantive assertion has delivered support; an answer may satisfy
that property while remaining incomplete. Correctness alone does not imply
grounding, and partial requirements do not count as complete facts.

| Answer-level endpoint | A | B | C |
|---|---:|---:|---:|
| No identified technical error or unresolved factual assertion | 10/12 | 11/12 | 11/12 |
| Correct and minimally complete, including applicable conditions | 4/12 | 5/12 | 6/12 |
| All substantive assertions context-grounded | 7/12 | 9/12 | 8/12 |
| Correct, minimally complete and fully grounded | 3/12 | 5/12 | 4/12 |
| At least one unsupported assertion | 5/12 (41.7%) | 3/12 (25.0%) | 4/12 (33.3%) |
| Contradicted or overgeneralized procedure assertion | 1/12 (8.3%) | 1/12 (8.3%) | 1/12 (8.3%) |
| Additional unresolved factual assertion | 1/12 | 0/12 | 0/12 |
| Missing at least one applicable critical requirement | 8/12 | 7/12 | 6/12 |
| Missing an answer-triggered conditional safety requirement | 4/12 | 3/12 | 1/12 |

The operational hallucination/error indicator is the contradicted or
overgeneralized assertion row; it does not count every unsupported but true
claim as false. Citation fabrication is reported separately. Missing critical
requirements include missing requested evidence in appropriately cautious
partial answers; **8/7/6 is not a count of unsafe instructions**. The
answer-triggered row isolates conditional obligations activated by the advice
actually given. Source gaps and generation omissions remain separately visible.

The three overgeneralization cases are P02-pl in A/B/C. A/B extend available
initial-preparation or accessory information into an unconditional replacement
procedure; C extends a different-sheet-type rule to every same-type replacement.
All need review of the precise necessity/scope boundary. P03-pl/A includes
additional categorical claims that the frozen evidence cannot adjudicate;
these are labeled unresolved, not asserted to be conclusively false.

Citation-group entailment/locator checks were **11/18, 30/34, 24/28** for A/B/C.
One B answer contains a fabricated filename/heading combination; another C
answer cites a delivered heading that does not entail the associated claim.
Other failed groups mix supported text with unsupported scope/range claims.
These are provisional group-level checks, not independent citation precision
measurements or atomic-claim incidence estimates. Uncited inspection commands
in three P01 answers are technically valid but not supported by their actual
delivered passages. Correct core answers are therefore not automatically fully
grounded.

Reviewed citation coverage is complete in 8/12 A, 11/12 B and 9/12 C answers.
The remaining answers contain material assertion groups without an associated
citation. This is a disclosed group-level reviewer rating, not an automatically
measured fraction of all atomic propositions. Citation presence does not make
an unsupported claim entailed.

# Paired and stratified observations

Wins/ties/losses below compare the **new arm to the preceding arm**, paired
within the same 12 questions. No questions were dropped.

| Endpoint | A → B | B → C |
|---|---:|---:|
| Correct and minimally complete | 1 / 11 / 0 | 1 / 11 / 0 |
| All assertions grounded | 2 / 10 / 0 | 2 / 7 / 3 |
| Correct, complete and grounded | 2 / 10 / 0 | 1 / 9 / 2 |

For the final endpoint, A→B gains are P01-de and P04-de. B→C gains P04-en,
but loses P01-en/pl because of unsupported additional inspection instructions.
The C gains are therefore not a uniform reliability improvement. The complete
paired requirement/condition log includes every newly missing critical
requirement, rather than hiding changes behind aggregate omission counts.

| Family | Correct + minimally complete A/B/C | Main observation |
|---|---|---|
| P01 | 3 / 3 / 3 | Sufficient original identity context already supports all core answers. Optional additions and citation errors create grounding regressions. |
| P02 | 0 / 0 / 0 | C supplies useful partial MINI+ evidence, especially in EN/DE, but no arm supplies or answers the complete safe minimum. Other-product context is often correctly bounded. |
| P03 | 0 / 0 / 0 | Incomplete context prevents a complete dependency/retention/restore answer. Some answers abstain appropriately; P03-pl/A supplies substantial correct-looking material without delivered proof. |
| P04 | 1 / 2 / 3 | All nine request the actual major version and avoid unconditional file creation. Three answers omit an applicable startup warning after providing the newer-version procedure. A/pl instead gives a bounded older-version explanation plus clarification. |

Every P02/P03 answer remains in the result set. Safe partial answering can be
correct evidence behavior while full-task completeness is zero. P04 has
positive technical retrieval recall N/A but is included in answer quality.
One valid clarification solution suffices; all version alternatives are not
mandatory. Giving an optional procedure activates its applicable warnings.

| Answer language | Correct + complete A/B/C, out of 4 | Fully grounded A/B/C, out of 4 |
|---|---|---|
| EN | 1 / 1 / 2 | 3 / 4 / 2 |
| PL | 2 / 2 / 2 | 2 / 2 / 2 |
| DE | 1 / 2 / 2 | 2 / 3 / 4 |

All 36 answers follow the requested response language. Evidence language is not
the answer language: the relevant P02 C passages are Polish, P03/P04 evidence
is English, and P01 mixes identity editions. The same exposed agent assessed
cross-language equivalence. These small, family-dependent strata do not show a
language-wide model ranking. Clarity/conciseness ratings and reasons are retained
per answer; off-target context sometimes leads to unnecessary discussion.

# Retrieval versus generation

The previous pilot's original selected recall was **13.0% / 14.8% / 13.0%**;
calibrated minimum-evidence coverage was **35.2% / 37.0% / 46.3%**.
Calibrated complete selected contexts remained **3/9 in every arm**, all P01.
These reference-coverage definitions differ from each other and from generated
answer endpoints; their percentages must not be treated as interchangeable.

The live results show a practical gain from delivered complementary warning
evidence in specific P04 cases, and useful partial content in C/P02. They do
not show that higher aggregate recall guarantees a complete or more grounded
answer. All six P02/P03 language variants remain incomplete in every arm.
The historical B/P03-en candidate pool held substantially more evidence than
the delivered payload. More candidate recall cannot compensate for evidence
discarded during selection/rendering. Other cases still have candidate gaps
or wrong-product/version candidates. Larger contexts also deliver repeated
material, metadata/navigation and off-target procedures.

P03-pl/A is a clear separation between factual plausibility and grounding:
the answer supplies important facts found in the full frozen originals even
though the dispatched body provides essentially no supporting explanation.
This is **consistent with prior knowledge**, not proof of its causal source,
and it does not repair the grounding score. Generation also introduces
avoidable extras and omits conditions even when some useful context is present.

The main next engineering target is **context delivery that preserves
complementary requirements, applicability and warnings**, with retrieval
candidate gaps still tracked. This is a recommendation, not a new experiment
or authorization to implement another selector. Do not revive rejected D1.
First adjudicate this pilot's disputed annotations and scorer applicability;
then design a separately approved study with new intent families/holdout data.

# Usage and latency

| Recorded telemetry | A | B | C |
|---|---:|---:|---:|
| Input tokens | 9,974 | 16,071 | 16,790 |
| Output tokens | 6,095 | 6,219 | 6,071 |
| Total tokens | 16,069 | 22,290 | 22,861 |
| Reasoning tokens, included in output | 3,081 | 2,560 | 2,660 |
| Median latency, seconds | 7.61 | 10.52 | 9.32 |
| p95 latency, seconds | 26.45 | 19.89 | 21.53 |
| Maximum latency, seconds | 34.79 | 21.14 | 29.63 |

Total actual usage was **42,835 input + 18,385 output = 61,220 tokens**;
8,301 reasoning tokens are already included in output. Cached tokens were zero
as reported. Usage and response IDs are available for all 36 attempts.
The observed `x-request-id` header was absent in all 36 responses, so request
IDs remain null; response IDs are not relabeled HTTP request IDs. No immutable
snapshot was supplied beyond the requested alias. Latencies include the
attempt workflow; p95 uses inclusive linear interpolation over twelve cases.
Sequential timing and shared question families limit performance conclusions.

The user explicitly accepted unavailable ChatGPT plan-percentage measurement.
Before/after percentages and concurrent plan attribution remain unknown.
These token counts are neither an OAuth invoice nor a plan-percentage estimate.
No paid fallback, billing change or allowance increase was requested or used.

# Scoring limits and review package

The unchanged deterministic v2.1 source-proof scorer was used on all 36
contexts. Its answer scorer produced **25 conservative diagnostics** and
rejected **11 branch combinations** with `Chosen method contradicts reviewed
applicability`: P02-en/C, P03-en/A/B, and eight P04 comparison/procedure answers.
Existing method definitions set some scenario assumptions to false while those
answers activate the corresponding conditions. Neither rubric nor scorer was
changed after seeing answers. Actual conditions and requirement applicability
were recorded explicitly with agent provenance using the existing applicability
function; these conditional semantic results are not falsely presented as
fully automated accepted scorer results.

Conservative diagnostics also leave unregistered substantive additions
unresolved rather than classifying them as nontechnical to earn credit.
The semantic review retains a bound full-answer assertion group, explicit
exception quotes, requirement-level quotations/reasons, source/version atoms,
actually delivered source intersections, condition decisions, citation checks,
0/1/2 dimension ratings and reviewer exposure. It is not an independently
double-coded atomic-claim census. Supportability-adjusted completeness requires
adjudication; no independently certified supportability denominator is claimed.

The self-contained HTML package conceals A/B/C and retrieval scores, supplies
all 36 answers, exact contexts, frozen requirement definitions and source-bound
evidence, and exports local manual judgments. Agent drafts are hidden until
requested; revealing them records exposure. The blank human template does not
claim validation. The original pre-answer second-review reservation is preserved.
Domain/bilingual review and the specified second-review/adjudication remain
outstanding human work, not a condition silently waived as completed.

# Artifacts, reproduction and repository preservation

External private research package, outside Git and Obsidian:

`C:\Users\korne\.codex\visualizations\2026\11\15\01a1e05d-6573-7bf1-b706-6d9499db2672\laew-luna-live-v1`

- `attempts.sqlite3`, timestamped attempt history, `raw-answers/`,
  `raw-integrity.json`: all effective requests, answers, statuses and hashes.
- Integrity receipts, `execution-contract.json`, code snapshots,
  `provider-preflight.json`, live catalog receipt, `usage-acceptance.json`,
  `telemetry-summary.json`: identity, settings, dependencies and provenance.
- `evaluation-v3/`: authoritative provisional annotations, authored decisions,
  deterministic diagnostics, strata and paired question results. V1/V2 are retained
  as intermediate outputs with the same primary endpoint counts.
- `manual-review-v3/answer-review.html`: authoritative manual interface;
  `review-data.json` and `blank-human-review.json` provide portable alternatives.
  The earlier interface is retained as an intermediate version. Arm keys remain
  curator-only and are not embedded as arm labels in the manual interface.
- `review_agent.py`, `render_review.py`, validation receipts, test logs,
  final Git status and artifact manifest: offline reproducibility and audit.

Re-evaluate offline by running `review_agent.py <new-output-directory>` using
the repository venv. Re-render the frozen evaluation with
`render_review.py <new-manual-directory>`. Both require fresh output paths.
Do not rerun the live command: all authorized attempts are consumed and the
durable guard is stopped. Preserve raw hashes and pinned input artifacts.

**85 tests passed, zero skipped**, using `scripts/run_isolated.py`, including
22 new bounded-dispatch acceptance cases and existing dataset, payload, scorer
and rejected-delivery regressions. Initial historical pilot tests were pointed
at v4 rather than their v3 fixture; that setup error produced two failures,
was corrected without changing tests/data, and the final run passed. HTML/data
validation and script syntax checks are recorded separately.

Changed repository files: the new evaluation-only runner, its new synthetic
acceptance tests, this metadata-only report, and one additive documentation
index entry. All pre-existing non-index dirty/untracked files were hash-checked
unchanged; initial index content is preserved. No production RAG/configuration
or historical artifact was changed. No Git add, commit, push, reset or clean ran.

**Hard stop:** generation is complete. Do not deploy B/C, produce more answers,
start retrieval experiments or modify production from this result.
