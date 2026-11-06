# Final evidence utilization investigation

The historical `v21` false abstention did not recur. Three fresh runs with the unchanged Chief Agent each named Lena. The three first inputs were identical within this run, including the user message, system message and native tool definitions. The investigation used 21 calls through the existing ChatGPT OAuth adapter under a cap of 22. The server identified every response as `gpt-5.6-luna`.

## Evidence and active prompt

The isolated Memory record said **“My camera was borrowed by someone.”** The Global excerpt from `@knowledge/v21.md` said **“My camera was borrowed by Lena.”** These statements are complementary. The first leaves the borrower unspecified, and the second identifies her. The captured first input included both complete statements, with labeled Memory JSON first and the labeled Global excerpt second. Both were delivered before any model-initiated search.

The runtime prompt is assembled by `AgentExecutor` from the default `AgentConfig`, registered tool descriptions, runtime knowledge guidance and the evidence prepared by `KnowledgeTurn`. Workbench uses that executor path. The investigation did not rely on `prompts/chief-agent.md`. The runtime asks the model to report genuine discrepancies, check coverage and disclose unverified gaps. It describes Memory as personal evidence and Global Knowledge as documentation. That distinction could affect interpretation, but the captured prompt contains no instruction that silence in Memory invalidates another source. The successful Global-only and reordered probes provide no repeatable indication of a presentation failure.

The Stage 4 report recorded the delivered atom and request size, rather than storing the full input. The reproduction used the same fixture, query, runtime path and tool schema, with the same recorded input lengths. The new Memory record has a synthetic identifier. Exact first-input equality was verified across the three fresh runs.

## Live checks

| Condition | Result |
| --- | --- |
| Unchanged end-to-end `v21`, Memory then Global | Lena in 3/3 |
| First response with Memory evidence only | Correctly left the borrower unknown in 2/2 |
| First response with Global evidence only | Lena in 2/2 |
| First response with Global before Memory | Lena in 2/2 |
| Independent complementary cases `e01`–`e03` | Nika, Oskar and drawer JN-73, all correct |
| Independent cross-source conflict `e04` | Reported both codes and declined to pick a current code |

The six first-response probes changed only the evidence appendix on the captured input. The tool definitions and question were preserved. These were adapter probes rather than rerouted turns. They produced text and no tool requests. In the independent end-to-end case `e02`, initial routing selected neither source. A model-initiated Memory recall and the ensuing automatic Global escalation recovered both before the answer. This is a routing observation outside the scope of the evidence-use investigation.

## Matched comparison

The panel includes `v20`, `v21`, `h11`, `h18`, `l03`, `l04` and `l05`. The fresh panel uses the first `v21` attempt. No production change separates the two columns.

| Metric | Stage 4 baseline | Unchanged retest |
| --- | ---: | ---: |
| Correct answers | 6/7 | 7/7 |
| Grounded answers | 6/7 | 7/7 |
| False abstention among answerable turns | 1/5 | 0/5 |
| Evidence utilization, labeled delivered atoms correctly used | 7/8 | 8/8 |
| Correct abstention | 2/2 | 2/2 |
| Evidence atom coverage | 8/8 | 8/8 |
| Model calls | 8 | 8 |
| Median end-to-end latency | 3.371 s | 3.037 s |

`v20` and `h18` used the expected personal facts. `h11` separated the tentative and confirmed dates. `l03` used both Project values while respecting the source restriction. `l04` disclosed both conflicting Memory codes and withheld a definitive choice. `l05` correctly acknowledged the absence of evidence. Across the 13 fresh end-to-end runs, including repeated `v21`, 13/13 answers were correct and grounded, all 15 delivered atoms were used correctly, and all three expected abstentions were correct. Direct review used the predeclared references and the observed evidence, without a separate judge call.

## Decision and limits

The original response demonstrates an evidence-use failure in that inference. The reproduction did not establish a routing, assembly, instruction or ordering defect. A small sample cannot determine the underlying cause or rule out recurrence. The Chief prompt and production code were left unchanged. The latency difference is a comparison between live runs rather than a measured improvement.

The targeted offline regression passed **309 tests**. The browser test was skipped and the loopback OAuth callback was deselected in this run. Prior source-restriction tests were included. The [per-case report](evidence-utilization-final.json) contains the captured synthetic adapter input, probe results and reference review.
