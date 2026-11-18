# Final RAG optimization preflight

Date: 2026-11-18. Status: offline work complete, embedding authorization pending.

## Verified baseline

The study used `codex/rag-development` at `dd5886e620d83fd8109fbe47fd929667b1986701`. The production route constructs scoped prefetch with a 500-estimated-token scope budget and the runtime legacy default. The frozen A arm is its K2/500 single-scope comparator. B and C use K10, cosine at least 0.30, ranked fill and 1,000 tokens per scope, with an 8,000-token outer budget. The underlying search uses L2-normalized embeddings and Chroma cosine. The renderer charges for attribution, only clips a sole first fragment, and skips later fragments that exceed the remaining budget. Legacy uses heading-separated windows of up to 1,000 characters and 200 overlap. Structure-v2 recognizes headings, fences and tables, groups by path and includes bounded source-derived synthetic context in indexed and delivered text. The freeze's Markdown and character offsets bind to the corpus source and original page/block maps. Runtime path filtering and benchmark-specific interval restrictions operate at different layers.

The cache-only runners verified the freeze of 777 artifacts and 24 units, the 60-question manifest, archived trace and vector integrity, rubric v2.1 and original datasets. They replayed all 180 historical rendered contexts and 540 stage scores. The 48 answerable variants represent 16 of 20 dependent intent families.

| Historical arm | Raw candidate complete | Delivered complete | First two eligible documents, accessibility ceiling |
|---|---:|---:|---:|
| A | 11/48 | 5/48 | — |
| B/K10 | 21/48 | 13/48 | 40/48 |
| C/K10 | 21/48 | 18/48 | 42/48 |

The accessibility ceiling reads all unrestricted ranges of the two documents without enforcing search, selection or budget within them. Previous K20, ranking, query decomposition and evidence navigation experiments did not establish enough gain in delivery to justify rollout. The new interventions change document representations before first retrieval or change what can co-locate within a fragment. They do not change query text, rank an already retrieved pool, or add a navigation step.

## Independent offline results

| Collection | Chunks | Body chars p50 / p95 / max | Attributed chars p95 / max | Unique cached document inputs | New exact inputs |
|---|---:|---:|---:|---:|---:|
| Historical B | 2,171 | — | — | — | 0 |
| Historical C | 2,185 | — | — | — | 0 |
| Matched B | 2,152 | 784 / 984 / 1,000 | 2,660 / 3,033 | 2,087 | 0 |
| Matched C | 2,161 | 839 / 1,000 / 1,000 | 2,771 / 3,150 | 2,126 | 0 |
| Contextual | 2,161 | Same as matched C | Same as matched C | 0 | 2,161 |
| Adaptive | 1,759 | 764 / 1,159 / 1,599 | 2,696 / 3,340 | 412 | 1,307 |

**Contextual embeddings.** The input prefix uses the exact manifest document identifier, pinned revision, declared applicability and allowed heading path. Its representation hash differs while chunk ID, body, source ranges and model-visible evidence remain identical to matched C. This can change ranking where generic chunks compete across products or editions. It cannot recover evidence withheld by the restriction or improve costs at fixed ranks. Evidence support for S05 is absent from matched C's index, therefore the contextual arm shares that ceiling. Metadata could also overweight the document, losing within-document discrimination. No candidate, delivered, warning or version gain has been measured for this arm.

**Adaptive chunking.** The candidate index has 18.6% fewer fragments than matched C. It preserves all nine parser-recognized tables and all 287 recognized fenced blocks whole. It divided five oversize list groups and 19 oversize narrative paragraphs. It withheld 164 lines at declared restrictions and no whole oversize code/table blocks in this corpus. Other original layout and list relationships remain subject to the freeze's known limitations. Every attributed fragment fits by itself in the 4,000-character scope budget. Fitting a set is a separate constraint.

The full-index diagnostic evaluates the least-cost union of whole chunks bearing registered proof, including attribution and separators. It ignores ranking, K10 availability and ranked fill. Across all 16 answerable families, the adaptive index contains a complete registered method, versus 16 in matched B and 15 in matched C. Thirteen families fit the 1,000-token limit in both adaptive and matched C, with different membership. S05 fits in adaptive at 615 tokens and in B at 666, but matched C misses registered support. S12 moves from 986 tokens in matched C and 827 in B to 1,092 adaptive. S08 rises from 433 in C to 445. P03 remains too large at approximately 3,408 tokens even under adaptive, versus 3,699 for B and 4,768 for C. S11 still exceeds 1,000 in all three. The ledger records minimum costs and exact witness IDs for every answerable intent.

## Source restrictions, applicability and controls

Each restricted component and related-context range was validated against its pinned text and source hash. Matched B removes 19 chunks for restricted source ranges. Matched C removes 18 for primary/copied context and conservatively removes six attributed table continuations on restricted units. Adaptive chunks contain one exact contiguous allowed source slice. Copied ranges and attribution are checked separately where applicable. The two arms use the same 24 version-pinned documents and retain source map references. Exact scope values distinguish Prusa hardware and printed revisions, Pro Git language-specific commits, and PostgreSQL release snapshots or the WAL commit. Applicability in the contextual prefix stays internal to retrieval. The delivered renderer remains historical. No missing diagrams, requirements or warnings were inferred. The ten restrictions and 329 inherited uninspected High findings remain open.

The rebuilt B and C controls changed raw K10 membership in two and five queries respectively compared with their own historical traces. Across the 120 B/C comparisons, no completeness flag changed at raw, eligible or delivered stages. Known historical selected restricted-range exposures were A/B/C on S16-de, with C also on S16-en and P02-en. The matched controls had zero restricted-range hits at any stage. This verifies this evaluation restriction policy on the frozen corpus. The paired ledger preserves full rubric method and requirement status to expose partial gains and regressions. The two experimental rankings and answer-level applicability and warning judgments remain pending.

| Cache-only disposable index | Build seconds | Disk MiB | Warm K10 p50 / p95 ms | Rendering p50 / p95 ms |
|---|---:|---:|---:|---:|
| Matched B | 2.21 | 21.8 | 13.49 / 14.38 | 0.16 / 0.25 |
| Matched C | 2.72 | 26.2 | 15.87 / 20.07 | 0.20 / 0.29 |

Each latency distribution has 60 queries after one cache-only retrieval warmup. These are embedded Chroma 1.5.9 measurements, excluding embedding time. Actual experimental disk, build and latency await the new vectors. Embedding prefix storage is not required in Chroma metadata.

## Embedding approval

| Workload | New unique inputs | Estimated input tokens (ceil(chars/4) per input) | Maximum requests | Raw new float32 vectors |
|---|---:|---:|---:|---:|
| Contextual | 2,161 | 569,114 | 662 | 8.44 MiB |
| Adaptive | 1,307 | 253,551 | 333 | 5.11 MiB |
| Both, independent runs | 3,468 | 822,665 | 995 | 13.55 MiB |

There are zero overlapping new inputs across arms. All 60 raw query texts have cached vectors and none need embedding. The workload is frozen by SHA-256 `28667adbe886f2e14cd694913723e2d8bdff6569fb9606b8c92cdf660a71709f`. The request ceiling counts a greedy stable pack per arm of at most four texts and at most 4,096 combined UTF-8 bytes plus eight units per sequence. Maximum new input length is 1,674 UTF-8 bytes. These are planning estimates and transport packing limits. The server-reported token usage will be recorded with no implicit truncation or retry. The immutable cache binds exact input and catalog identity. The newly read local GGUF hashes to `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`, 639,150,592 bytes. The historical receipt from the same build documents last-token pooling and L2 normalization. No currently running service was verified. Before dispatch, require a user-prepared CUDA instance and verify actual launched weight hash, build, alias, pooling, normalization, offload, dimension and slot settings locally. Keep original cache entries under their historical model identity. Only documented catalog runtime fields such as reload time may drift after weights and inference settings are verified.

```powershell
llama-server --model "<existing verified Q8_0 GGUF>" --alias laew-qwen3-embedding `
  --host 127.0.0.1 --port 8081 --embedding --pooling last --embd-normalize 2 `
  --gpu-layers 99 --parallel 4 --ctx-size 16384 --batch-size 4096 --ubatch-size 4096
```

Installed binary reports b11540-1e6f04a75. The sampled RTX 4060 had 8,188 MiB total and 6,743 MiB free. A 16,384-token total FP16 KV allocation would be about 1.75 GiB at the publisher's 28 layers, eight KV heads and 128 head dimension. Weights add approximately 0.60 GiB. Allow roughly 3–5 GiB total for weights, buffers and CUDA overhead, verifying actual allocation and full GPU offload before submitting any embedding. Reserve 0.3–0.5 GiB scratch disk for experimental indexes, ledgers and traces. GPU timing is a conditional estimate. At 1,000–3,000 effective input tokens/s, the joint inference work would take approximately 5–14 minutes before process, HTTP and measurement overhead. Reserve 15–25 minutes in total. The prior 41-short-query GPU run processed 3,419 tokens in 0.956 s, an imperfect reference for longer passages. Stop on identity mismatch, truncation, memory pressure, ambiguous dispatch or partial response. No automatic retry or CPU fallback. [llama.cpp server flags](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) · [Qwen3 model config](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B/raw/main/config.json)

## Decision and reproduction

Retain A. Adaptive has the cheaper workload and a direct measured packing effect, with a mixed feasibility result and no demonstrated net gain in budget-feasible families versus safe C. Test it first if GPU time is limited. Contextual embeddings target the larger first-stage discovery deficit but provide no offline performance evidence and leave all packaging limits intact. One frozen run per approved arm is the last justified test. No combined variant is scheduled. Stop RAG optimization if no arm meets the preregistered delivery criterion with acceptable safety and applicability. The existing exposed benchmark and incomplete human validation cannot establish a 90% real-world target.

The conditional live protocol in the companion design caps work at 120 attempts. At that ceiling, the previous navigation proposal's approximate first-turn average of 2,086 estimated input tokens suggests roughly 250,000 input tokens. Its 300–900 final-answer output tokens per attempt imply roughly 36,000–108,000 output tokens, excluding reasoning. Exact payloads and the authorization cap must be calculated afresh. The existing OAuth transport and guard require terminal model verification and durable accounting, but current runners authorize specific 36- and 48-attempt study packages. A new frozen schedule and corresponding reviewed authorization configuration are required if one variant earns a live test. The evaluation would use exactly `chatgpt/gpt-5.6-luna`, preserve fresh one-shot state, and obtain separate authorization. No live question or payload is frozen now.

Reproduction uses the isolated runner, the exact diagnostic study config and the historical decomposition model receipt. Use a fresh external directory for each phase and pass the actual manifest SHA-256. The three phase manifests cover the pending workload, cache-only results and post-collection scoring. `reproduce-preflight.ps1` in the external package captures arguments. `verification.json` records code, test, output and Git state. No embedding or generation requests were dispatched. No production code was edited.

One bounded test-writing task was assigned explicitly to GPT-6.1 Terra. Model selection was accepted by the tool; the running worker reported its model identity was not independently exposed. GPT-6 Luna was unavailable in the override catalog, so the coordinator performed source inspection. There was no Sol or Astra delegation. The coordinator reviewed the tests and corrected their offset fixture to supply full normalized text before the final run. Result: 52 passed, 3 skipped through `scripts/run_isolated.py`.
