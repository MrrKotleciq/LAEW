---
type: protocol
title: Task 3B fixed hierarchical dense retrieval protocol
date: 2026-11-11
status: frozen-before-evaluation
---

# Task 3B protocol v1

Frozen before running strategy comparisons or reading new fixture results.
No query-specific policy or label-dependent branching. No generative rewriting.

* Both arms use the identical stored query embedding, source authorization,
  cosine >=0.3, D10/M10 per scope, ranked_fill/1000 and manifest overall budget.
* Fetch D10 hits from the scope-filtered Chroma query, sort by (-cosine, stable
  chunk ID), and retain eligible, nonempty, authorized unique seeds. Return fewer
  than 10 if eligibility removes hits. Native approximate tie membership at the
  cutoff is a backend limitation; ordering within its returned pool is stable.
  Compare the new baseline against the prior native D10 capture.
* A returns these seeds. B takes the first three distinct document identities
  in that ordering. Identity is (collection UUID, project root, scope,
  normalized relative Windows path), never basename or text equality.
* B issues ONE conditional Chroma query with source AND file_path IN the selected
  documents' stored path spellings, requesting at most 128 hits (or the known
  authorized child count). Validate every returned payload before eligibility;
  cosine-sort the restricted union with stable-ID ties and retain M10 leaves.
  No per-document quotas, seed reservations, expansion text, or score changes.
* Both arms use the existing original leaf renderer and source deduplication.
  No second embedding, parent vector/index, lexical backend or fusion.
* Maximum 2 Chroma query calls/scope for B, 1 for A; no vector fetches. At most
  138 returned records/scope, <=1 MiB serialized metadata per response. A response
  overflow fails closed. These are client consumption bounds, not a server-side
  HNSW work guarantee. Documents may have more than 128 leaves: conditional
  search returns a bounded approximate top pool, not source-order truncation.
* Supply a generation-bound authorized snapshot and a mandatory freshness lease.
  Hold the lease through seed query, drill-down and final validation. Reject
  collection/project/scope mismatches, unknown returned IDs, changed text/path/
  metadata, invalid scores and generation changes. Never retry without filters.
* Missing document mapping or filtered-query availability failure falls back
  exactly to the validated A seeds, ONLY after a fresh lease check. Invalid
  metadata/authorization/freshness fails closed. Empty match is not an outage.

## Evaluation freeze

Reuse all four frozen corpora, both chunkers, original legacy stress embeddings.
For stress v2, reuse distractor vectors and re-chunk/re-embed only Atlas if no
exact text matches exist; explicitly report the changed chunk count. Group the
same distractor leaves into 16 longer document identities as a controlled layout
intervention, preserving text/vectors and assigning unique stable control IDs.

Add authored long manuals (global and project), multilingual questions, a
multi-document question, a >3-document requirement and an unsupported query.
Freeze texts/labels before embedding or scoring; these are agent-authored,
not independently human judged. Record a separate cache hash. Do not alter
fixtures or policy after inspecting method results.

Measure candidate vs final evidence separately, per-query gains/losses/positions,
excluded documents, document/cross-language subsets, fragments, irrelevant/no-atom
context, attributed tokens and adapter replay. Overall manifest RAG allocation
and per-scope 1000 are hard limits. Summaries must not hide individual regressions.

Use actual disposable PersistentClient Chroma collections populated by the
existing production metadata serializer with cached vectors. Repeat warm timing
20 times on holdout, long-document and both stress layouts; report p50/p95,
query calls, serialized returned metadata bytes (not HTTP wire bytes), Python
allocation peak, process RSS and registry/index build cost separately. Timing
excludes the shared query embedding and reports selection separately.

Security tests cover all requested failure modes and existing generation locks.
Use scripts/run_isolated.py for tests and evaluations. No production writes,
services, dependency/model downloads, commit or push. Stop before rollout.
