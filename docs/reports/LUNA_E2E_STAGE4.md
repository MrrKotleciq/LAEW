# Stage 4 live Chief Agent evaluation

The November 6, 2026 baseline completed 13 synthetic turns through the existing LAEW ChatGPT OAuth adapter. The account catalog contained `gpt-5.6-luna` and the server returned that exact model identifier on all 16 inference responses. The run used one existing protected Windows registration. It used ChatGPT plan authentication and the documented Responses endpoint with local namespaced tools. [OpenAI model and inference documentation](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference) · [OAuth preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## Scope and methodology

The harness runs the production `KnowledgeTurn`, `AgentExecutor`, permission broker and OpenAI adapter in process. It provides only `MemoryTool.recall` and `RagTool.query`. The live tests executed both functions and delivered their actual native tool results to the next inference request. The Workbench HTTP, UI and persistence layers were outside the sample. Sources/Run fields came from the same `KnowledgeTurn.snapshot()` consumed by Workbench. Evidence was verified independently in the messages received by the adapter.

The data consisted of four unchanged historical synthetic turns and nine independent turns with [predeclared references](../../tests/evaluation/luna_e2e.json). The four-turn red-case conversation carried its actual answers forward. Memory used isolated SQLite and FTS5. Project and Global RAG used temporary persistent Chroma indexes with deterministic fixture embeddings, so this sample does not estimate production retrieval ranking. The default Chief prompt and production routing rules were used. The report stores synthetic answers and measurements, without request headers, provider continuation metadata or credentials.

## Results

| Measure | Result |
| --- | ---: |
| Initial / final / executed retrieval recall | 10/14 · 12/14 · 13/14 |
| Initial / final / executed recall excluding the two tool probes | 10/12 · 12/12 · 11/12 |
| Evidence coverage / atom coverage | 11/11 · 13/13 |
| Correct / grounded answers | 12/13 · 12/13 |
| Correct answers with all labeled evidence delivered | 10/11 |
| Unsupported domain claims | 0/13 |
| Missing required information | 1/12 |
| Correct abstention | 2/2 |
| Source restriction compliance | 7/7 |

Correctness and grounding were reviewed against the predeclared facts and actual answers without a separate judge call. The missing-information denominator includes every turn with required answer content, including the conflicting codes and the calculation. Grounding includes appropriate abstention and the arithmetic deduction. The incorrect claim of insufficient evidence in `v21` is recorded as a false abstention and an evidence-use failure. It did not invent a domain fact. Restriction compliance uses the seven explicit or inherited restricted turns, their backend scopes, forbidden markers and answer review.

The two tool probes intentionally bypassed automatic retrieval and recovered their required sources through model-initiated calls. One required backend search was absent in `l05`: the empty fixture had no active Memory rows, so automatic and model recall stopped before FTS. The model abstained correctly. Extra Global searches occurred in `v20`, `h18` and `l09`; the last returned empty.

| Named regression | Retrieved evidence | Live answer |
| --- | --- | --- |
| `v20` | Solaris in Memory and Global | Correct |
| `v21` | Lena in Global before the first inference | False abstention |
| `h11` | Confirmed Friday at 16:00 in Global; tentative Wednesday in Memory | Correctly distinguished the dates |
| `h18` | CR2032 in Memory and Global | Correct |

In `v21`, Memory said someone borrowed the camera and the delivered Global excerpt identified Lena. Luna answered that the context did not verify who borrowed it. The selected source ran, the relevant excerpt reached the adapter, and the response omitted its answer. The observed failure is evidence use. The model's internal reason is unknown. On the short continuation `l07`, topic binding was recorded. On return `l09`, the earlier answer and current Memory both supplied the cabinet code, so the run cannot distinguish their influence.

Median end-to-end latency was **3.335 s** (range **2.082–8.542 s**), with **51.165 s** summed across turns. The provider reported **17,556 input + 508 output = 18,064 tokens**. The 16 model calls initiated two MemoryTool calls and one RagTool call. Adapter message bodies contained a median of 3,890.5 characters (3,468–4,672), excluding tool schemas and provider continuation metadata. Automatically prepared retrieval context had a median of 365 characters and a maximum of 575.

The targeted offline regression passed 164 tests, and the separate loopback OAuth callback test passed. A smaller intermediate regression run observed incomplete evidence on the Chroma control fixture, despite successful retrieval statuses. The subsequent targeted run passed that control. The live persistent fixture delivered every labeled atom.

## Follow-up priorities

1. **P1 — Evidence synthesis.** Reproduce the `v21` pattern on independently labeled turns where Memory is incomplete and an allowed document supplies the missing identity. Compare reference-grounded answers and false abstentions before changing the Chief prompt.
2. **P2 — Fallback efficiency.** Test whether the three extra Global searches can be avoided while retaining the necessary Global evidence in cases like `v21` and `h11`. Include the empty-Memory case when reviewing retrieval hints and repeat recall behavior.

The [per-case JSON report](luna-e2e-stage4.json) is the recorded baseline. To explicitly start a new authorized run, provide a new output filename:

```powershell
.venv\Scripts\python.exe -m laew.eval.luna_e2e --live --output docs/reports/luna-e2e-new.json
```
