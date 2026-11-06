# Retrieval reliability evaluation

Run the isolated, controlled checks with:

```powershell
.venv\Scripts\python.exe -m pytest tests/integration/test_conversation_reliability.py tests/integration/test_reliability_conversation_flow.py tests/integration/test_knowledge_routing.py -q -s --basetemp=<new-empty-test-directory>
```

The conversation fixture creates a temporary SQLite store and temporary Global and Project indexes. Its provider emits a fixed response. The printed source recall is the fraction of turns with a required source where that source actually ran. Evidence coverage is the fraction of those turns whose expected marker reached the provider. The unnecessary-retrieval denominator is the explicitly retrieval-free turn. These small numbers are regression probes, not representative population estimates. The diagnostic-derived timing is a sum of individual automatic retrieval durations, not end-to-end latency. Context tokens are estimates from diagnostics, not tokenizer measurements. Grounded answer rate cannot be computed from a fixed provider response.

Before the changes, the original knowledge-routing integration suite passed 119 tests with one skipped. The initial conversation probes passed two of six cases; three continuation variants and the prose-candidate case failed. These probes do not establish a baseline for the later six-turn evidence metrics. The existing Global RAG baseline is unchanged.

## Stage 2 first-person and intent routing

The previous classifier treated the normalized token `i` as sufficient evidence of first person in an education question. Profile and equipment lookups also bypassed the advice filter. A settled-date expression could trigger Memory without evidence of a personal or local operational event. The updated classifier uses English subject and verb constructions, Polish first-person inflections and possessives, and one advice check for implicit recall. Settled dates use event ownership and local or public cues. Explicit source requests and exclusions still use the Stage 1 policy. Short continuations use the existing topic binding.

The [36-case intent fixture](../tests/evaluation/routing_intent.json) is separate from the four existing datasets. Its labels were recorded before the router changes and inspected during implementation. Cases include Polish conjunctions, English first person, advice with a possessive, current and past employment, public schedules, personal handovers, short continuations, and explicit Memory, Global and Project restrictions. Run the same evaluator for each version of the router:

```powershell
.venv\Scripts\python.exe -m laew.eval.knowledge_routing_eval --output <result.json>
```

The evaluator runs the actual KnowledgeTurn and Chief executor with a fixed adapter, isolated SQLite and persistent Chroma indexes, and fixture embeddings. [Before](reports/routing-intent-stage2-before.json) and [after](reports/routing-intent-stage2-after.json) contain the fixture hashes, metrics, and per-case evidence observed at first adapter dispatch. The intent pytest case uses an ephemeral Chroma client to avoid the intermittent on-disk HNSW startup error observed in broader runs.

| Metric on the intent fixture | Before | After |
| --- | ---: | ---: |
| False Memory Routing Rate, Memory selected among turns without a Memory requirement | 12/22 | 0/22 |
| Memory Routing Recall, Memory selected among turns requiring it | 11/14 | 14/14 |
| Routing Precision, correct source selections / all selections | 16/51 | 20/33 |
| Missed Retrieval Rate, missing selections / required sources | 4/20 | 0/20 |
| Unnecessary Retrieval Rate, extra selections / all selections | 35/51 | 13/33 |
| Evidence Coverage, turns with all expected markers / scored turns | 15/19 | 19/19 |
| Actual backend searches | 39 | 33 |
| Mean routing time from per-turn diagnostics | 0.446 ms | 0.529 ms |

All four existing datasets retained their selection and evidence metrics across 96 turns. Evidence coverage remained 79/79 on those datasets. The four named regressions (`v20`, `v21`, `h11`, `h18`) still selected Memory first, supplied one Memory result and one Global excerpt each, and delivered their expected markers. The additional Global searches on Memory-only ground-truth cases come from the existing fallback assessment. Both evaluator runs used one fixed Chief dispatch per case and zero model assessment calls.

A separate timing probe called `resolve_turn` with the fixture questions, history and project flags. After five warm-up sweeps, the median per-turn cost across 11 samples of 30 sweeps was 0.2626 ms before and 0.2728 ms after. The sample ranges overlapped (0.2607–0.2707 ms and 0.2633–0.3037 ms).

The final focused suite passed 386 tests and skipped one browser test. A broader offline run during implementation passed 1,367 tests, failed 43 and had one setup error. The sandbox blocked loopback connections with WinError 10013, disposable Chroma servers failed to start, and two documentation assertions flagged stale test counts in `PROJECT_STATUS.md`.

Public/private classification depends on lexical and grammatical cues. A date question with no clear ownership or event type may need an explicit source request or a more informative topic anchor. The fixture measures routing and evidence delivery in a controlled environment. A fixed response cannot measure answer grounding.

## Stage 3 routing measurement accuracy

Run `.venv\Scripts\python.exe -m laew.eval.knowledge_routing_eval --output <result.json>` to reproduce the [version 2 report](reports/routing-accuracy-stage3.json). The report keeps the five dataset hashes and the original `metrics` and row fields. The additional `accuracy` fields use the definitions below. Historical reports remain valid under their original definitions.

| Measurement | Unit and denominator |
| --- | --- |
| Initial Routing | A source/turn pair selected before recall. Reads `memory_requested` and `initial_scopes`. |
| Final Source Selection | An automatically selected source/turn pair after escalation. Reads `memory_requested` and final `scopes`. Scripted model tool requests do not count as automatic selection. |
| Executed Retrieval | A source/turn pair with at least one completed backend search. Empty results count. Failed backend attempts, pipeline entry without a query and cached reuse without a query are recorded separately. Repeated completed queries count once in source precision and recall and individually in backend call counts. |
| Evidence Coverage | Cases that delivered every labeled atom divided by cases with at least one label. |
| Evidence Atom Coverage | Distinct labeled atoms delivered divided by all distinct labeled atoms across the cases. |

Source recall divides correctly observed pairs by the number of required pairs. Precision divides the same numerator by the number of observed pairs at that stage. All three source stages use the fixture's `required` sources, including sources expected only after escalation. A deferred source therefore lowers initial recall without implying a routing defect. A turn requiring no sources adds zero to the recall denominator and can still add a false-positive selection to the precision denominator. A zero denominator is reported as `[0, 0]`. The historical Memory Sufficiency labels require a Memory consultation and require Global when `needs_rag` is true. Availability and user exclusions are reflected in the labels and runtime diagnostics. The evaluator does not infer correctness from the presence or absence of a call.

The evaluator observes SQLite FTS and the Chroma search boundary in isolated fixtures. Metric regression tests use ephemeral Chroma clients. The standalone report and runtime integration tests use persistent indexes. The evaluator captures Memory candidates and RAG candidates that survive relevance filtering before deduplication and budget handling. It checks the prepared Memory JSON and RAG excerpts against the exact retrieval attachment in the captured adapter input, or the native tool observation with the matching call ID. Historical markers infer acceptable sources from the seeded content, with optional explicit `evidence_sources` overrides. RAG atoms must come from the current fixture's note in an acceptable scope. Marker matches in conversation, instructions, paths or metadata do not count. Coverage records delivery in any dispatch of the evaluated turn, with first-dispatch attribution separately available per atom. Each atom records where it was found, prepared and delivered. A required source with no completed search and all its labeled evidence already delivered is reported separately from unresolved source gaps. A fixed Chief response cannot measure answer quality or grounding.

The per-case Memory Recall, prefetch and follow-up fields reflect the same snapshot used by Sources/Run. Their counters describe runtime selection, dispatch and reuse. A single excerpt marked as supplied can still be truncated and contain only some expected atoms. The backend and atom measures verify those boundaries independently.

| Dataset | Initial R / P | Final R / P | Executed R / P | Case coverage | Atom coverage |
| --- | --- | --- | --- | ---: | ---: |
| validation | 24/40 · 24/24 | 40/40 · 40/46 | 38/40 · 38/44 | 22/22 | 22/22 |
| horizon_holdout | 18/29 · 18/18 | 29/29 · 29/35 | 28/29 · 28/34 | 17/17 | 17/17 |
| horizon_strategy_holdout | 18/30 · 18/18 | 30/30 · 30/35 | 29/30 · 29/34 | 18/18 | 18/18 |
| knowledge_routing | 26/32 · 26/26 | 32/32 · 32/41 | 29/32 · 29/38 | 22/22 | 24/24 |
| routing_intent | 20/20 · 20/20 | 20/20 · 20/33 | 20/20 · 20/33 | 19/19 | 20/20 |
| Evaluator controls | 7/9 · 7/7 | 7/9 · 7/7 | 7/9 · 7/7 | 4/8 | 6/10 |

Across the five existing datasets, legacy routing recall remains 132/132 cases, including turns with no required source. That legacy value uses final selection. The new initial measure is 106/151 required pairs, with 45 Global requirements selected later. Final selection covers 151/151 pairs. The seven missing backend completions were Memory recalls that found no active rows before running FTS. Existing evidence coverage remains 98/98 cases, and the new atom denominator is 101 because three cases have two labeled facts. The report's elapsed and retrieval times include observation overhead and ordinary runtime variation.

All legacy non-timing metrics and per-case source and evidence results match the Stage 2 report. Compared with the older `knowledge-routing-after.json` report, `r16` has 51 more context characters. Stage 1 added the instruction to ignore evidence from excluded sources in prior turns. The Stage 2 report already contains the same longer context.

The controls distinguish several cases with similar diagnostics. The budget-limited excerpt reports one supplied fragment, but delivers one of two atoms. An exact repeat reuses the prior outcome without a backend call, while a different query executes and then omits the duplicate fragment. The old full-system scan credits a scaffold mention in `c04`, and the old first-dispatch boundary misses the native tool result in `c08`. Those opposite errors leave the legacy case total at 4/8. An injected embedding error also demonstrates why pipeline entry does not establish that a backend ran.

The focused measurement and source-policy rerun passed 54 tests. The wider regression passed 427, skipped one browser test, and failed one persistent-index integration case with Chroma's `Error creating hnsw segment reader: Nothing found on disk`. The failed integration case passed on an isolated rerun.

## Prompt audit

The actual CLI and Workbench configurations do not load `prompts/chief-agent.md` as their system prompt. That file contains workflow and confirmation instructions and should not be mistaken for the effective runtime prompt. The executor builds tool instructions and appends knowledge and memory guidance. Source labels already distinguish automatic memory, global and project results; retrieved content is described as untrusted data. The new guidance explicitly treats active Memory as stored evidence and distinguishes a question from a user preference or plan. Existing tool descriptions describe scoped recall and RAG correctly. The executor's instruction to stop after acquiring sufficient information is conditional and does not prohibit further search when evidence is incomplete.

Using the repository's rough four-characters-per-token estimate, the non-native executor scaffold with no tools is about 540 tokens; the dynamic knowledge and memory guidance is about 298 and 89 tokens respectively. MemoryTool and RagTool descriptions alone are about 266 and 109 tokens; actual tool schemas, native tool handling, configured project instructions and retrieved context vary. The added source guidance is about 61 tokens. These estimates are not model-tokenizer counts. `prompts/chief-agent.md` sections estimate approximately 72, 168, 150, 89 and 51 tokens, plus 53 tokens of header material, but are not automatically included in these paths.

## Limits

The router uses bounded lexical intent signals, not semantic understanding. Its limited typo tolerance applies to grammatical intent markers, not source restrictions or retrieval queries. Short follow-ups bind to the latest substantive user turn; resolving an implicit return to an older topic is not generally solved. Prose-candidate detection is deliberately conservative and does not prove that a memory answers a question. An uncertain candidate skips the automatic fallback but the model receives a retrieval hint and can search if necessary. Detailed, conflicting, missing and otherwise ambiguous cases retain the existing fallback policy. Actual answer grounding and latency require a separate opt-in evaluation with a real model and representative isolated data.
