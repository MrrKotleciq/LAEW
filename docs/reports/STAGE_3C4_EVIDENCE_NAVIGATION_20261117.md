# Evidence Navigation: Offline Development Trial and Live Decision

17 November 2026. Evaluation-only work on the existing exposed twenty-family
development benchmark. Production A and all historical research inputs remain
unchanged. No inference, catalog request, embedding, API-key use or deployment.

**Decision: stop at the offline investment gate.** Section navigation reaches
8/16 registered-complete packets versus the strongest static control's 6/16:
+2 net, below the prespecified +3 requirement. This is not a measured answer-quality
gain. Keep A; build no dedicated runtime adapter and execute zero live requests.

External reproducible package:
`C:\Users\korne\.codex\visualizations\2026\11\17\01a1ea8e-9496-7262-afbb-408b7fb44636\evidence-navigation-v1`.

## Verified architecture

The application already supports native tool-operated reading. `OpenAIProvider`
has `native_tools=True`, serializes completed function calls/results and uses the
`laew` namespace for ChatGPT (`laew/llm/cloud.py:11,45-86`).
`ResponsesTransport.stream` sends `store=false` and exposes native function output
when tools are enabled (`laew/cloud_chat.py:119-194`). The shared executor validates
and dispatches native calls (`laew/agent/executor.py:794-877`). This is the reuse
path; a second authentication or general document-agent framework is unnecessary.

The historical answer pilot does not test this behavior: it registers no tools,
uses one iteration, rejects function outputs, and permits one HTTP dispatch
(`laew/eval/real_world_live_pilot.py:199-306`). Its durable ledger and terminal
server-model checks are reusable concepts, but its 36-attempt schema and one-shot
transport cannot be silently reused for a multi-turn trial.

Dense retrieval uses Chroma and source mappings in frozen research traces.
Production ingestion applies file allowlists/exclusions and freshness fingerprints;
these do not establish immutable upstream edition ownership (`knowledge_base.py:
351-355,461-577`, `runtime.py:359-415`). The broker controls per-turn project/global
scope (`knowledge/routing.py:723,1014`). The historical two-document opportunity is
an accessibility ceiling, not measured reader quality.

Filesystem tools already provide literal/regex grep, filename discovery and
bounded line reads. Default `view_file` reads the whole file and returns a current
file hash; grep recursively returns matching lines (`tools/filesystem.py:323-384,
503-612`). PathResolver constrains aliases and denied components, but corpus
restricted-region masks are absent from these operations. A readable excluded file
or restricted part of an otherwise permitted manual must not be exposed through
the unmodified filesystem route. The offline common projection emulates existing
read/search semantics with additional corpus-specific controls; it does not
certify the unchanged runtime as safe for this frozen corpus.

## Frozen study and security boundary

The input manifest authenticates 24 normalized source snapshots, twenty existing
questions, B/C routes and all ten restriction records. Sorted family IDs receive
EN/PL/DE cyclically (7/7/6); no new questions or holdout are used. There are sixteen
answerable and four insufficient/unavailable families. Private original IDs are
removed from navigator views. The C/K10 first-two-distinct-source route is primary;
B static controls report sensitivity. Source text copies stay outside Git/Obsidian.

Comparators are the immutable historical static reference, a larger deterministic
static read with automatic extraction, a separate agent's extract from the same
static material, ordinary grep/range reading, and structural headings/section
reading. Every new reading condition starts with identical source-faithful safe
retrieved excerpts, capped at 1,000 estimated initial tokens. The source menu is
charged separately. Each interactive condition permits three operations and
4,000 cumulative inspected tokens; final packets have a separate 1,000-token cap.
Both line and code-point range reads are available in ordinary navigation.
Static expansion alternates the two routed sources at each expansion radius and
uses only unrestricted source-native headings as boundaries. No question labels
or question text guide static packing.

The common evaluation-only module is `laew/eval/evidence_navigation.py`. Every
access checks the source allowlist, global ownership, immutable normalized hash,
LF/code-point coordinates and restriction intervals. Menus carry source ID,
revision, hash and product/version applicability. Restricted text is removed
before heading discovery, grep and reading. Noncontiguous pieces are independent
segments with exact offsets and explicit omissions. Stale or uncertain source
resolution fails closed. Final packets can cite only the union of inspected
source intervals. The trusted external session state is not a hostile-process
authorization boundary: its limits/allowlists must be pinned by orchestration,
and rollback protection would be required before a live runner.

Sol High's precollection review reproduced an atomicity defect: a failed budget
check could leave a ghost inspected span. It also found raw restricted heading
use in static expansion, unfair source ordering, and operation/error-accounting
differences. All were corrected before collection. A regression test proves that
an unsuccessful response cannot authorize an unshown final range. Read-line errors
consume exactly one operation. Error outputs are retained in the separate audit
stream and added during scoring; no hidden navigation retries are allowed.

Independent clean-context Sol Medium agents navigate grep and section conditions;
a third agent extracts from static material. They see questions and allowed tool
results, never rubric, proof atoms, oracle witnesses, old answers or outcomes.
Packets are sealed before a separate scorer opens rubric v2.1. These are Codex
agent navigation observations, not GPT-5.6 Luna behavior or human validation.
Three minutes is the per-case target; overruns/failures remain in the denominator.

The registered investment rule remains >=3 net complete adequately sourced
answerable families over the stronger static control, gains in >=2 technical
domains, no new critical errors/exposures, and suitable treatment of all four
insufficient families. A dedicated structural interface additionally needs >=2 net
families over existing operations. Unresolved semantic judgments count against go.
All 329 uninspected High findings and inherited P03/S12 disputes remain open.

## Collection, decision and live gate

**Stop this navigation investment at the registered budget. Do not build a
dedicated runtime adapter or launch live inference from this result.** The stronger
static control is the independent agent extract from larger fixed material.
Structural navigation improves its registered completeness proxy by only **two
families net**, below the required three. Ordinary operations lose one family net.

| Condition | Complete registered evidence /16 | Net vs static editor | Median inspected tokens | Median final packet tokens |
|---|---:|---:|---:|---:|
| Historical B | 4 | — | 932 | 932 |
| Historical C | 4 | — | 944.5 | 944.5 |
| Larger static B, automatic extract | 4 | — | 3,858 | 998.5 |
| Larger static C, automatic extract | 3 | — | 3,830.5 | 982 |
| Larger static C, separate agent extract | 6 | 0 | 3,830.5 | 394 |
| Ordinary grep/range navigation C | 5 | -1 | 1,898.5 | 531.5 |
| Structural navigation C | 8 | +2 | 2,018 | 577 |

These are sixteen dependent-family representatives, not forty-eight independent
translation trials, answer-quality percentages, or deployment effectiveness.
Structural gains over static/editor are S05, S09 and S12; the loss is S06. Gains
span Prusa and PostgreSQL but do not meet the net-count criterion. Structural
navigation gains three over ordinary navigation, clearing its *secondary*
incremental count while failing the primary investment gate. Against only the
weaker historical C static reference it gains four; omitting the stronger control
would produce the wrong development decision. B sensitivity does not change this.

All sixty agent sessions were retained, with 59 final packets. Section/P03 has a
rejected final and no replacement. Ordinary/S12 retried a rejected finish: its
eventual partial packet is preserved but invalid for the gate. Ordinary P03 and
S16 plus section S16 retain failed reads. Five errors in total are logged; no new
reading or evidence repair followed a failure. No case exceeded the three-minute
target. Error costs are included; successful/failure rows and exact timing are in
`scoring/rows.csv`. All 629 inspected source exposures replayed exactly, with
zero declared restricted-region exposure, source drift or scope escape.

Targeted post-result agent review supplements the automatic scorer; see
`SEMANTIC_REVIEW.md`. It checks all dispositions and selected technical packets,
including the three gains, S06 loss, P01 regression and version comparison. It
does not independently certify every packet. Table identity clipping, incomplete
sentences, P03/S12 scope disputes and missing conditions remain explicit. The
registered counts are optimistic proxies for adequately sourced semantic success.
No new confirmed critical falsehood was found in the reviewed excerpts, but
exhaustive semantic safety is not established. Unresolved disputes count against
go; they are not waived to improve the result.

All three readers appropriately qualify the four insufficient/unavailable families:
P04 asks for server major version, S14 withholds an exact unestablished torque,
S15 asks for remote/source/destination details, and S16 withholds unavailable
graphical position/symbol claims. These are packet dispositions, not validated
GPT-5.6 Luna refusals or clarification behavior. S07's inapplicable document route
remains an answerable-case failure, not a successful refusal.

This is a provisional negative development decision for this budget, route and
agent reader. It neither disproves broader document reading nor demonstrates how
GPT-5.6 Luna would behave. In particular final packets can lose useful already-read
conditions; additional evidence accessibility is distinct from delivered grounding.
There was no second tuning cycle, no stage-3 runtime adapter and no live test.

## Exact conditional OAuth protocol

The v2 protocol, original questions, instructions, settings, source-bearing design
fixtures, order and hashes are frozen in external `live-proposal-v2/`. It is
**conditional, not authorized and not execution-ready**. Recommended requests now:
**zero**. It includes the required historical production-A service reference,
alongside causal controls for the common C seed. V1 is preserved as an earlier
three-condition design; V2 adds the production-A reference to avoid confusing a
C-starting-context reading comparison with a production improvement.

| Planned condition | Independent answer sessions | Maximum OAuth POSTs |
|---|---:|---:|
| P: exact historical A context plus model-visible source registry | 20 | 20 |
| A: common safe C historical-selection projection, no tools | 20 | 20 |
| L: larger static C material, no tools | 20 | 20 |
| B: same C starting projection with guarded existing grep/view operations | 20 | 80 |
| Total, only if separately justified and authorized | 80 | 140 |

All use exactly `chatgpt/gpt-5.6-luna`, existing LAEW OAuth provider integration,
fresh executor/conversation, the same engineering instructions and original
question wording. No API-key route or alternate model. Tool sessions allow three
tool calls and at most four POSTs, including the final answer turn. Early final
answers leave request slots unused. No forced continuations, warmups, catalog
probes, replacement attempts, retries or extra questions. Each dispatch requires
an independent durable reservation. Every uncertain dispatch stops the experiment.

Planning estimates under chars/4: **166,871 initial input tokens** across eighty
sessions; up to approximately **752,870 cumulative input tokens** in a conservative
four-turn replay estimate; **24,000–72,000 final-answer output tokens**, plus tool
call text and reasoning. These estimates exclude unknown wire/encrypted-history
overhead. The proposed receive guards are 12,000 input and 4,096 output tokens per
POST, with a 90-minute experiment ceiling. They stop subsequent requests after a
completed oversized response; they are not hard server-generation cost caps.
Neither ChatGPT plan percentage nor actual latency is predicted. Store=false;
temperature, top-p, seed and reasoning effort remain omitted equally across arms.

The provider registration and requested model can be checked locally before
dispatch. Actual remote availability was **not probed**. The first separately
approved POST would require the terminal server alias exactly `gpt-5.6-luna`,
consistent usage and response identity; rejection, absence, alias change or model
unavailability stops without fallback. Adapter echo is not server verification.

The current one-shot guard cannot execute this design. Only after a justified
decision would an evaluation-only multi-turn guard reuse the existing provider,
executor, broker and restricted source projection, with per-POST accounting and
mock SSE/restart/concurrency/crash tests. Source-owner review must accept visible
applicability and historical passage continuity before any transmission. The
original A bodies are unchanged and have no declared restricted intersections on
this subset, but the appended registry deliberately changes the old prompt.
Do not call this a bit-identical historical pilot replication.

Every tool operation would log exact source ranges, transcript and cumulative
reading cost. Every POST would log payload hash, request/response IDs where
available, terminal model, input/output/cache/reasoning usage and latency. Failed,
uncertain or insufficient cases remain in denominators. Manual quote-bound review
would assess technical correctness, completeness, grounding/citations, activated
warnings/prerequisites, versions, unsupported additions and appropriate uncertainty;
tool efficiency, aggregate tokens and latency would be reported separately.
Scoring/review artifacts must remain outside generator inputs. No automatic
registered-proof score alone may determine the live answer winner.

## Architecture recommendation and conditional rollout

Keep production A. Retain the existing filesystem capability for its authorized
product purposes, but do not promote it as safe navigation over this restricted
corpus without the missing range-level enforcement. Do not invest in a dedicated
structural interface from this result, and do not promote larger static context
from an agent-extraction advantage. No practical answer improvement was measured.
This bounded trial provides a stopping point for the optimization phase.

If a later separately approved live study establishes meaningful end-to-end gains,
prepare opt-in manual reading behind a default-off feature flag, reuse routing and
the broker, bind scope/source/revision/ranges at every read, and invalidate stale
handles. Keep production defaults and existing indexes unchanged during an
evaluation/canary phase. Rollback disables the flag and removes only experimental
tool registration; no corpus/index migration is needed for this design. Deployment,
representative user-task validation and rollback execution require separate
authorization. No holdout is consumed or specified here.

## Verification and preservation

Existing filesystem, path resolution, routing and native-provider integration:
257 passed, one skipped (optional actual-browser test) in the isolated runner. New evaluation projection:
11 passed in the isolated runner. Tests use synthetic/mock providers; they neither
verify remote model availability nor spend OAuth inference. `git diff --check`
passed. The initial checkout was `dd5886e620d83fd8109fbe47fd929667b1986701` on
`codex/rag-development`, with 24 preexisting dirty files recorded by hash.
No Git staging, commit, push, reset or clean was performed.
Final byte checks confirm all 24 preexisting files, HEAD and Git index are unchanged.
Only this report, the new offline module and its test file were added by this task.

| Integrity anchor | SHA-256 |
|---|---|
| Frozen inputs manifest | `b5691656c77eccc1d8c2cdf0bf54474c72e5435ed46fd05cd76706b5f1abf293` |
| Pre-scoring packet/scorer seal | `6b46ce97e09ebd3a3ba1396e57b957f3b32581d740827e0e3289f89f64626b4e` |
| Conditional live protocol v2 manifest | `17da32b31fcdee3615e15dd46c01bcfa4abd830c3803fedb75a7f7772e5ac1e1` |

`artifact-integrity.json` in the external package seals the final reports, scripts,
snapshots, input contracts, raw collections, audits, scores and conditional plans.
The package README identifies the canonical v2 protocol and replay commands.

Delegation: Luna 6 Medium performed runtime inventory and input freeze; Terra 6.1
Medium inspected provider/evaluation infrastructure and implemented the common
offline harness/tests; Sol 6.1 High reviewed access security/fairness; separate
Sol 6.1 Medium navigators collected blind packets. At most two subagents ran
concurrently and no delegated agent spawned children. Initial direct pytest
validation was subsequently repeated through the required isolated runner.
The user's later delegation correction prohibits further Sol Medium subagents;
all three completed navigation tasks are retained without restarting. Remaining
integration, decisions and verification were performed by the coordinator. The
external delegation record distinguishes explicitly configured accepted model
assignments from unavailable service-level model introspection.
