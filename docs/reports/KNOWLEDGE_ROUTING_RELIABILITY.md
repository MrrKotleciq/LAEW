# Knowledge Routing reliability

## Execution path

CLI chat and both Workbench chat paths use `KnowledgeTurn.prepare` before
the Chief request. It resolves the current user intent and any eligible
recent topic, invokes project-aware automatic Memory Recall when selected,
and assembles separate Memory and Knowledge sections. It calls RagTool
through the permission broker with an explicit Global or Project scope and a
bounded context budget. An inconclusive Memory result can schedule one Global
lookup when the turn policy allows it. After a model-initiated MemoryTool
recall, the same policy can add evidence before the next adapter dispatch.
The executor records when prepared excerpts actually reach the adapter.
Workbench Sources and Run report selection, omission reasons, backend
execution, and evidence supplied. Persisted diagnostics describe the original
run.

Project Knowledge is unavailable in General Chat. Project RAG resolves the
active project index, and Memory Recall filters project records by the active
project ID. Global and Project evidence remain separate. Conversation history
provides topic references and conversational context. Stored personal facts
come from Memory records, with explicit current statements distinguished from
questions and inferences.

## Failure analysis and policy

| Case | Initial cause | Observed after the change |
| --- | --- | --- |
| v20 | The Polish saved-context question pattern recognized `ktory` forms but omitted normalized `ktora`. | Memory supplied the novel. The existing assessment was inconclusive and also searched Global. |
| v21 | The English question used `has` with an owned object. The possession construction fell outside the interrogative patterns. | Memory supplied the topical record. Global supplied the missing borrower. |
| h11 | The confirmed-schedule question had no ownership cue or explicit source. The router had no corresponding intent signal. | Memory supplied the tentative record. Global supplied the confirmed date and time. |
| h18 | The English question used `does` with an owned subject. The previous patterns did not select Memory. | Memory supplied the battery identifier. The existing assessment was inconclusive and also searched Global. |

In all four baseline cases, neither Memory nor RAG was selected, so Recall,
assessment, escalation, and evidence assembly never had input. A separate
follow-up defect discarded the prior turn's source restrictions when
reconstructing a short continuation. The baseline also lacked a Memory
exclusion for automatic and model-initiated recall.

The policy now recognizes inflected interrogatives and first-person past
tense, English possession and auxiliary constructions, and narrow requests
for already arranged dates. The agreed policy for the last category starts
with Memory and allows one Global fallback under the existing sufficiency
rules. Generic definitions and advice have weaker retrieval signals.
Short dependent questions keep the recent topic's scope and exclusions.
Explicit source switches apply to subsequent short continuations of that topic.
The current user can also exclude Memory for the turn. Initial selection adds
zero model calls.

## Baseline and comparison

Each dataset ran through KnowledgeTurn and the real executor using a fixed
Chief adapter, isolated SQLite FTS5 and Chroma, and synthetic embeddings.
The historical sets retain their original evidence and Global-fallback labels.
Memory is the expected first attempt on those sets. The independent set
includes Polish and English personal queries, both RAG scopes, multi-source
questions, recent and revisited topics, negation, typos, general questions, and
missing evidence. Evidence is scored from the system message actually sent to
the adapter. A scored turn requires all of its markers. Fixture embeddings
select the seeded evidence deterministically. Rankings and answer quality on
real data are outside this comparison.

| Metric | Historical sets, 60 turns | Independent set, 36 turns | Combined, 96 turns |
| --- | ---: | ---: | ---: |
| Routing Recall, turns with every required source selected | 56/60 → 60/60 | 24/36 → 36/36 | 80/96 → 96/96 |
| Routing Precision, required selections / all selections | 93/108 → 99/116 | 17/24 → 32/41 | 110/132 → 131/157 |
| Missed Retrieval Rate at routing, missed selections / required sources | 6/99 → 0/99 | 15/32 → 0/32 | 21/131 → 0/131 |
| Unnecessary Retrieval Rate, extra selections / all selections | 15/108 → 17/116 | 7/24 → 9/41 | 22/132 → 26/157 |
| Required sources without an executed backend search | 10/99 → 4/99 | 17/32 → 3/32 | 27/131 → 7/131 |
| Unnecessary backend searches / executed backend searches | 15/104 → 17/112 | 6/21 → 9/38 | 21/125 → 26/150 |
| Evidence Coverage | 53/57 → 57/57 | 11/22 → 22/22 | 64/79 → 79/79 |
| Turns with forbidden evidence markers in prepared context | 0 → 0 | 3 → 0 | 3 → 0 |

All seven remaining missing backend searches are Memory invocations that
found zero active records in scope before reaching FTS5. The independent
no-source cases selected and executed zero searches after the change,
including when Project Knowledge was unavailable. The remaining extra
selections were Global fallback after inconclusive Memory Recall, including
v20 and h18. The absolute count rose by four while the share declined from
16.7% to 16.6%. Executed extra searches rose by five.

Each variant dispatched 96 fixed Chief requests and made zero assessment
model calls. Memory invocations rose from 65 to 77 and executed backend
searches from 125 to 150. Mean routing time was 0.39 → 0.53 ms per turn,
and mean end-to-end fixture time was 13.78 → 17.60 ms. Mean added context
was 262 → 323 characters per turn.

The [baseline](knowledge-routing-baseline.json) and
[post-change results](knowledge-routing-after.json) include dataset hashes,
per-case routing and evidence, wall time, retrieval time, backend call counts,
and assembled context length. Timing comes from single passes on this machine
and includes cold-run variation. Assembled context measures only the
Memory and Knowledge additions in characters.

Reproduce the offline run from the repository root.

```powershell
.venv/Scripts/python.exe -m laew.eval.knowledge_routing_eval --output "$env:TEMP/laew-routing.json"
```

## Verification and limits

Integration tests exercise the shared CLI and Workbench paths, automatic and
model-initiated Memory Recall, both RAG scopes, evidence supplied at adapter
dispatch, missing evidence, and rejection of disallowed tool calls. Multi-turn
tests cover inherited scope, an explicit source switch, and interruption by an
unrelated topic. A headless Workbench run uses a fixed streaming adapter and
isolated local services to check Sources and Run in the browser.

The full offline run with loopback access passed 1,437 tests, with four skips
and two deselections. All 30 JavaScript tests and the headless Workbench
test passed separately. One targeted run hit the previously documented
intermittent Chroma HNSW reader error. Its five prefetch cases passed on
isolated rerun. The latest follow-up cases passed in the focused run.

Topic binding is limited to recent user messages. Dates for specific public
events can resemble personal schedules and trigger a lookup. Generic
technical requests outside the recognized question forms can still trigger
the existing technical-topic heuristic. Source limits govern current
retrieval and evidence use. Earlier conversation messages may remain visible
to the model, whose adherence to the evidence instructions is outside these
fixture checks. Real-model answer quality, production retrieval accuracy, and
remote latency were outside this run.
