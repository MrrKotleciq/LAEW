# Memory sufficiency assessment

The optional semantic assessor evaluates the current question against the recalled
Memory evidence before a Global RAG fallback. It uses the same policy after
Automatic Recall and MemoryTool recall. A structured field/value match can avoid
this request; no evidence, weak lexical matches, explicitly broad requests, and
other clear gaps continue directly to fallback. At most one assessment chain runs
per turn. A failed or invalid response is treated as unverified. Explicit source
restrictions and existing context and project boundaries remain in force.

Enable it in the system manifest. It is disabled by default to avoid silently
introducing a separate model call and potential cloud costs:

```yaml
memory_sufficiency:
  enabled: true
  model: active
```

Alternatively select a configured provider and model (and account for cloud
providers, where applicable):

```yaml
memory_sufficiency:
  enabled: true
  model:
    provider: ollama
    model: your-model-id
```

The provider choices are the same as Memory extraction: `manifest`, `ollama`,
`llama.cpp`, `gemini`, `openai-api`, and `chatgpt`; cloud selections may include
`account_id`. The selected model must support the provider's text generation
interface. Active follows the chat provider, including a provider fallback. The
manifest is read for each new Workbench turn (and when CLI chat starts). No UI
redesign or database migration is required.

The extra request sends the question and recalled memory contents to the chosen
provider. Choosing a cloud provider can transmit personal or project data and
incur charges. Its provider timeout applies to this separate request. The model
is a fallible classifier: a positive response is not proof of semantic
completeness, and prompt injection in recalled data cannot be ruled out. The
response parser accepts only a single JSON boolean; errors, malformed output,
and oversized questions trigger conservative fallback. Model, timing, token
counts when available, and outcomes appear in routing diagnostics without
recording the question or memories there.

## Horizon-preferred mode

Select this experimental policy explicitly in the system manifest.

```yaml
memory_sufficiency:
  enabled: true
  model: horizon-preferred
```

Start and stop the Horizon service in the root `laew` Compose project with
[`tools/horizon-sufficiency/start-horizon.ps1`](../tools/horizon-sufficiency/README.md).
LAEW connects directly to `127.0.0.1:8082`.
Before inference it checks `/readyz` for a ready
`Horizon-Labs/multilingual-zeroshot-small` model and the `horizon-nli-v1`
contract. The readiness request uses a 250 ms socket timeout and a 30-second
positive cache. Inference uses an 800 ms socket timeout and validates the model,
contract, and score pair again. A failed probe or inference invalidates readiness
and opens a five-second cooldown. The first eligible assessment after cooldown
probes again in the same LAEW process. Concurrent Horizon calls abstain while
the current call completes.

The premise contains only the in-scope recalled text. The hypothesis asks if
that text directly and completely answers the resolved question. Scores of
0.95 or higher for either NLI label are tagged as strong diagnostic signals.
Every valid score leaves coverage unverified and permits the usual RAG fallback.
Oversized input, possible token truncation, and an in-flight assessment also
abstain. Horizon never produces a positive coverage decision.

If Horizon fails or is in cooldown, the currently selected Chief model may make
one assessment using the existing strict boolean parser. The automatic fallback
allows only a loopback HTTP llama.cpp provider, with a separate five-second
request timeout and environment proxies and redirects disabled. Ollama can run
cloud-backed models even when its endpoint is local, so it is excluded from
this automatic fallback along with cloud and non-loopback providers. A valid
boolean is recorded as a diagnostic signal. Coverage stays unverified in this
mode regardless of the model's response. The explicit `active` and
provider/model settings above retain their behavior.

Sources and Run show the same assessment chain for both Recall paths, including
the Horizon signal or failure phase, the active attempt when applicable, and
timing. The chain does not include the premise, hypothesis, or provider output.

Compare heuristic routing with advisory Horizon using isolated fixture data.

```powershell
.venv/Scripts/python.exe -m laew.eval.memory_sufficiency_eval --horizon --output "$env:TEMP/laew-horizon-validation.json"
.venv/Scripts/python.exe -m laew.eval.memory_sufficiency_eval --horizon --dataset tests/evaluation/memory_sufficiency/horizon_holdout.json --output "$env:TEMP/laew-horizon-holdout.json"
```

### NLI formulation experiment

`laew.eval.horizon_strategies` compares the existing hypothesis with direct
answerability, a deterministic location candidate in English or Polish, and
topical relevance. It runs on the existing validation corpus and a separately
authored strategy holdout by default. Additional corpora can be supplied with
repeatable `--dataset` options.

```powershell
.venv/Scripts/python.exe -m laew.eval.horizon_strategies --output "$env:TEMP/laew-horizon-strategies.json"
```

The evaluator preserves the advisory policy, then replays the exact scores
with a hypothetical 0.95 gate. That replay is confined to isolated fixture
orchestration. On the 18-case strategy holdout, the location gate would have
prevented three necessary searches (s03, s17 and s18) and three unnecessary
ones. The high scores verified the candidate statements about an assigned,
previous or ambiguous location, which still lacked the requested location.
A manually supplied claim probe also yielded 0.934 for one side of a
contradictory pair (s07). Direct answerability and relevance produced zero
scores above the gate, with incomplete answers sometimes scoring higher than
complete answers. The [per-case report](reports/horizon-nli-strategies-20261106.json)
includes the actual scores and replay outcomes.

Routing precedes both Recall and assessment. In v20 the normalized Polish
interrogative `ktora` does not match the saved-context pattern for `ktory`.
In v21 the English possession question `Who has my camera?` falls outside the
supported forms. The same stage skips h11 and h18. All four record
`memory_requested=false`, `memory_status=not_selected`, no initial RAG scope
and no assessment. The separate routing task in the
[backlog](roadmap/BACKLOG.md) covers these cases.

For an answerability experiment, consider a local multilingual extractive QA
model with an explicit no-answer score, such as
[`timpal0l/mdeberta-v3-base-squad2`](https://huggingface.co/timpal0l/mdeberta-v3-base-squad2).
Evaluate Polish transfer and abstention independently. A supported answer
span still requires a separate check for all requested facts and conflicting
evidence.

## Evaluation limits

`tests/evaluation/test_memory_sufficiency_calibration.py` is a small hand-labeled
assessment corpus. Its labeled assessor is an oracle stub used to verify control
flow, not a measure of model quality. The integration tests use isolated SQLite
and Chroma data and stub providers. A representative held-out dataset and real
model evaluation, including false-sufficient rates, answer coverage, latency and
cost, remain necessary before relying on model judgments in production.

## Isolated baseline and orchestration comparison

On the same 23 manually labeled assessment cases, the pre-change policy made
3/6 unnecessary Global RAG decisions and missed 1/17 required searches. With
semantic assessment disabled, the conservative policy made 4/6 unnecessary
searches and missed 0/17. With an oracle stub that returns the hand label, the
policy made 0/6 unnecessary searches and missed 0/17, with 17 assessment calls.
The oracle result is an upper-bound control-flow check, not observed performance
of any model. It cannot establish a reduction for a real provider. The stubbed
multi-turn adapter test supplied 5/5 expected evidence markers. Integration tests
also verify automatic and model-initiated recall for positive and negative model
decisions, including delivery of Memory and Global evidence to the adapter.
This baseline used stubs for model decisions. Its assessment timing measures
the test harness and excludes real inference.
