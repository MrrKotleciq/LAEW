---
type: report
title: Stage 2B.2 advanced dense retrieval review — Task 3A
date: 2026-11-11
status: review-complete-pending-task-3b-approval
scope: read-only architecture, frozen cosine diagnostics and established retrieval methods
---

# Stage 2B.2 — Advanced dense retrieval review, Task 3A

**Recommend one isolated Task 3B experiment: seed-guided document/section drill-down using the existing dense embeddings.** Do not implement it yet. Retain dense-only; FTS5/RRF remain undeployed. `legacy / K10 / ranked_fill / 1000 tokens per scope` remains an experimental validation configuration, with the existing overall allocation. Production behavior is unchanged.

## Architecture and diagnosis

Reviewed the current pipeline, knowledge base, both chunkers, Obsidian parsing, Chroma adapter and synchronization, alongside the [chunking](STAGE_2B2_STRUCTURE_CHUNKING.md), [context preservation](STAGE_2B2_CONTEXT_PRESERVATION_PL.md), [evidence selection](STAGE_2B2_ADAPTIVE_EVIDENCE_SELECTION_20261110.md), [lexical](STAGE_2B2_LEXICAL_RETRIEVAL_20261110.md) and [RRF](STAGE_2B2_HYBRID_RRF_20261110.md) reports. Task 2's fixed-budget regressions remain the reason to retain dense-only.

Current retrieval embeds one question and ranks flat chunks by cosine, with eligibility at 0.3. Legacy chunks include their heading and carry source, file path, section/chunk indexes, tags, frontmatter and outgoing wiki-link targets. The field named `backlinks` is not a resolved inverse graph. Structure-v2 adds section paths, block IDs, offsets/lines and bounded contextual spans. It does not implement parent routing or general contextual expansion. There are no explicit parent/child or previous/next links in either runtime retrieval path.

Chroma stores `source` and `file_path` directly; the adapter JSON-encodes other metadata, including `section_path`. A native prefix/tree join cannot be assumed. Existing `query`/`get` and scalar metadata filters are sufficient building blocks for an isolated adapter, although the current public search method exposes only a source filter. Chroma documents metadata filtering for both operations. [Chroma filtering](https://docs.trychroma.com/docs/querying-collections/metadata-filtering)

Any future traversal must use collection/project identity, source and normalized logical path together, not a basename or a wiki link as permission. Hold the existing scope/generation locks across both stages; validate fingerprints, chunk IDs and provenance on follow-up reads. An edited file must invalidate its derived relationships. Added/removed chunks and moved paths must not leave stale parents. Existing upsert/delete synchronization is not a transaction across a new parent store. Avoiding a second store initially reduces that maintenance burden.

### Why `s14` fails

Read-only diagnostics reused the frozen Task 1 corpus/vector cache and ranking cache, verifying their common content hash. Exact normalized float64 cosine gives:

| Corpus / chunker | Prerequisite atom rank | Both acceptance atoms' rank |
|---|---:|---:|
| Supplement / legacy | 1 | 4 |
| Supplement / structure-v2 | 1 | 3 |
| 1036-chunk stress / legacy | 1 | 66 |

The acceptance chunk has cosine **0.447940**, above the existing gate. It contains the Atlas entity, the `Acceptance` heading and both complete required results: drift below 80 microseconds and a continuous 40-second trace. Neither result is split or clipped. Its rank **within Atlas is 4**; **62 non-Atlas chunks** outrank it. The top correct prerequisite is eight section/chunk positions away, so same-section expansion or a ±1 neighbor window will not reach acceptance.

The stress corpus adds 1024 generated, mostly near-clone distractor files with overlapping firmware/recovery/acceptance vocabulary, including statements that they supply no Atlas prerequisites or limits. Top distractor cosine is 0.505259. This supports a competition and query-representation explanation rather than broken chunk boundaries. Cosine similarity does not enforce negation or answer completeness. The one-file-per-distractor layout may particularly favor document routing; it is not representative evidence about a real large Second Brain. No structure-v2 stress cache exists, so its small-corpus rank 3 is not a stress result.

Six one-off calls used only the existing loopback Qwen embedding endpoint, matching the cached model/dimensions. A fresh original-question control had cosine 1.0 against its cached vector and reproduced rank 66. These fixed manual variants are **oracle diagnostics**, not an automatic rewriting system:

| Manually supplied query | Prerequisite rank | Acceptance rank |
|---|---:|---:|
| Polish prerequisite facet | 1 | 143 |
| Polish acceptance facet | 4 | 3 |
| English compound translation | 1 | 3 |
| English prerequisite facet | 1 | 80 |
| English acceptance facet | 24 | 1 |

The independently frozen German acceptance question `s16`, reused as an oracle facet, gives ranks 4/3. Both facet focus and language/phrasing can matter; this does not isolate their causal contributions or establish automatic cross-language rewriting quality. Single embedding calls took 95–219 ms; these are observations, not a latency benchmark. No answer values were inserted into the variants.

Across **161 answerable query/chunker pairs** from all four frozen datasets plus stress, every required document already appears in dense-eligible K10, and every atom ranks within 10 **when its correct document is supplied by the labels**. This is an opportunity audit, not achieved hierarchical recall. Documents are small: at most 12 legacy or 11 v2 chunks in the supplement. In `u27` v2, one required document is fourth in first-hit document order within its scope; a hard three-document beam could lose it. Do not choose a beam from its gold labels.

## Established approaches

| Approach | Reusable implementation / deterministic alternative | Cost, compatibility and limitations |
|---|---|---|
| Multi-query | LangChain `MultiQueryRetriever` generates variants with an LLM. Haystack `MultiQueryEmbeddingRetriever` instead accepts supplied queries; its separate QueryExpander is generative. Deterministic clause splitting or dictionary aliases need no LLM but are different methods. | Reuses Chroma and existing embeddings, with additional query embeddings/searches and union memory. No corpus re-embedding. Multilingual capability depends on both the embedder and variant quality; punctuation splitting is not reliable multilingual semantic decomposition. Parallelism trades wall time for load. Every branch needs the same authorization. Manual oracle success does not validate any automatic variant generator. |
| Hierarchical document/section retrieval | LlamaIndex `HierarchicalNodeParser` builds relationships deterministically; `RecursiveRetriever` follows linked nodes/retrievers. A seed-guided route can identify documents from existing child hits, then search their children with the same vector. | Language-neutral structure and the existing multilingual embedding space; suitable for both chunkers at document level, with richer section grouping in v2. Seed-guided routing requires no new corpus vectors/index. True coarse parent-vector routing requires extra parent embeddings and synchronization. Added query/read latency is bounded by routing breadth. A missed parent is a hard recall ceiling; multi-document questions need multiple routes. |
| Parent-document / contextual expansion | LangChain `ParentDocumentRetriever` maps small hits to stored larger parents. LlamaIndex `AutoMergingRetriever` merges sufficiently many retrieved siblings. Haystack `SentenceWindowRetriever` fetches neighbors. These mechanisms are deterministic; LLM-written summaries/context prefixes are separate, generative methods. | No extra embeddings when existing leaves and authorized source spans are reused. Requires reliable mappings/order, current parent text and deduplication. Larger contexts consume RAM and the final token budget; expansion does not guarantee relevant sibling selection. Legacy supports file/section grouping, while v2 offsets improve exact-span reconstruction. Adjacent windows miss distant evidence. |

Primary implementations: [LangChain multi-query](https://reference.langchain.com/python/langchain-classic/retrievers/multi_query/MultiQueryRetriever), [Haystack supplied-query retrieval](https://docs.haystack.deepset.ai/docs/multiqueryembeddingretriever), [generative QueryExpander](https://docs.haystack.deepset.ai/docs/queryexpander), [hierarchy parser](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/node_parser/relational/hierarchical.py), [recursive retrieval](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/recursive_retriever.py), [parent retrieval](https://reference.langchain.com/python/langchain-classic/retrievers/parent_document_retriever/ParentDocumentRetriever), [auto-merging](https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/retrievers/auto_merging_retriever.py), [sentence window](https://github.com/deepset-ai/haystack/blob/main/haystack/components/retrievers/sentence_window_retriever.py).

These libraries are not installed here and were not added. Reuse their algorithms through a thin isolated adapter if approved. Preserve LAEW's IDs rather than framework-generated UUIDs or automatic resplitting. Haystack's content-based multi-query deduplication is unsuitable as LAEW's sole source-identity rule. Recursive retrieval needs no LLM when linked only to nodes/retrievers; a query-engine branch may generate answers. Auto-merging's default requires **more than half** a parent's children: one hit among 12 Atlas chunks would not trigger it. Its inherited parent score is not a measured parent cosine.

### Recommendation and deferred alternatives

**Select seed-guided hierarchical drill-down only.** Start from existing authorized leaf hits, group by document, and run conditional dense retrieval inside a small set of those documents. Preserve original leaf chunks and their citations for final selection. The motivation is to reduce irrelevant-document competition: `s14` has a correct rank-1 seed and an acceptance leaf at local rank 4. This is a hypothesis to benchmark, not a demonstrated fix. Simply adding siblings and sorting the whole corpus by the same cosine leaves rank 66 unchanged; routing must actually change candidate allocation. It can also remove useful documents, as the `u27` audit warns.

Defer automatic multi-query: no tested model-free decomposition exists here, and adding an LLM would violate the intended first experiment. Defer whole-parent/window expansion as a second implementation. A hypothetical Atlas parent costs **1000 rendered estimated tokens** and still includes all three atoms, but almost consumes the scope budget. Its raw text is 4194 characters / 1049 estimated tokens. The two gold leaf chunks cost **231 tokens** with attribution, an oracle lower bound rather than achieved selection. Whole-parent expansion is approximately 4.3 times that cost and will scale poorly on long manuals; small windows miss the distant acceptance section. This is renderer inspection, not a parent retriever benchmark.

## Proposed short Task 3B benchmark — approval required

1. Freeze one isolated seed-guided routing policy before scoring. Baseline: dense D10/M10, `ranked_fill`, 1000 estimated tokens per scope and unchanged overall allocation. One experimental arm: D10 seeds; a fixed small document beam, initially 3 per scope by first eligible hit; conditional dense query restricted to those authorized document identities; M10 original leaf candidates. Keep cosine eligibility unchanged, deterministic ID ties and independent Global/Project processing. Do not reserve only one fragment per document. Report excluded seed documents, including the pre-existing `u27` risk; do not widen the beam specifically to rescue it.
2. Reuse all four frozen datasets under legacy/v2 and the reproducible 1036 legacy stress corpus. Keep candidate and final evidence metrics separate. Measure atom recall, complete evidence, multi-document/cross-language cases, positions, newly recovered/lost evidence, irrelevant selected context, fragments and attributed tokens. Inspect `s14`, `u27` and every regression. Unsupported questions still need evaluation; routing is not a sufficiency gate.
3. Use cached exact cosine to understand routing effects, then replay the same arm in isolated Chroma collections through the actual metadata serializer/filter path. No production collection access. Measure query count, zero additional query embeddings for drill-down, fetched bytes, warm p50/p95 over 20 repetitions, indexing/mapping time and peak RSS. Bound any exact child-vector fetch to 128 vectors per scope (512 KiB raw float32 at dimension 1024, excluding objects/metadata); report cap-limited cases and explicit dense fallback. Prefer filtered query over unbounded document scans. Never source-order truncate a long parent and claim complete search.
4. Test source/project isolation, duplicate IDs across scopes, deleted/renamed documents, fingerprint/generation changes between stages and missing mappings. Missing structural data may fall back to the original fresh dense result; freshness or authorization failure must fail closed. Keep mappings generation-bound and rebuildable in scratch storage.
5. Before broader adoption, add a small independently judged long-document and multi-document set. Include a stress control grouping competing passages into longer documents, because the existing distractor layout favors routing. Freeze judgments independently of method output. The present fixtures have already informed this hypothesis and are no longer a blind validation set.

Success requires improved candidate **and final** completeness at M10/1000 on independent cases, bounded measured overhead, no source/freshness violations and no unexplained losses of previously complete holdout cases. A gain only on `s14`, or only with a larger context/K, is insufficient. No statistical generalization is justified from these small synthetic fixtures. Production integration is outside Task 3B as proposed.

## Artifacts, validation and working tree

New inspection-only module: `laew/eval/dense_review_diagnostics.py`. It does not implement retrieval, fusion, expansion or a parent index. Added this report and a navigation link in `docs/README.md`; the remaining Task 3A files are diagnostic/state JSON and the validation log. [Structural audit](dense-review-20261111-structural-audit.json), [oracle observations](dense-review-20261111-oracle-diagnostics.json), [initial state](dense-review-20261111-initial-state.json), [final preservation audit](dense-review-20261111-final-state.json), [test log](dense-review-20261111-validation.log).

Diagnostics ran through `scripts/run_isolated.py eval laew.eval.dense_review_diagnostics`, first with six local oracle/control embeddings and then cached-only structural inspection. Existing focused chunking, ingestion, fixture and retrieval-lock checks ran through `scripts/run_isolated.py pytest`: **59 passed in 16.02 seconds**. No proposed method was implemented or tested. No new dependency, model, service, index or source data was created/changed.

Git remains dirty: pre-existing tracked modifications to `docker-compose.yml` and `docs/README.md`, plus earlier untracked experiments/reports/fixtures. Task 3A only appends its README link among pre-existing files; the final state artifact verifies the other captured pre-existing file hashes are unchanged. No commit or push. Stop here pending Task 3B approval.
