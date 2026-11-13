---
type: report
title: Stage 2B.2 lexical retrieval backend evaluation — Task 1
date: 2026-11-10
status: experimental-pending-task-2-approval
scope: isolated dense cosine, SQLite FTS5 and BM25S candidate retrieval
---

# Stage 2B.2 — Lexical retrieval, Task 1/3

**Recommend SQLite FTS5 as the lexical backend for the next design stage.** Its
transactional incremental changes suit a changing Second Brain better than
BM25S's whole-corpus score snapshots. BM25S wins search speed and active disk size
here; FTS5 has a small quality advantage on legacy holdout. Neither replaces dense
retrieval, fixes cross-language retrieval generally, or repairs stress-case s14.
No fusion, production integration, routing/default/model change or index migration
was implemented. Task 2 requires user approval.

## Architecture and actual Chroma capability

Observed local Python client: **chromadb 1.5.9**. Running container binary:
**`chroma 1.4.4`**, image digest
`sha256:1e0b73a187a28757c572acba508c46f48c9e8b0acaf5c20e6d95cdedce1acdf6`.
Compose says `latest`, which is not reliable version evidence. `/api/v2/version`
returns `1.0.0`; the [Rust frontend source](https://github.com/chroma-core/chroma/blob/1.5.9/rust/frontend/src/server.rs)
hardcodes that value. Binary/client/API versions are recorded separately rather
than falsely claiming the server release equals the endpoint value.

The actual server advertises a `/search` route, but capability is **unavailable
for its local executor**. A one-off container from the exact existing image,
`--pull=never`, localhost:18099, 1 CPU/512 MiB and empty `/data` tmpfs, accepted a
fictional explicit-vector `query()` and rejected `search()` with:
`Search operation is not implemented for local executor`.
It was stopped/automatically removed. No host data was mounted and no production
collection was accessed. This transient diagnostic was necessary to distinguish
an advertised endpoint from functionality. A disposable 1.5.9 PersistentClient
also raises `NotImplementedError`. This agrees with the
[Search API availability documentation](https://docs.trychroma.com/cloud/search-api/overview).
Cloud hybrid/BM25 features must not be assumed available in this deployment.

Existing `ChromaVectorStore.search` uses `collection.query(query_embeddings=...)`,
converts distance to `1-distance`, and restores original chunk IDs/text/metadata.
Classic `where_document` filtering is not BM25 ranking.
Generic project/global stores are distinct; project collection identity depends
on project root, with post-query source checks. Legacy IDs contain source, relative
path, section/chunk ordinals; v2 adds strategy and chunk ordinal, preserving section,
span/block and note metadata. IDs identify stable slots, not immutable semantic
content: an edited section can replace text under the same ID.

Synchronization prepares changed document chunks/embeddings before upsert and
deletion of obsolete IDs. Fingerprints include source/chunker/model identity.
Runtime freshness checks use process/scope locks and complete generation markers;
the Chroma upsert/delete pair is not a cross-store transaction. Experimental
`evidence_selection.py` remains separate, scope-local and unused by production.
This task ends at candidate retrieval, without invoking its policies or context
budgets. A future lexical index must participate in the same approved source and
generation boundaries; these adapters do not supply authorization or dual-index
atomicity.

## Implementations and tokenization

| Property | SQLite FTS5 | BM25S 0.3.15 |
|---|---|---|
| License | [SQLite public domain](https://sqlite.org/copyright.html) | [MIT](https://github.com/xhluca/bm25s/blob/0.3.15/LICENSE) |
| Dependencies | Python sqlite3; local SQLite 3.50.4 has ENABLE_FTS5 | Existing NumPy; no extras, SciPy, Numba, JAX or language model |
| Ranking | Native negative `bm25()`, ascending | Positive Lucene BM25, descending, NumPy backend |
| Configuration | Built-in k1=1.2, b=.75 | Fixed k1=1.2, b=.75; no auto compilation |
| Persistence | One database, payload table + external-content FTS and triggers | Arrays/vocabulary + original record JSON, memory-mapped reload |
| Changes | Native transactional upsert/delete; fresh global statistics at query time | No native add/update/delete methods in this pinned version; full rebuild |
| Experimental publication | SQLite transaction | New generation, then atomic CURRENT.json replacement; old snapshots retained |

[FTS5's documentation](https://sqlite.org/fts5.html) describes its ranking and
external-content maintenance. Its IDF clamps nonpositive values to a small floor;
BM25S's Lucene IDF stays positive for frequent terms. Thus the shared k1/b settings
do not make rankings or score scales numerically equivalent. BM25S eagerly
precomputes corpus-dependent scores; its [pinned implementation](https://github.com/xhluca/bm25s/blob/0.3.15/bm25s/__init__.py)
has save/load/mmap but no mutation API. Masking deleted documents would leave stale
statistics, so the adapter deliberately rebuilds.

Both receive identical language-neutral tokens: Unicode NFKC, casefold, Unicode
word runs including underscores, single letters and numbers; no stemming, accent
folding or stoplist. Only chunk text is indexed, not extra filename/qrel features.
Original text, stable ID, scope, path and complete metadata remain separate.
Independent corpus/scope/project bindings reject mismatched reloads and mixed-scope
input; they also prevent unrelated scopes from sharing IDF statistics. Callers
must still establish authorization/freshness before providing records.

FTS stores ASCII hex encodings of the normalized tokens, ensuring its native
tokenizer sees the same token stream as BM25S. Queries become quoted literal
tokens joined by adapter-owned OR, passed through SQL parameters. Raw user text
never becomes FTS syntax. Queries beyond 4096 characters or 128 unique terms are
rejected explicitly. This encoding adds storage/processing overhead; results are
for this safe shared-tokenizer adapter, not the fastest possible unicode61 setup.
BM25S uses public `get_scores`, positive matches only, and a stable full sort of
matches; its measured adapter cost includes this O(M log M) tie-safe step.

Regression probes establish: `sample_rate` is retained, `sample` does not match it;
`net.http`/`foo::bar` split; `C++` and `C#` both reduce to `c`; composed/decomposed
`café` agree, unaccented `cafe` stays distinct; `ŻÓŁĆ` casefolds consistently and
`Straße` becomes `strasse`. Code-symbol collisions and morphology/translation gaps
are real limitations, not repaired with case-specific rules.

## Method

Protocol: `tools/lexical/PROTOCOL.md`, recorded before lexical scoring. Reuse all
four frozen datasets and both legacy/v2 full corpora, rebuilding with the existing
KnowledgeBase, local embedding model and 1024 dimensions. Do not index merely the
old dense top-K union. Verify existing freezes, preserve IDs/synchronization
metadata, and cache all vectors/queries in `lexical-20261110-corpus.json.gz`.
The previous 1036-chunk stress corpus reproduces its exact recorded text/metadata
hash: 12 Atlas fragments + 1024 synthetic engineering distractors. No new model
was downloaded. Preparation overlapped offline tests; it is not a clean embedding
throughput experiment.

Actual K5/10/20/50 searches are per scope and capped by available/matching counts.
Compare dense raw candidates, dense eligible cosine >=.3, FTS5 and BM25S; **no
cosine threshold is applied to either BM25**. Zero-score padding is omitted.
There are 3040 query/backend/K rows: 186 fixture query/chunker pairs and four stress
queries. No final selector, rendering budget, generated answer or hybrid fusion
is evaluated. Each dataset remains separate; the small authored holdouts share
sources and do not justify statistical significance.

Search timing: warmup + 20 repetitions, including tokenization/ranking/hydration;
exclude dense query embedding, using the cached vectors. Timing/resource runs
started after our embedding/test workloads finished. Reported latency medians are
medians of per-scope query medians, not full production request latency. Fresh
sequential subprocesses measure build, reload and native-inclusive working set.

## Candidate quality and regressions

K20, macro evidence-atom coverage over answerable queries; dense raw and eligible
coverage coincide here. These are candidate-availability scores, not answer scores.

| Dataset | Chunker | Dense | FTS5 | BM25S | FTS5 / BM25S complete evidence |
|---|---|---|---|---|---|
| baseline | legacy | 100% | 64.58% | 64.58% | 62.50 / 62.50% |
| baseline | v2 | 100% | 64.58% | 64.58% | 62.50 / 62.50% |
| hard | legacy | 100% | 81.82% | 81.82% | 81.82 / 81.82% |
| hard | v2 | 100% | 81.82% | 81.82% | 81.82 / 81.82% |
| holdout | legacy | 100% | 82.74% | 80.95% | 75.00 / 75.00% |
| holdout | v2 | 100% | 85.71% | 85.71% | 82.14 / 82.14% |
| supplement | legacy | 100% | 84.38% | 84.38% | 81.25 / 81.25% |
| supplement | v2 | 100% | 84.38% | 84.38% | 81.25 / 81.25% |
| stress | legacy | 77.78% | 33.33% | 33.33% | 33.33 / 33.33% |

| Holdout | Backend | Coverage K5 / K10 / K20 / K50 |
|---|---|---|
| legacy | dense eligible | 87.50 / 96.43 / 100 / 100% |
| legacy | FTS5 | 70.24 / 75.60 / 82.74 / 87.50% |
| legacy | BM25S | 70.24 / 73.81 / 80.95 / 87.50% |
| v2 | dense eligible | 96.43 / 100 / 100 / 100% |
| v2 | FTS5 or BM25S | 70.24 / 77.38 / 85.71 / 89.29% |

At K20, both lexical backends have 100% document recall on holdout, yet lose
necessary sections/atoms. FTS5 multi-document atom coverage is 73.81% legacy /
85.71% v2, versus BM25S 66.67% / 85.71% and dense 100%. Baseline FTS5 multi-document
document recall is 87.5%, atom coverage only 62.5%; supplement is 75% for both.
Document recall alone would conceal missing evidence.

FTS5 cross-language K20 atom coverage: baseline 39.29%, hard 0%, holdout
65.48/71.43% legacy/v2, supplement 72.22%; dense is 100% on these small corpora.
Holdout legacy FTS5 PL/DE/EN coverage is 81.25/92.86/78.21%; BM25S
81.25/92.86/74.36%. Neither language-neutral lexical backend translates queries.

Concrete K20 FTS5 losses versus dense include hard h06/h08 (100→0), holdout
u06/u08/u12 (100→0), legacy u21 (100→66.67), u22/u24/u27 (100→50), and supplement
s04/s06 (100→0), hybrid s12 (100→50). At K5 lexical retrieval adds one useful
counterexample: legacy u17 is complete under FTS5 while dense has 0% evidence.
That is a candidate-complementarity observation, not a tested fusion gain.

Between lexical backends, legacy u20 has atom ranks FTS5 [10,9], BM25S [10,11],
so K10 coverage is 100% versus 50%. Legacy u24's Polish acknowledgement passage
ranks 20 with FTS5, 22 with BM25S; its German timing atom has no lexical match.
At K20 coverage is 50% versus 0%. Both differences disappear at K50. There is no
other atom-coverage difference between the lexical backends in this grid; ranking
differences beyond these labels can still exist. No parameters were retuned.

Unsupported-query empty rate: 25% on baseline and 0% on hard/holdout/supplement/
stress for both lexical backends and eligible dense at K20. FTS5 returns means of
2.25, 15.5/20, 14.75/14, 12.25/12 and 20 unsupported fragments respectively.
Literal matching is not an abstention or relevance guarantee; common words still
retrieve irrelevant candidates. No new no-answer threshold was introduced.

## s14 and approximate-index diagnostic

All three s14 atoms exist in the full index. In the small legacy supplement,
dense/FTS5/BM25S atom ranks are [1,4,4]. In stress, dense ranks are **[1,66,66]**;
both lexical backends rank them **[1025,1028,1028]**. Exact float64 normalized cosine
also places them [1,66,66]. Thus K5–50 dense coverage remains 33.33%, lexical 0%.
The two acceptance atoms share a fragment. Numerous synthetic distractors repeat
Atlas/firmware terms; the Polish query provides little lexical discrimination.
Increasing K to 50 or changing final selection does not recover missing candidates.

An initial evaluator run sorted IDs before insertion, changing the original stress
generator order. That HNSW index missed German s16 through K50, even though its
exact cosine atom rank is 3. The final run restores original corpus insertion order
uniformly and recovers s16 (as in the previous experiment); its exact diagnostic
agrees. The initial artifact is retained as `*-id-sorted-insertion-details.json.gz`.
This demonstrates an approximate-index omission and sensitivity to index construction;
it is not a controlled ablation separating insertion order from index randomness.
No HNSW setting, embedding, label or lexical parameter was changed. The s14 failure
persists in both runs and in exact cosine. Synthetic stress is not independent
industrial relevance evaluation or proof about million-document behavior.

## Search, storage, RAM and updates

K20 warm search, median of query medians / median of query p95 values in ms:

| Corpus | Dense | FTS5 | BM25S |
|---|---|---|---|
| holdout legacy | 2.832 / 3.160 | .616 / .741 | .197 / .228 |
| holdout v2 | 3.857 / 4.246 | .652 / .710 | .264 / .290 |
| stress legacy | 2.245 / 2.651 | 2.032 / 2.338 | .156 / .166 |

BM25S is faster for search; FTS5 remains inexpensive here. Cached dense query
embedding is excluded from this table, so these are not equal end-to-end language
query costs. Full per-query timing distributions and embedding observations are
retained in the cache/details; cold model inference was not benchmarked.

Fresh resource probes, one build and one observation per mutation (descriptive):

| Corpus/backend | Build/publish ms | Reload ms | Active / retained bytes after changes | Warm working-set increase MiB |
|---|---|---|---|---|
| 52 chunks FTS5 | 7.4 | 1.6 | 155648 / 155648 | 1.40 |
| 52 chunks BM25S | 41.0 | 62.1 | 79014 / 315767 | 4.76 |
| 52 chunks dense | 86.3 | 36.5 | 977060 / 977060 | 63.27 |
| 1036 chunks FTS5 | 92.2 | 1.9 | 1744896 / 1744896 | 4.57 |
| 1036 chunks BM25S | 70.5 | 51.3 | 940004 / 3759693 | 8.88 |
| 1036 chunks dense | 466.2 | 73.3 | 10779776 / 10779776 | 68.27 |

Backend import/open is separate (about 21–24ms FTS5, 46–127ms BM25S, 1010–2312ms
dense). Working-set increases are measured after loading the same cached payload
and before backend import, including native allocations; they are not exact index
heap sizes. Stress warm totals are 95.8/100.3/159.7 MiB FTS5/BM25S/dense. Lifetime
peaks include JSON payload parsing (~196–219 MiB), so they must not be called index
RAM. Separate tracemalloc build peaks are 1.58/5.85/37.15 MiB, excluding native
SQLite/NumPy/Chroma allocations. This is not a large-corpus memory bound.

| Corpus/backend | Add ms | Update ms | Delete ms | Clean rebuild ms |
|---|---|---|---|---|
| 52 FTS5 | 3.41 | 2.92 | 2.94 | 8.15 |
| 52 BM25S | 11.14 | 11.71 | 10.25 | 11.01 |
| 1036 FTS5 | 4.67 | 3.99 | 4.00 | 92.05 |
| 1036 BM25S | 59.43 | 58.24 | 59.50 | 57.49 |

All mutation visibility, clean-rebuild equivalence and reload checks passed. New
vocabulary, updated metadata/path and removed postings are checked. FTS5 failures
roll back payload/postings together. BM25S failed-publication tests retain the old
pointer. Its snapshot replacement is atomic visibility in this single-writer
experiment, not a power-loss durability or concurrent-writer guarantee. Four
snapshots remain after the initial build and three mutations; no garbage collector
or generation coordination with Chroma was introduced. FTS5 uses ordinary rollback
journaling, not an untested production WAL/concurrency configuration. Dense mutation
performance was not measured; its existing synchronization was reviewed instead.

## Decision, limits and deliverables

FTS5 wins this backend decision because incremental transactional changes avoid
BM25S's whole-corpus recomputation, extra snapshot lifecycle and score-staleness
risks, while preserving comparable/slightly better labeled recall. Its measured
search/disk penalties are acceptable for further design, not proven acceptable
at Second Brain scale. BM25S remains a credible option for mostly static, batched,
search-heavy corpora; its faster query time and smaller active index are real.
Do not promote either to standalone multilingual retrieval or assume future fusion
will recover s14. Independently judged natural queries, larger real corpora, code
tokenization trade-offs and concurrent synchronization/recovery need further work.

Tests: full offline suite **1569 passed, 4 skipped, 2 deselected, 39 warnings** in
195.63s. After the insertion-order/exact-cosine method correction, **65 focused
tests passed** in 5.00s, including the old evaluators and evidence selector. No
assertion was weakened. All tests/evaluations used `scripts/run_isolated.py`.

New code: `laew/rag/lexical_experiment.py`, `laew/eval/lexical_benchmark.py`.
New tests: `tests/rag/test_lexical_experiment.py`,
`tests/evaluation/test_lexical_benchmark.py`. Protocol/dependency pin:
`tools/lexical/{PROTOCOL.md,requirements.txt}`. BM25S is installed only in ignored
`runtime/lexical-deps`, not in production dependencies. Documentation: this report
and its `docs/README.md` entry. Artifacts use `docs/reports/lexical-20261110-*`:
architecture/native capability, corpus cache, initial/final details, summary/query
CSV, resource observations, logs, initial/final state and file hashes.

Reproduce with the pinned optional package on PYTHONPATH, then run
`scripts/run_isolated.py --keep-diagnostics eval laew.eval.lexical_benchmark`
using phases `prepare --previous-stress <old-scale.json>`, `benchmark --input
<corpus.json.gz> --repeats 20`, `resources --input <corpus.json.gz>`, and `export
--input <details.json.gz>`, each with `--output docs/reports/<new-file>`.
Inputs must be absolute because the runner changes cwd. Copy only resulting
artifacts from the printed run directory; keep actual indexes temporary.

Final state JSON records exact paths, hashes, commands, preserved initial changes
and Git status. Existing Docker Compose changes and previous experiment artifacts
were preserved. No production ChromaDB, SQLite Memory, vault/Smart Connections,
Horizon/reranker, source allowlist or main/embedding model was modified. No model
downloads, paid inference, commit or push occurred. **Stop here pending approval
of FTS5 as the backend for Task 2.**
