# Stage 2B.2 reranker quality protocol v1

Initial design recorded before new reranker scoring on 2026-11-09. The independent fixture and
its labels are in `tests/rag/reranker_holdout_v1`; `FREEZE.json` records their
hashes. No model output is used to establish labels or tune the selection policy.
The additional 5000-token condition was requested before scoring started.
Implementation clarifications added before quality analysis cover per-scope hybrid
metrics, raw-candidate performance counts and resource instrumentation. They do not
change holdout labels after scoring, the selection policies, the material-gain
criterion, or Mixedbread's predeclared stop rule. A pre-score label audit extended
u21's required atoms; that audit and the final fixture hashes are in FREEZE.json.

## Data and isolation

Use the unchanged `baseline_v1` (28 queries) and `hard_cases_v1` (13 queries), plus
the new independent holdout (32 queries). The holdout contains paraphrases and
translations of public engineering software documentation, and explicitly fictional
versioned gateway/calibration/site runbooks. It is an authored test, not an expert
blind annotation study or a sample of private production knowledge. Related
questions share topic IDs for clustered uncertainty estimates. Labels name exact
document/passage atoms; source links and document languages are saved separately.

Reuse `rag_baseline.run` with a replacement evaluation callback to build six
disposable PersistentClient indexes: three datasets × legacy/structure-v2. The
production Chroma server/collections are never used. The existing local manifest
embedding endpoint/model/dimensions and cosine threshold 0.3 remain unchanged.
Use `scripts/run_isolated.py` for every test and evaluation phase. Candidate capture
finishes before models run, so embedding work does not compete with reranker timing.

Capture separate raw Chroma K=10 and K=20 searches per permitted scope, before
selection and context limits. Record actual counts when fewer candidates exist.
Retain IDs, logical paths, source scope, original cosine scores, text and metadata.
All methods use identical captured pools. Apply the same original cosine threshold
to all methods before reranking; report raw and eligible evidence separately.

## Ranking and selection

Compare cosine with the existing pinned GTE, BGE and Mixedbread services. Scores
are pointwise raw relevance, never cross-model probabilities. The existing shared
client is reused. Split pools exceeding its 16-document limit into bounded calls,
then remap original IDs/indices and stably sort. Do not truncate model input. Any
overflow, startup error or timeout is explicit; there is no silent cosine fallback.

Score the union of K=10/K=20 candidates once per query/scope/model, and reuse
pointwise scores in each subset. Cache identical query/text pairs across chunking
conditions to avoid redundant inference. Performance probes bypass this cache.
Never use quality-run cache timings as K-specific warm latency estimates.

Primary policy: top two ranked fragments **per scope**, matching current automatic
prefetch. Secondary diagnostic policy: pass the whole ranked pool to the existing
context builder and fill the budget. Both use the unchanged `_build_context`
attribution, first-fragment truncation and later-fragment skipping behavior.
Evaluate budgets **500, 1000, 5000 estimated tokens per scope**, using chars/4.
The larger-budget diagnostic does not change production fragment limits or defaults.

Measure raw candidate document recall/evidence coverage, unique-document MRR/nDCG,
evidence positions, pre-budget and final atom coverage, complete evidence,
multi-document/one-document/cross-language outcomes, irrelevant-document selection,
and >80% token-set overlap among selected fragments (diagnostic, not a filter).
Document-level relevance does not prove each selected fragment contains an atom.
Hybrid rankings stay separate: MRR/nDCG are averaged over evidence-bearing scopes,
and evidence positions refer to the corresponding scope's ranking.
No-answer queries have no relevance denominator: report selected irrelevant context
and empty-selection rate; do not invent an abstention threshold.

Classify each atom: absent from candidates (also record whether available anywhere
in the index), filtered by original cosine threshold, below selection limit, removed
by context budget, or delivered to adapter. Reuse the existing replay Observer with
AgentExecutor and llama.cpp's real payload serializer; mock transport/response,
force only fixture scopes, and use no history/tools. Replay verifies delivery, not
answer correctness or full production routing. At 5000 tokens **per scope**, a
hybrid request may exceed the manifest's 8000-token RAG allocation; report serialized
system size and do not treat this as an approved production prompt budget.

## Performance and stopping

Run one model at a time through `manage.ps1`; preserve existing quotas. Readiness
wait/model startup, first inference, and warm inference are separate. Use realistic
frozen `h03` development query/candidate lengths, both chunkers, K=5/10/20.
Performance pools use raw retrieved candidates, before cosine eligibility, so a
20-document workload can be measured even when the unchanged quality filter would
retain fewer than 20. Earlier probes with the same prefix remain comparable; any
missing raw-K=20 probe is measured explicitly rather than extrapolated.
Use one first/warmup request plus 10 warm samples per condition for GTE/BGE; p95
with n=10 is descriptive and has substantial uncertainty. Native backend timing
boundaries differ; report both native and end-to-end timings. A thin timing subclass
of the existing client additionally records the rerank POST phase (tokenization,
queueing and response included) and TEI's server-total header where available.
TEI 1.9.4 averages per-pair inference durations for its inference header; the sum
of two split-call headers is a diagnostic aggregate, not the whole-pool compute
duration. Never compare it directly with Mixedbread's full scoring-loop duration.
The common POST-phase and end-to-end measures are the comparable serving latencies.
Record cgroup CPU,
current/peak memory, Docker stats, errors, limits and truncation flags.

Logical pool deadline: 90 seconds, with bounded per-HTTP-call timeouts inside it.
For Mixedbread, start with three warm K=5 samples after the first request. If any
measured configuration's warm median exceeds **10 seconds**, or a probe fails/exceeds its deadline, stop
larger configurations and the full quality workload. Report every skipped condition
as unmeasured, without extrapolating latency or inventing quality scores. A small
performance sample cannot establish a reliable production p95. This resource gate
is declared in advance and follows the requested expensive-model stop condition.

## Analysis and review

Report each dataset separately; do not pool regression and independent results to
claim generalization. Primary quality comparison is top2, K=20, budget=1000; also
show the current 500 budget and requested 5000. Report all query regressions,
including h11 and h04/h05/h09, without exceptions in the ranking algorithm.
Use paired topic-cluster bootstrap intervals on independent holdout final-coverage
deltas, and exact paired signs where feasible. Multiple comparisons are exploratory;
do not claim significance merely from positive averages. A material improvement is
at least 5 percentage points of final evidence coverage, supported by uncertainty
and no unexplained single-document regressions. Consider latency and memory alongside
quality. If evidence is insufficient, recommend D (no model yet). Any model/config
recommendation remains a proposal requiring user review; production stays unchanged.

## Reproduction commands

Run from the repository root in PowerShell. `--keep-diagnostics` retains the
runner's printed temporary directory; evaluation outputs are under its `work/`
subdirectory, not the production repository. Copy only the resulting experiment
JSON to `runtime/` for the next phase. Never point candidate capture at production
knowledge or a production Chroma client.

```powershell
.venv\Scripts\python.exe scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.reranker_benchmark prepare --output docs/reports/candidates.json
# Copy <printed-run-directory>\work\docs\reports\candidates.json to runtime\.

.\tools\rerankers\manage.ps1 -Model gte -Action start
.venv\Scripts\python.exe scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.reranker_benchmark score --model gte `
  --input "$PWD\runtime\candidates.json" --output docs/reports/gte.json
.\tools\rerankers\manage.ps1 -Model gte -Action stop
# Repeat independently for bge and mxbai; copy their output JSON files to runtime\.

.venv\Scripts\python.exe scripts/run_isolated.py --keep-diagnostics eval `
  laew.eval.reranker_benchmark analyze --input "$PWD\runtime\candidates.json" `
  --scores "$PWD\runtime\gte.json" "$PWD\runtime\bge.json" "$PWD\runtime\mxbai.json" `
  --output docs/reports/analysis.json

.venv\Scripts\python.exe scripts/run_isolated.py pytest `
  tests/evaluation/test_reranker_benchmark.py tests/evaluation/test_rag_baseline.py `
  tools/rerankers/tests/test_contract.py -q
```

The `performance` phase repeats only timing probes without scoring quality again;
`--probe-strategy legacy|structure-v2` and `--probe-count 5|10|20` can restrict a
diagnostic repeat. Keep all original observations and explain why a repeat was
needed. In this run, the user released memory after an observed host-memory-pressure
episode; all GTE timing conditions were repeated, while deterministic quality scores
were retained. No container quota or Docker Desktop limit was increased.
