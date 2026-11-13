# Stage 2B.2 model-free evidence selection protocol

Recorded 2026-11-10 before selection quality runs. Production stays unchanged.

Reuse the immutable 2026-11-09 captured cosine pools and labels for baseline_v1,
hard_cases_v1 and reranker_holdout_v1. K10 and K20 are actual separate historical
Chroma searches. K5 is a prefix of captured K10, explicitly NOT a measured K5
retrieval. Do not infer fresh retrieval latency from historical captures.
Compare all three selectors on identical scope-local pools, cosine >= 0.3.

Stage 1: K5/10/20, 1000 estimated tokens/scope, all policies and both chunkers.
Stage 2: K20 at 500/2000; 5000 is a diagnostic ceiling only. Retain all three
policies as controls; no parameter tuning or query-specific exceptions after
examining labels/results. Policy A is exact top2 plus the existing renderer;
B is the full cosine ranking plus that renderer; C is whole-fragment lexical
marginal utility with fixed penalty .15, stop utility .05 and sqrt cost penalty.
C anchors the first whole fragment by relevance. No per-document quota, document
bonus, query complexity classifier or generative inference is introduced.

Freeze a limited source-grounded engineering supplement before scoring it. Labels
are authored independently of retrieval outputs; they are not independent human
judgments. Keep this supplement and the existing holdout separate from regression
fixtures. Public documentation paraphrases and fictional versioned procedures
are permitted; private production knowledge is not read or indexed. Record source
URLs, file hashes, languages and exact passage labels. Synthetic distractors are
only retrieval-stress material, never independent quality evidence.

Measure raw/eligible atom coverage and document recall, final atom/complete/multi-
document coverage, scope-local counts, selected IDs, reasons/loss stages, no-answer
empty rate, irrelevant-document and no-labeled-atom rates, lexical redundancy,
fragment/source diversity, clipping and budget drops. Report token mean/p50/p95
and atoms per 1000 estimated tokens (not answer accuracy). Preserve per-query
regressions, including named historical cases. Do not pool datasets or claim
statistical significance from the small correlated topic groups.

Scope allocation: reserve section labels/separators from manifest RAG allocation,
then give equal capped allocations to requested scopes, without redistribution or
cross-scope score comparisons. Per-scope fragment limits include attribution and
separators. Record unconstrained demand and final allocated context. This is an
experimental allocator, not a claim that AgentExecutor enforces the manifest cap.
Replay every result through the existing real executor/llama.cpp payload builder
with mocked transport and no tools/history. Replay is NOT generated-answer testing.
Try the existing local chat server's /tokenize endpoint for exact content counts;
report endpoint failures explicitly, and distinguish content counts from chat-
template token accounting. Never start model services or call paid APIs.

Performance: separate selector wall-clock repeats (no tracing) from a tracemalloc
peak probe (Python allocations only). Test K5/10/20 and a bounded K128 stress pool.
Run an isolated Chroma corpus with at least 1024 synthetic engineering distractors
and real manifest embeddings. Measure K2/5/10/20 searches after warmup, index time,
size and evidence retention. A single stress corpus is not large-production proof.
All tests/evaluations use scripts/run_isolated.py. Preserve old artifacts, services,
model configuration and production stores. No commit/push/reset/clean.

Decision: prefer the simplest strategy with material coverage gain and acceptable
context cost, and disclose no-answer/regression limits. A candidate for further
validation is not approval for production. Require natural independently judged
queries, full routing/security/freshness tests, tokenizer calibration and real
answer evaluation before deployment; seek user architecture/configuration approval.
