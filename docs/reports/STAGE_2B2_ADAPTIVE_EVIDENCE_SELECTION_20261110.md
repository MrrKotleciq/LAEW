---
type: report
title: Stage 2B.2 adaptive retrieval and evidence selection
date: 2026-11-10
status: experimental-pending-review
scope: isolated model-free RAG evidence selection
---

# Stage 2B.2 — Adaptive retrieval and evidence selection

**Decision: keep production unchanged.** Broader retrieval with variable fragment
counts repairs substantial labeled-evidence loss, but increases irrelevant context
and does not establish answer quality. The redundancy-aware selector does not
consistently beat simple ranked filling. Proposed architecture: separate authorized
candidate retrieval, eligibility, selection, allocation and attributed rendering.
For further isolated validation, use **legacy / K10 per scope / ranked_fill /
1000 estimated tokens per scope**, with a hard overall manifest RAG allocation.
This is a review candidate, not an approved production default or deployment.

## Confirmed implementation

- `KnowledgeTurn._prefetch` requests `max_results=2` and a private 500-token budget
  separately for each routed scope. Routing can choose no scope. `RagTool` passes
  these limits to the pipeline; normal follow-up searches have separate behavior.
- `RAGPipeline` defaults to K5, cosine >=0.3 and 8000 estimated context tokens.
  `_rerank` only filters and stably sorts cosine; the manifest's `reranking: true`
  does not enable a learned model. Legacy is the `KnowledgeBase` constructor and
  runtime default; structure-v1/v2 require explicit experimental construction.
- Retrieval checks embedding identity; fresh runtime retrieval acquires scope
  synchronization locks and verifies current generations before using stores.
  Project allowlists, global exclusions, scope authorization and project-specific
  collections remain outside the selector and unchanged. Direct generic HYBRID
  retrieval currently merges scopes before cosine sorting; this experiment uses
  separate scope calls and does not adopt that cross-scope ranking behavior.
- `_build_context` includes provenance, section paths, tags, backlinks, selected
  frontmatter and separators. It can clip the first oversized fragment, then skips
  later fragments that do not fit. Its count is ceil(characters/4).
- Manifest allocation is RAG=8000, total=18000, with a default 2000 response reserve.
  Executor appends knowledge to the system message and trims older history; it
  preserves system/current user content. It does not independently enforce a hard
  RAG section ceiling. The experimental allocator explicitly caps the rendered
  RAG section, including enclosing labels, before replay.

Reviewed ADR-003/004/006/011, all four requested Stage 2B.2 reports, the previous
benchmark protocol, source code and existing evaluator/replay machinery. No public
RAG contract, routing behavior or source-security boundary was modified.

## Method and data

Reuse the immutable historical pool hash
`4cfc7e69ae22712ec12c84318b14efb55cb1f2523d6a91074227a34ab8b87610`:
baseline_v1 (28 queries), hard_cases_v1 (13), reranker_holdout_v1 (32).
The holdout remains only six connected topic/source groups. K10/K20 are separate
historical Chroma searches. Historical K5 is explicitly a K10 prefix, not a fresh
K5 latency measurement. No old label/artifact was changed.

Add `evidence_supplement_v1`: 20 questions, 16 answerable and four unsupported,
PL/EN/DE, eight documents. Labels were authored from sources and frozen before
retrieval/scoring, independently of ranked outputs. They are **not independently
judged by another human**. Public paraphrases use
[SQLite WAL](https://www.sqlite.org/wal.html),
[PostgreSQL isolation](https://www.postgresql.org/docs/current/transaction-iso.html),
[Git revert](https://git-scm.com/docs/git-revert) and
[CMake custom commands](https://cmake.org/cmake/help/latest/command/add_custom_command.html).
Atlas's long maintenance manual and conflicting R6/R7 release procedures are
explicitly fictional. The supplement covers prerequisites, multiple sections,
same-document/multi-document evidence, hybrid scope and cross-language questions.
Legacy indexes 29 global + 6 project chunks; v2 indexes 23 + 4. Actual K2/5/10/20
searches were captured; every actual K2 pool matches the K20 first-two prefix.
Its source-linked questions add breadth, not statistical independence.

Protocol: `tools/evidence_selection/PROTOCOL.md`. At 1000 tokens compare K5/10/20;
at K20 compare 500/2000 and diagnostic-only 5000. All three policies use identical
candidate pools, original cosine scores, metadata and >=0.3 eligibility per scope:

1. **A top2:** unchanged stable cosine order, at most two, exact existing renderer.
2. **B ranked_fill:** full cosine ranking, admit fragments with the existing renderer.
3. **C novelty:** anchor on highest-ranked fitting whole fragment, then maximize
   `(relevance * (1 - lexical_overlap) - .15 * lexical_overlap) /
   sqrt(1 + attributed_tokens / 256)`, stopping at utility <=.05. Unicode token-set
   Jaccard measures overlap with selected fragments. No model, filename/query/atom
   exception, document quota or inferred query complexity. Whole-fragment admission
   avoids clipping prerequisites but may skip useful oversized material.

The selector preserves metadata/attribution and cosine. Optional explicitly
normalized scope-local relevance scores allow a future scorer without replacing
the cosine eligibility gate; a pool cannot mix supplied relevance with cosine
ranking. Bounds are 128 candidates and one million input
characters including metadata; invalid scores, duplicate IDs or mixed scopes fail
closed. Input order resolves ties. Incremental overlap updates bound time to
O(K²L), memory to O(KL). Caller authorization/freshness is a precondition; a source
string is not an authorization mechanism. Related section context is preserved
through whole fragments and the existing renderer; there is no semantic graph or
automatic prerequisite expansion. Cross-language duplicates and contradictions
are not understood by lexical overlap.

Equal scope allocation reserves wrappers/separators before applying per-scope
ceilings; unused allocations are not redistributed. Scores are never compared
across scopes. Budgets are transparent and fixed; fragment count is adaptive.
Summary costs below include outer labels, unlike older passage-only reports.
Hybrid total usage can exceed a single per-scope ceiling while respecting 8000.
The historical K20/top2/500 control audit matches all 146 query/chunker cases in
atom coverage, inner rendered token cost and fragment order within each scope.
Four hybrid cases change only outer scope order (sorted global then project);
no scores are merged. The separate renderer tests cover first-fragment clipping.

## Quality and context cost

K20 / 1000 tokens per scope. Coverage is macro exact labeled-atom recall over
answerable questions; costs/counts include unsupported queries. These are not
correct-answer scores. A fragment with no labeled atom can contain useful unlabelled
background; document irrelevance uses the frozen qrels.

| Dataset | Chunker | Coverage A / B / C | Complete B / C | Mean RAG tokens A / B / C |
|---|---|---|---|---|
| baseline | legacy | 81.25 / 100 / 100% | 100 / 100% | 116 / 473 / 473 |
| baseline | v2 | 91.67 / 100 / 100% | 100 / 100% | 116 / 518 / 518 |
| hard | legacy | 86.36 / 100 / 97.73% | 100 / 90.91% | 180 / 812 / 763 |
| hard | v2 | 92.42 / 100 / 96.97% | 100 / 90.91% | 259 / 817 / 768 |
| holdout | legacy | 80.36 / 94.64 / 92.86% | 89.29 / 85.71% | 229 / 1005 / 983 |
| holdout | v2 | 82.74 / 96.43 / 96.43% | 92.86 / 92.86% | 332 / 992 / 981 |
| supplement | legacy | 70.83 / 100 / 100% | 100 / 100% | 130 / 825 / 825 |
| supplement | v2 | 86.46 / 100 / 100% | 100 / 100% | 217 / 872 / 868 |

| Holdout, K20 | Budget/scope | Coverage B / C | Mean tokens B / C |
|---|---|---|---|
| legacy | 500 | 91.07 / 91.07% | 528 / 530 |
| legacy | 1000 | 94.64 / 92.86% | 1005 / 983 |
| legacy | 2000 | 100 / 100% | 1629 / 1628 |
| v2 | 500 | 89.88 / 92.86% | 493 / 489 |
| v2 | 1000 | 96.43 / 96.43% | 992 / 981 |
| v2 | 2000 | 100 / 100% | 1802 / 1802 |

At 500, hard B coverage is 88.64% legacy / 96.97% v2; C is 89.39% / 93.94%.
At 500, supplement B already reaches 100% for both chunkers; C/v2 loses one
half-query atom, giving 96.88%. More budget cannot bypass A's fixed two-fragment
limit. At 2000/5000, B/C reach 100% fixture coverage in all datasets. This is an
evidence ceiling on small authored corpora, not production retrieval/answer proof.
Diagnostic B/5000 averages 1661 legacy and 2327 v2 holdout tokens. It is not a default.

| Holdout, 1000/scope | Candidate atom coverage K5 / K10 / K20 | B final K10 / K20 | B mean tokens K10 / K20 |
|---|---|---|---|
| legacy | 87.50 / 96.43 / 100% | 94.64 / 94.64% | 872 / 1005 |
| v2 | 96.43 / 100 / 100% | 96.43 / 96.43% | 982 / 992 |

The supplement has 96.88% candidate coverage at K5, 100% at K10/K20 for both
chunkers. All historical K20 atoms remain eligible, reproducing the previous
availability finding; it does not establish scalability. K20 can hurt C: holdout
legacy 96.43% at K10 becomes 92.86% at K20, v2 98.21% becomes 96.43%. Additional
candidates consume budget without guaranteed extra evidence. No default winner
can be inferred from raw candidate recall alone.

At K10/B/1000, holdout complete evidence is 89.29% legacy / 92.86% v2;
multi-document coverage is 78.57% / 85.71%. Token p95 is 1033 / 1245 across scopes.
The full summary CSV includes mean/median/p95/max costs, fragment/document counts,
atom-per-token ratios, irrelevant/no-atom/overlap rates and loss stages.

## Regressions, diversity and no-answer behavior

K20/1000 B and C have no final atom-coverage regression against A across these
four datasets, but **C regresses against B**: legacy h09 is 75% instead of 100%;
v2 h04 is 66.67% instead of 100%; holdout legacy u20 is 50% instead of 100%.
V2 C trades u27's recovery for u20's loss. Cases are budget/marginal-order effects,
not repairs encoded in the algorithm. h03 retains all prerequisites, h05 improves
legacy 66.67→100%, and v2 h11 improves 50→100% under both B/C. h04 legacy reaches
100%; h09 v2 retains 100%. Frozen labels and the selector were not retuned.

B still misses legacy u22/u24/u27 and v2 u22/u27 at 1000, all budget losses.
Candidate availability, selection and adapter delivery are recorded separately
per atom, including availability anywhere in the isolated index. Every query's
selected IDs, scores, metadata and rejection decisions remain in the details gzip.

At K20/500, baseline multi-document coverage rises from A 62.5/75% to B/C 100%
(legacy/v2); v2 h11 recovers both sources. The supplement includes both multiple
sections of Atlas and hybrid release prerequisites/validation; B/500 covers all
labels. There is no one-fragment-per-document cap. Mean fragment counts at
K20/1000 are B 12.38 legacy / 6.91 v2 on the holdout, compared with A 2.12
(two per scope, sometimes hybrid). Multiple same-document fragments survive.

The context expansion is substantial: holdout B's qrel-irrelevant fragment rate
at 1000 is 74.2% legacy / 67.4% v2, versus A 29.4% / 41.2%. C gives 77.4% / 68.3%.
No >80% token-set overlap remains in these selected fixture fragments, so near-copy
removal has little opportunity to help; substring overlap and semantic redundancy
are not ruled out. C sometimes reduces cost by dropping redundant/low-utility
material, but does not solve irrelevant unique passages admitted by cosine >=.3.
This contradicts a claim that variable count alone makes evidence context efficient.

No-answer empty rate is 25% on baseline and 0% on hard, holdout and supplement
for all policies at these settings. Zero eligible candidates correctly produces
zero output in tests, but eligibility still admits distractors for unsupported
questions. No unvalidated abstention threshold was invented. Similar/superseded
sources remain a source-of-truth risk; keeping approved evidence does not prove
that a generator will disregard conflicting archived material.

## Delivery, performance and scale

3348/3348 contexts reached the real AgentExecutor and llama.cpp serializer with
mocked transport/response, no history/tools and fixture-forced scopes. No RAG
allocation violation occurred; maximum rendered RAG usage was 4310 estimated
tokens, including diagnostic conditions. Unit tests also exercise cap pressure
at 0/1/100/8000 and both scopes. This is not end-to-end routing or answer testing.

Exact tokenization was attempted against existing localhost:8080 `/tokenize`,
but `/v1/models` refused the connection. No chat service was started. Exact content
tokens and full chat-template tokens remain unmeasured. Estimated allocation
compliance does not establish model-token compliance or prefill latency.

Selector probes use h03 passages, 30 repetitions after warmup; Python memory peaks
are measured separately with tracemalloc, excluding native/pre-existing allocations.
K128 is a synthetic expansion for selector bounds, not retrieval quality.

| Chunker / policy | K5 median ms | K10 median ms | K20 median / p95 ms | K128 median ms | K20 / K128 Python peak bytes |
|---|---|---|---|---|---|
| legacy A | .021 | .035 | .062 / .065 | .351 | 2776 / 12287 |
| legacy B | .024 | .045 | .106 / .110 | 2.475 | 9397 / 16544 |
| legacy C | .121 | .314 | .664 / .676 | 8.881 | 40973 / 257046 |
| v2 A | .036 | .060 | .111 / .116 | .659 | 2776 / 11793 |
| v2 B | .038 | .075 | .148 / .154 | 2.083 | 9089 / 15936 |
| v2 C | .211 | .399 | .720 / .744 | 7.311 | 54235 / 316105 |

These are bounded local processing costs, not end-to-end RAG latency. B's repeated
renderer bookkeeping at K128 remains small in absolute time. No model inference
or new dependency is involved in selection; the previous learned reranker serving
costs are not directly remeasured here.

Scalability diagnostic: **1036 real embedded chunks** (12 legacy Atlas fragments
plus 1024 generated engineering distractors), a disposable local PersistentClient,
existing manifest embedding model/dimensions. Embedding took 506.27s, Chroma upsert
.643s, index files 10,775,680 bytes. Embedding preparation overlapped the offline
regression suite; it is not a clean embedding throughput measurement. Query probes
and final selector timing ran after that suite finished. Four Atlas questions
(three answerable, one unsupported), 20 warm searches per K after warmup:

| K | Range of query median retrieval ms | Range of query p95 ms |
|---|---|---|
| 2 | 1.841–2.262 | 2.205–2.473 |
| 5 | 1.910–2.183 | 2.151–2.543 |
| 10 | 1.965–2.263 | 2.318–2.575 |
| 20 | 2.289–2.558 | 2.650–3.078 |

Paired median overhead K20 versus K2 is .296–.510ms (about 13–28%) in this local
index, excluding query embedding and remote-server transport. It does not measure
production-server overhead or million-document behavior.

Crucially, the complex Polish Atlas prerequisite/acceptance query s14 has only
**33.33% raw and eligible atom coverage at every K, including K20**, versus 100%
at K10/K20 in the small supplement. B consequently also delivers only 33.33%.
The distractors deliberately share engineering/Atlas terms but contain no required
atoms. The other two supported Atlas questions retain complete candidate evidence;
the unsupported torque question receives context. This shows candidate retrieval
can fail before selection when the corpus grows. A fixed broad K is not a guarantee
of sufficient evidence. This is synthetic retrieval stress, not independent quality
judgment or a natural production workload; only legacy is tested in this phase.

Validation: the focused selector/evaluator/old-evaluator suite passed **41 tests**;
full offline `tests -m 'not live and not ollama'` passed **1545**, with **4 skipped,
2 deselected and 39 warnings**, in 205.19s. The final normalized-score input guard
was subsequently checked by another 41-test focused pass; all quality runs
and selector performance were then regenerated with final code. A final 41-test
pass including an overfilled two-scope 8000-token cap check took 1.55s. Initial sandbox
execution failed at pytest temporary-directory setup (WinError 5, 18 setup errors);
the same isolated runner outside that filesystem sandbox succeeded. No assertions
were weakened. Logs are saved alongside the artifacts; no live-model test ran.

## Recommendation, migration and rollback

1. K2 is a significant selection bottleneck. Variable counts improve fixture
   coverage, but B/C can spend 3–6 times the context and admit much irrelevant text.
2. K10/B/1000 is the simplest **next validation configuration**, with K20 reserved
   for candidate-availability diagnostics. Fixed budgets are more defensible than
   query-complexity heuristics here. No tested selector meets a deployment claim
   of reliable sufficiency, no-answer handling and context efficiency.
3. C is fast but not consistently better than B. Do not expand this into a tuning
   framework or promote lexical novelty as semantic evidence utility.
4. V2 often packs more necessary evidence into the first two fragments; legacy
   reaches the same B coverage with lower cost on hard/supplement. Holdout v2 has
   slightly better B coverage but greater K10 cost. Do not switch chunking defaults.
5. Before deployment: independently judged natural multilingual queries from an
   approved representative corpus, document/version conflict judgments, larger
   real embedding/index tests, exact tokenizer calibration, history/tools budget
   pressure, actual generated-answer/citation assessment and security/freshness
   integration under concurrent synchronization. Current authored data and one
   stress corpus cannot establish statistical significance or large-vault quality.

If subsequently approved, introduce a disabled configuration switch outside public
tool schemas; keep authorized retrieval and freshness locks intact; allocate the
overall cap before rendering; test shadow selection with approved data, then a
limited opt-in rollout. Broader K on unchanged legacy chunks requires no reindex.
Rollback should disable the selector and restore top2/500 with the same index and
model. A future v2 migration separately requires a new isolated index, full sync,
generation validation and coordinated runtime/sync cutover, retaining the old index
and reconciling source changes before rollback. No switch or migration was implemented.

## Files, artifacts and reproduction

Implementation: `laew/rag/evidence_selection.py` (experimental only),
`laew/eval/evidence_selection_benchmark.py`. Tests:
`tests/rag/test_evidence_selection.py`,
`tests/evaluation/test_evidence_selection_benchmark.py`.
Protocol/generator: `tools/evidence_selection/{PROTOCOL.md,build_fixture.py}`.
New dataset: `tests/rag/evidence_supplement_v1/` (eight source Markdown files,
`dataset.json`, `FREEZE.json`, `README.md`). Documentation: this report and its
entry in `docs/README.md`. New artifacts use `evidence-selection-20261110-*`.
The final state JSON records exact paths, hashes, commands and Git status.

Use `.venv\Scripts\python.exe scripts/run_isolated.py --keep-diagnostics eval
laew.eval.evidence_selection_benchmark <phase> --output docs/reports/<new-file>`.
Phases: `prepare-supplement`, `analyze --input <old-pool.gz> <supplement-pool.gz>`,
`performance --input <old-pool.gz>`, `scale --distractors 1024 --repeats 20`,
`tokenize --input <supplement-pool.gz>`, `export --input <details.gz>`.
Use absolute input paths because the runner changes cwd. Outputs remain inside
the printed temporary run directory; copy only benchmark artifacts to this report
directory. No production collections, SQLite Memory, vaults, Smart Connections,
allowlists, model settings, Horizon or reranker services were changed or started.
No paid APIs, destructive Docker actions or Git mutations were used.
