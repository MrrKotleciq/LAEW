# Stage 2B.2 hybrid RRF — Task 2 only

Declared before scoring, 2026-11-10. Use equal-weight RRF with constant 60,
one-based ranks after eligibility/authorization/deduplication. No score mixing,
tokenizer changes, language rules, query exceptions or post-result tuning.

Reuse the immutable Task 1 corpus and final original-insertion-order candidate
artifact for all four frozen datasets, both chunkers and stress_1036. No new
embedding calls, model/server work or production indexing. Native dense >=.3,
literal FTS matches with negative native BM25 scores; never apply cosine gates
to BM25 or call fusion values cosine. Canonical authorized records, exact binding
and matching payload are required before either backend contributes a rank.
Bindings remain separate for global/project; do not merge scores across scopes.

Compare dense, FTS5 and RRF at (backend depth D, final per-scope limit M):
(5,5), (10,10), (20,20), (50,50), (20,10), (50,10). Every method receives the same
D search results and the same final M cap. Report eligible union size/evidence
before truncation and final output size/evidence. Lexical-only candidates are
allowed only when the existing source policy permits them; lack of a dense hit
is not lack of source authorization. Preserve original scores and both ranks.
Identical duplicate IDs in a backend contribute once at first position; payload
conflicts fail closed. RRF score ties use stable IDs. Lexical outage falls back
to the exact eligible dense order, with a visible diagnostic; binding/freshness
errors must not be hidden as availability failures. Empty lexical matches are
not an outage.

For M10 only, run existing experimental ranked_fill at 1000 estimated tokens per
scope and manifest overall RAG allocation. Add a pre-vetted-ranking entry point
to the experimental selector to reuse its renderer/allocator without inventing
cosine values for lexical-only hits. Existing cosine entry/defaults remain intact.
Check equivalence to dense's old entry and replay through executor/adapter with
mocked transport. No production Chief Agent integration or real answer evaluation.

Measure candidate/complete/multi-document/cross-language coverage, scope-local
atom positions, gains/losses versus dense and eligible union; final coverage,
irrelevant/no-atom context, count, clipping and attributed token cost. Retain all
per-query regressions and s14/u17/cross-language diagnostics. No significance
claims from these small source-correlated datasets. Unsupported hits do not prove
answerability. Cached retrieval timings remain historical, not fresh hybrid latency.

Separately replay fresh dense+unchanged FTS5 indexes from cached vectors in runner
temporary storage, at representative scope-global holdout and stress queries,
D5/10/20/50, M10, 20 warm repeats. Measure dense, FTS and full sequential hybrid
plus fusion-only processing separately. Measure Python fusion allocations and
native-inclusive RSS with scope/backend bounds; do not infer million-document cost.
No BM25S dependency is needed for this task. Tests/evaluations use run_isolated.py.

Task 3 design only: dual-store generation publication, locking, rollback, deletions,
authorized scope/project binding, stale lexical detection, and visible degraded
mode. Do not implement a production coordinator, change routing, defaults, chunking,
models, services, source policy, tokenizer or paid APIs. Preserve all prior changes;
no commit/push. Stop for approval before Task 3.
