# Stage 2B.2 lexical backend evaluation — Task 1 only

Declared before lexical quality scoring, 2026-11-10. No hybrid fusion, production
integration, default changes, language models, source allowlist changes or private
knowledge reads. Preserve all existing labels, candidate pools and user changes.

Four frozen datasets, each legacy and structure-v2: baseline_v1, hard_cases_v1,
reranker_holdout_v1, evidence_supplement_v1. Reconstruct full indexes using the
existing KnowledgeBase and unchanged local embedding model; do not index only the
previous top-K union. Capture actual dense K5/10/20/50 and both raw and >=.3 eligible
dense results, per scope. Lexical results have no cosine threshold. BM25S returns
only positive lexical matches, not arbitrary zero-score padding; FTS matches only
the constructed bag-of-terms query. Final evidence selection is out of scope.

Language-neutral tokenizer fixed in advance: Unicode NFKC + casefold + Unicode
word runs (underscore retained), single-letter/numeric tokens included, no stemming,
no stopword list, no accent folding. Preserve document text and metadata separately.
Encode normalized tokens as ASCII UTF-8 hex for FTS5, quoted OR query constructed
by the adapter and SQL-parameterized. Raw user syntax cannot reach MATCH. Apply
the identical token list to BM25S. This sacrifices punctuation-only distinctions
(C++ vs C#) and does not solve inflection/cross-language translation; diagnose,
do not tune around individual fixtures. Bound queries to 4096 characters/128 unique
terms, reject overflow explicitly rather than silently changing the question.

FTS5: built-in bm25 fixed k1=1.2, b=.75 and native IDF behavior. BM25S 0.3.15:
NumPy backend, Lucene method, k1=1.2, b=.75, no auto compilation or optional extras.
Document frequency formulas differ; compare actual implementations, not claim
numerically equivalent BM25. Stable chunk-ID ordering breaks equal-score ties.
Independent per-corpus/scope/project index bindings isolate IDF and payloads.

Reuse the exact 1036-chunk stress generator from the previous experiment and verify
its recorded corpus hash. Persist new fixture/stress vectors and provenance in a
compressed experimental artifact, so further analysis does not repeat inference.
Re-embedding is local existing-model inference, not a model download. Stress uses
1024 generated distractors and the same 12 legacy Atlas chunks, four related queries.
It is not an independent relevance benchmark. Diagnose s14 raw/eligible evidence
ranks through K50, including whether each atom exists anywhere in the full index.

Metrics: candidate document/atom recall, complete evidence, multi-document recall,
PL/EN/DE and cross-language breakdowns, unsupported empty/irrelevant-hit behavior,
all per-query regressions against dense and between lexical backends. Separate
each dataset/chunker; no significance claims on correlated source groups.

Timing: one warmup and 20 repeated searches per K/query, including tokenization,
ranking, stable top-K and metadata hydration, excluding dense query embedding
(reported separately). Index/rebuild/save/load and incremental add/update/delete
costs are separate. Use fresh subprocess resource probes with Windows working-set
and peak-working-set observations; Python tracemalloc is supplementary and does
not capture SQLite/NumPy native allocations. Report active and retained snapshot
disk size separately. Do not extrapolate these small corpora to millions of chunks.

SQLite changes must be transactional and reversible. BM25S has no native mutation
API in the pinned version; update/delete/add are full snapshot rebuilds with a
published generation pointer, not fake incremental support or stale score masks.
Verify mutation visibility, stable IDs, metadata, deletion and reload; compare
post-mutation search with a clean rebuild, including newly introduced vocabulary.
Future dual-index freshness/generation coordination is architecture work for a
later approved task; no production Chroma/lexical transaction claim is made.

Use scripts/run_isolated.py for tests and evaluation. Optional dependency path:
`$env:PYTHONPATH="$PWD\runtime\lexical-deps"`. Keep every experimental index in
the runner's temporary work directory. Retain only reports, compressed cache and
logs under docs/reports. No production Docker changes, commit, push, reset or clean.

Capability-audit clarification (before quality analysis): because `/version` is
hardcoded and a `/search` route exists even on an unsupported executor, a single
temporary container from the exact running image digest is necessary to verify
native Search capability without accessing production collections. Use --pull=never,
an empty tmpfs, localhost-only port, 1 CPU/512 MiB, then stop/remove only that owned
container. Do not create a persistent service or change any production container.

Method audit after the first quality run: the evaluator had sorted IDs before
inserting all backends, changing HNSW insertion order relative to the old stress
generator. Preserve that first artifact as a sensitivity observation, restore
original corpus order uniformly for dense indexing, and rerun without changing
tokenization, BM25 parameters, HNSW settings, embeddings or labels. Add exact
float64 cosine diagnostics on the stress corpus to distinguish embedding rank
from approximate-index omissions. This is a retrieval-method correction, not
per-query tuning or a proposed production ranking change.
