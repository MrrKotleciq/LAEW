---
name: Global RAG and Ingestion Audit
description: Source-based Stage 2A audit, isolated verification, and proposed Stage 2B scope.
type: report
title: Global RAG and Ingestion Audit
scope: project
status: active
read_when:
  - assessing Global Knowledge freshness and retrieval quality
  - planning Stage 2B RAG improvements
---

# Global RAG and Ingestion Audit — Stage 2A

Audit date: 2026-11-03. This document distinguishes implemented behavior from architectural intent. It audits the existing ingestion/retrieval foundation; Knowledge Curation adds an approved-write trigger on top. No production vault, collection, model, Obsidian plugin configuration, or embedding configuration was modified for this audit.

## A. Current architecture

```text
Configured @knowledge root (C:\ROOT\Knowledge)
  -> selected UTF-8 *.md files
  -> simplified Obsidian frontmatter / tags / wikilink parser
  -> regex heading sections
  -> character chunks (1000 characters, 200-character overlap)
  -> dedicated llama.cpp /v1/embeddings endpoint
  -> normalized vectors + source/path/text/chunk metadata
  -> ChromaDB global collection laew_global (cosine)
  -> query embedding + vector nearest neighbors
  -> similarity threshold + descending similarity sort
  -> bounded attributed context
  -> RagTool.query
  -> Chief Agent tool-result context
```

Primary evidence: `laew/runtime.py::build_embedding_service`, `build_rag_tool`; `laew/rag/knowledge_base.py:296`, `:455`, `:558`, `:596`; `laew/rag/vector_store.py:239`, `:347`, `:388`; `laew/rag/pipeline.py:90`, `:249`, `:274`; `laew/rag/rag_tool.py::RagTool`.

ADR-002 requires one global vault; ADR-011 separates it from project memory. ADR-003 describes a retrieval/reranking pipeline, but the current “reranking” implementation only filters and sorts existing cosine scores. It does not invoke a learned reranker. The manifest's `reranking: true` does not introduce a reranker or select a different implementation.

### Actual vault and metadata

Read-only inspection found `profile/`, `topics/`, `research/`, `decisions/`, `inbox/`, `templates/`, `README.md`, `.obsidian/`, and `.smart-env/`. Existing topic subfolders include `topics/ai/` and `topics/security/`. The vault README explicitly specifies Polish authored notes, existing-language source exceptions, stable descriptive filenames, and manual approval before promotion.

Existing metadata includes `name`, `description`, `title`, `type`, `scope`, `status`, `tags`, and `read_when`; ordinary notes use `type: docs`, indexes use `type: index`, and draft notes may use `status: draft`. Existing Breadcrumbs properties and wikilinks must be retained. The template `templates/engineering-note.md` asks authors to distinguish verified claims from open questions and preserve source paths/URLs and verification dates.

The ingestion parser is a limited custom parser, not a full YAML/Markdown parser (`laew/rag/obsidian.py`). Only tags and extracted wikilinks are copied into indexed chunk metadata. Most semantic fields, including status, scope, name, description, and arbitrary Breadcrumbs relations, are lost from retrieval metadata. Heading text is retained as `section_header`; it is not a hierarchical heading path. The parser calls outgoing `[[...]]` links “backlinks”; it does not calculate an incoming-link graph. Links retain textual aliases/anchors rather than resolving a canonical target. Dataview, DataviewJS, Smart Connections, and Breadcrumbs plugins are not executed or used as retrieval backends.

### Selection and scope

`laew/rag/config.py::global_source_exclusions` excludes `inbox/**`, `templates/**`, `assets/**`, `backups/**`, `temp/**`, and temporary/backup Markdown patterns. Manifest exclusions extend defaults. Reserved exclusions are matched case-insensitively. Hidden files/directories and common dependency directories are skipped. The vault README intentionally remains indexed. Only Markdown is ingested; attachment/PDF/office content has no ingestion path here. Both initial and incremental loading use `_source_selected`.

Root resolution uses `PathResolver` and `resolve_knowledge_root`; traversal outside the trusted alias is rejected. Resolved source files are checked against the selected root. `KnowledgeBase` rejects overlapping project/global roots. Project sources use a manifest/project allowlist and a collection name derived from the canonical project-root identity (`laew/rag/identity.py`), rather than sharing the historical `project_collection` value. General Chat registers a global-only RagTool; Project Chat can request project, global, or both.

### Embeddings and ChromaDB

The checked-in manifest specifies `type: llamacpp`, model ID `laew-qwen3-embedding`, endpoint `http://127.0.0.1:8081`, 1024 dimensions, and a 30-second embedding request timeout. This identifies configured behavior; the actual GGUF weights, pooling configuration, server command line, loaded model identity, and Polish/English semantic quality were not independently verified. No model requests were made for this audit.

`LlamaCppEmbedding` posts document chunks in one OpenAI-compatible batch per file. Response validation checks count, indexes, numeric values, and declared dimension. There is no hidden embedding probe during construction. Stored vectors and query vectors are normalized to unit length by the vector-store layer. Model identity includes service implementation, model string, endpoint, and dimensions. A populated Chroma collection with missing/incompatible identity is rejected. This catches configuration changes, but cannot detect different weights served under an unchanged model ID and endpoint. No task-specific query prefix is added by the current adapter; whether one benefits this deployment needs model-specific evaluation.

Local installed Python Chroma client: **1.5.9**, observed through package metadata. `pyproject.toml` allows `chromadb>=0.4.0`; `docker-compose.yml` uses `chromadb/chroma:latest`. The production server version was not queried. This is not a pinned client/server deployment. `ChromaVectorStore` uses `HttpClient(host, port)` with a legacy settings fallback, `get_or_create_collection`, `get`, `upsert`, `query`, and `delete`. Although constructors accept `timeout`, `_build_chroma_client` does not apply that argument to `HttpClient`; it is not an effective explicit request timeout.

Chunks store `text`, `source`, `file_path`, section/index data, tags, and links in metadata. Compound metadata is JSON-encoded and decoded on retrieval. Collection configuration requests cosine distance. There is no separate native Chroma document payload/lexical search path in this implementation. Collection construction can create a collection or attach model identity, so even constructing a store is not a strictly read-only production probe.

## B. Implemented features

### Incremental synchronization

`KnowledgeBase.synchronize` performs a full selected-files scan and reads existing scope metadata. It fingerprints file text, chunk size, overlap, and embedding identity. Unchanged documents reuse existing records without embedding calls. It also checks expected chunk count and supports comparing legacy records without fingerprints against freshly chunked text/metadata.

Changed documents are re-embedded in full; this is document-level incremental processing, not changed-section embedding. New chunks replace matching IDs through upsert; IDs no longer produced are deleted. Deleted files and files newly excluded from source selection have their records removed at the next successful reconciliation. Unrelated records/scopes are preserved. IDs use source, relative path, section ordinal, and chunk ordinal. They are stable for the same structure, but a renamed file or inserted earlier section changes IDs. Native path separators appear in IDs, while reconciliation normalizes stored file paths for comparison; cross-platform migration deserves a targeted fixture.

Scan/read/embedding work is planned before vector mutations. A scan failure or embedding failure therefore does not immediately delete a valid index. Upsert followed by deletion is not a database transaction: failures can leave a partially updated generation.

### Coordination, restart, and failures

`synchronize_scope` (`laew/rag/sync.py:68`) combines a process-local scope lock with a cross-process collection lock. It marks a generation incomplete before mutation and complete after success. Retrieval through the standard runtime requires a successful synchronization state and holds the matching locks while querying. An incomplete or foreign generation blocks retrieval until reconciliation succeeds. This coordinates cooperating local processes; it does not prevent external Chroma clients from mutating a collection.

Freshness status is process-local. Startup synchronization re-establishes it; a restart does not trust a populated collection merely because it exists. When persistent storage initially cannot connect, `KnowledgeBase` can expose a warning and temporarily build an in-memory store. The standard `require_freshness` path calls `ensure_store` and blocks successful persistent retrieval until reconnection/synchronization, rather than silently claiming the fallback is the persistent index.

Periodic retries are possible through the scheduler; manual synchronization is also available. The pre-curation scheduler has no durable per-file outbox, exponential backoff, or persistent retry ledger. Partial-write recovery comes from reconciliation plus generation validation. Logging and last-success/last-failure status exist; there are no service-level metrics or alerting dashboards.

### Actual synchronization triggers and freshness

The existing mechanism is **startup + periodic + manual**, without a filesystem watcher. `SyncScheduler.start` immediately requests global synchronization and, when a project is selected, project synchronization. It then requests global synchronization every **1800 seconds**. Project activation/manual actions can request project synchronization; the periodic loop itself is global-only. The web application and interactive CLI start managed schedulers (`WorkspaceService.start_sync`, `laew/cli.py`). Standalone API consumers that build a pipeline must establish freshness themselves.

| Change | Visibility condition | Timing / limit |
|---|---|---|
| New selected Markdown file | Successful global reconciliation | Startup/manual, or next 30-minute tick plus scan/embedding/write time |
| Changed Markdown | Fingerprint changes; successful upsert and obsolete-ID deletion | Same triggers; not immediate after arbitrary external edits |
| Shortened document | New IDs upserted; old extra IDs deleted | Same successful synchronization |
| Deleted/moved-to-Inbox document | File absent from selected set; old IDs deleted | Same successful synchronization |
| Changed index through cooperating process | Matching successful generation required | Standard retrieval blocks unknown/foreign/incomplete generations |
| Chroma unavailable | Synchronization/retrieval reports failure | No guaranteed recovery deadline; retry after service recovery |
| Approved curation write | Curation outbox invokes existing ingestion | Separate write/index statuses; do not infer retrieval availability from file-write success |

A “successfully synchronized” status describes the last scan, not current filesystem state. There is no check for later external file edits during each RagTool query. Thus a successful status can coexist with an externally changed or removed file until another synchronization. Thirty minutes is a nominal polling interval, not a maximum freshness guarantee during outages, contention, or long processing.

## C. Retrieval and missing features

Global retrieval is vector-only. `RAGPipeline._retrieve_candidates` requests `top_k` candidates from the selected collection(s). The default is **5**, default cosine similarity threshold **0.3**, context budget **8000 estimated tokens**. `scope=hybrid` means merging project/global vector results; it does **not** mean lexical/vector hybrid search. It may return up to twice `top_k` before context assembly because each store is searched independently.

There is no BM25/keyword Global RAG search, query rewriting, learned reranker, retrieval-quality confidence calibration, neighbor-chunk expansion, semantic chunk deduplication, or document diversity policy. Returned source paths are deduplicated; overlapping chunk text is not. Metadata filters beyond source scope are not exposed by RagTool. `max_results` accepts positive integers without a hard upper bound. Chroma's source-filter compatibility fallback can retry without the filter; source isolation currently relies primarily on separate collections.

Context includes source scope, logical alias, path, section header, tags, and links. Token counts use characters/4 rather than the actual model tokenizer, and attribution/separators are not included in the count. RagTool retains a ContextBudget reference but context fitting occurs inside RAGPipeline. There is no shared dynamic budget arbitration with conversation history and Memory Recall.

Chief Agent invokes RagTool through its ordinary model-directed tool loop. Registered tool descriptions tell the model which scope to use and require provenance. There is no automatic Global RAG prefetch on every user turn. In contrast, Long-Term Memory Recall is automatically invoked by web/CLI chat orchestration, querying a separate memory collection with SQLite validation and FTS fallback. This is not a lexical fallback for Global Knowledge. Memory and Global RAG have separate limits, storage, and purposes; they are not merged into one knowledge store.

## D. Risks

1. **Freshness semantics:** external changes are invisible until reconciliation; a green last-sync status does not certify live filesystem freshness. Curation must request ingestion and expose index success independently from Markdown success.
2. **Trust metadata loss:** frontmatter `status`, document type, and uncertainty are not available for retrieval filters. Research/draft content can be returned like active documentation. Keep uncertainty in the visible body until metadata preservation/filtering is designed.
3. **Technical chunk quality:** regex heading detection is unaware of fenced code, so `#` lines inside code can create false sections. Character splitting can cut code fences, tables, wikilinks, equations, and sentences. Heading ancestors are absent. The default is a workable baseline for short prose, but insufficiently validated for technical documentation.
4. **Budget implementation:** the oversized-first-chunk branch slices with `remaining_chars` calculated from a float (`CHARS_PER_TOKEN_DEFAULT=4.0`), which raises TypeError. Default 1000-character chunks usually avoid this branch under the 8000-token budget. Attribution overhead also permits actual context to exceed the nominal estimate.
5. **Write atomicity:** upsert/delete are separate requests. Generation guards limit exposure for cooperating consumers, but cannot make Chroma transactional. Old or duplicate legacy records outside the recognized source-ID format are not necessarily reconciled.
6. **Scale:** every sync reads all selected files and all scope metadata; all pending embeddings/chunks are held before writes. Chroma count/get paths download records rather than using efficient scoped/paged APIs. Batches are not explicitly bounded to server limits. Full reindex cost scales with all selected chunks; no production timing/cost measurement was performed.
7. **Compatibility and availability:** Docker `latest`, a broad Python version range, and unused explicit Chroma timeout make upgrades and latency less predictable. Some legacy convenience methods (`clear`, `get_chunk`, `count`) hide particular errors; authoritative reconciliation should use fail-visible paths.
8. **Source correctness:** filename-based ordinal IDs do not identify a semantic claim; link aliases are not resolved to canonical targets. No claim-level provenance or verification filter exists. Retrieved text must remain untrusted data, never authorization.
9. **Quality unknowns:** deterministic fixtures prove software behavior, not Polish/English semantic recall or grounded final answers. No measured quality advantage should be attributed to the current model or threshold from these fixtures.

## E. Verification performed

All test writes used disposable resources under the repository, offline transport guards, temporary databases, and test embedding fixtures. No real model inference, production HTTP query, production indexing, or production collection write was performed.

| Command / scope | Observed result |
|---|---|
| `pytest tests/integration/test_rag_sync.py tests/unit/test_rag.py tests/unit/test_rag_config.py tests/unit/test_obsidian.py tests/unit/test_m17_obsidian_ingestion.py -q` | **86 passed**, 3.18 s |
| `pytest tests/integration/test_chromadb_persistence.py tests/integration/test_rag_project_isolation.py tests/integration/test_rag_process_lock.py -q` | **15 passed**, 13.78 s; one Chroma dependency deprecation warning |

Commands used the repository `.venv` Python, a unique workspace `--basetemp`, and workspace-local `TEMP`/`TMP`. Initial attempts using the sandbox default temp location failed to create/clean directories; reruns with permitted local temp paths passed. Those initial infrastructure errors are not reported as product regressions.

The second group uses actual disposable Chroma PersistentClient databases, including subprocess/locking cases; it does not prove production server health or production embedding quality. The repository also contains a disposable Chroma HTTP partial-upsert crash test (`tests/integration/test_rag_http_crash.py`), Chief Agent scope tests, global-source-selection tests, and synthetic retrieval performance benchmarks. Their existence is source evidence; tests not listed above were not run as part of this audit.

The existing `tests/benchmarks/test_profile_rag_retrieval.py` uses deterministic pseudo-random vectors and measures speed, not semantic quality. `laew/eval` contains general task metrics/datasets, but no labeled bilingual Global RAG corpus with Recall@k/MRR/nDCG evaluation was found.

## F. Prioritized improvements

| Priority | Improvement | Reason and dependency |
|---|---|---|
| Critical | Preserve approved-write/index separation and durable retry/recovery in curation | An approved file must survive unavailable Chroma and remain visibly pending until indexing succeeds; Stage 1 integration responsibility |
| Critical | Keep generation checks and source boundaries on all new ingestion entry points | Direct uncoordinated upserts would bypass partial-write protections |
| High | Correct partial-chunk budget handling and include context labels in estimates | Prevents an actual oversized-chunk exception and understated budgets |
| High | Preserve trust/type/status/title metadata without rewriting vault files | Enables honest provenance and later reviewable filtering policy |
| High | Add a small labeled bilingual retrieval evaluation | Establish baseline before deciding whether hybrid search/reranking is useful |
| High | Pin supported Chroma client/server versions and apply effective timeouts | Improve reproducibility and outage behavior; deployment changes require approval |
| High | Add fence/table-aware chunking with heading ancestry | Improve technical evidence coherence, evaluated against current baseline |
| Medium | Document freshness SLA; track dirty/pending status and indexing latency | A last-sync timestamp alone is insufficient; watcher vs polling is a user decision |
| Medium | Bound/paginate Chroma reads/writes and cap requested results | Improve memory use, server compatibility, and predictable latency |
| Medium | Normalize cross-platform source IDs and assess legacy orphan records | Requires an explicit migration/rebuild plan rather than silent mass changes |
| Medium | Evaluate overlapping chunk/document diversity handling | Reduce redundant context without discarding necessary evidence |
| Optional | Lexical/vector fusion, learned reranking, query rewriting | Implement only after measured benefit, model/service choices, costs, and approval |

## G. Proposed Stage 2B (not implemented by this audit)

Start with correctness, metadata, evaluation, and observability. Do not introduce a new Context Manager, embedding model, reranker, provider, or lexical/vector retrieval architecture implicitly.

1. Fix and regression-test context budget edge cases, including short budgets, attribution overhead, multilingual text, and oversized chunks.
2. Preserve existing frontmatter as selected retrieval metadata without migrating notes. Agree how draft/research/unverified notes should be surfaced or filtered; do not silently remove them from search.
3. Build a frozen, isolated mini-corpus and approximately 24–32 labeled queries. Include exact terms, paraphrases, Polish and English variants, cross-language queries, technical names such as ARX/RLS, ambiguous terms, questions requiring multiple notes, and no-answer questions. Record expected document IDs, graded relevance, relevant passages, permitted scope, and unsupported claims.
4. Establish the current vector-only baseline, then trial a fence/table-aware chunker and heading ancestry against the same corpus. Changing chunking implies a controlled reindex; do not run it against the production vault without an approved rollout.
5. Pin a compatible Chroma stack, implement effective HTTP timeout behavior, bound batches, and measure scan/embedding/write/retrieval latency and pending-index age. Evaluate a targeted single-file path or dirty-file queue only if full-scan cost warrants it, retaining periodic reconciliation for external deletions.
6. Present measured results and remaining failures before proposing lexical hybrid retrieval, reranking, query expansion, or a shared Context Manager.

### Evaluation metrics and acceptance criteria

Compute document-level Recall@5, Precision@5, MRR, and nDCG@5 with relevance labels frozen before tuning. Also inspect chunk evidence coverage, source correctness, scope leakage, no-answer behavior, and grounded answer accuracy separately. Multi-document questions need recall over every required source; deduplicating source paths alone is not enough.

Proposed initial gates, to be approved before treating them as release policy: zero cross-project leaks, zero fabricated source paths, 100% expected add/update/delete/restart/outage fixtures, at least 0.85 document Recall@5 and 0.80 MRR on the mini-corpus, and no answer asserted for at least 90% of designated no-answer cases. Quality thresholds are proposals, not existing measurements or user-approved requirements. Compare English and Polish groups individually so aggregate scores do not hide a language regression. Record latency/token counts and manually assess grounding with explicit evidence; model-based judges are optional and require cost/model approval.

Risks include a small overfitted corpus, weaker bilingual performance, chunking-induced reindex cost, changed result ordering after metadata/filter policies, and deployment incompatibility. Depend on isolated test resources and a reproducible stack before interpreting performance comparisons. Stage 2B implementation and any broader architecture change require the user's separate approval.
