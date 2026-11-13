# Optional multilingual reranker lab

These services belong to the existing Compose project `laew` and network
`laew_default`. Each model has its own process, container, profile and persistent
volume. They have no dependency on Horizon or production LAEW components. Nothing
in Chief Agent, retrieval, scope selection, authorization or production RAG calls
them. This is a functional inference lab, not a quality evaluation or model choice.

## Models and verified implementations

All three model repositories declare **Apache-2.0**. TEI and `mxbai-rerank` also
use Apache-2.0. Runtime dependency versions, including transitive Python packages,
are pinned in `requirements.lock`; PyTorch uses its CPU wheel, with no CUDA stack.
The main Python runtimes are Transformers/Accelerate/Hugging Face Hub (Apache-2.0),
PyTorch (BSD-3-Clause) and NumPy (BSD-3-Clause with bundled library notices).
Their installed wheel metadata and license files remain in the image; this is
not a claim that every bundled binary has a single common license.

| Profile / service | Model ID | Exact model revision | Backend | Host / internal port | CPU / RAM limit |
|---|---|---|---|---|---|
| `reranker-gte` | `Alibaba-NLP/gte-multilingual-reranker-base` | `8215cf04918ba6f7b6a62bb44238ce2953d8831c` | TEI 1.9.4 CPU / Candle | `127.0.0.1:8083` / `80` | 2 / 3 GiB |
| `reranker-bge` | `BAAI/bge-reranker-v2-m3` | `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e` | TEI 1.9.4 CPU / Candle | `127.0.0.1:8084` / `80` | 2 / 4 GiB |
| `reranker-mxbai` | `mixedbread-ai/mxbai-rerank-base-v2` | `3ea9d4dffa7d12a4f366be8e275c349de9fc9865` | `mxbai-rerank==0.1.6`, `torch==2.6.0+cpu`, `transformers==4.51.3` | `127.0.0.1:8085` / `8080` | 2 / 4 GiB |

TEI is pinned by digest
`sha256:2538ea1c9640d3763b15af668039d24172d063b42337b0c27796fc2be180c78d`
(`ghcr.io/huggingface/text-embeddings-inference:cpu-1.9.4`, linux/amd64).
Mixedbread uses local image `laew/reranker-mxbai:0.1.0`; its Python 3.11.11 base
is pinned by digest in the Dockerfile. The build runs `pip check`.

Compatibility was checked against the pinned model configurations, official model
cards, TEI source, and the installed `mxbai-rerank` 0.1.6 source:

- GTE is a 306M encoder with RoPE and model type `new`. TEI implements it natively
  on CPU, including its classification head. Its model configuration references
  `Alibaba-NLP/new-impl` for Transformers, but TEI never executes that Python code.
  No `trust_remote_code` is enabled or needed. The model supports 8192 tokens.
- BGE is an XLM-RoBERTa sequence classifier with an absolute-position context of
  8192 tokens (8194 position entries include the position offset). The official
  card supports FlagEmbedding **and** Hugging Face Transformers. TEI's native CPU
  implementation supports this architecture, avoiding a second Python dependency
  tree. Both encoders receive query/document token pairs and return raw logits.
- Mixedbread v2 is a Qwen2 causal decoder, not an encoder classifier. The official
  library applies its relevance instruction and chat template, left padding, and
  the final-token `logit("1") - logit("0")` score. We call its `predict` method
  directly, one pair at a time; this preserves input order without reimplementing
  model inference. `normalize=False` avoids the library's score scaling. The
  library advertises 8K context / 32K compatibility; the model configuration has
  32768 positions. Full long-context inference is not enabled or validated here.
  Only safetensors and tokenizer/configuration files are downloaded; loading uses
  `trust_remote_code=False`, `local_files_only=True`, float32 and CPU SDPA.

Primary references:
[GTE model card](https://huggingface.co/Alibaba-NLP/gte-multilingual-reranker-base/tree/8215cf04918ba6f7b6a62bb44238ce2953d8831c),
[BGE model card](https://huggingface.co/BAAI/bge-reranker-v2-m3/tree/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e),
[Mixedbread model card](https://huggingface.co/mixedbread-ai/mxbai-rerank-base-v2/tree/3ea9d4dffa7d12a4f366be8e275c349de9fc9865),
[TEI 1.9.4 backend](https://github.com/huggingface/text-embeddings-inference/blob/v1.9.4/backends/candle/src/lib.rs),
[TEI request schema](https://github.com/huggingface/text-embeddings-inference/blob/v1.9.4/router/src/http/types.rs),
[Mixedbread 0.1.6 release](https://pypi.org/project/mxbai-rerank/0.1.6/).

## Build and operate independently

Run these commands from the repository root in PowerShell. The normal
`docker compose up -d` does not start reranker profiles. Rerankers use
`restart: "no"`, so Docker Desktop startup does not automatically load them.
The helper checks port availability and refuses to start a second reranker while
another one is running. Direct Compose commands remain available for explicit use.

```powershell
.\tools\rerankers\manage.ps1 -Model gte -Action start
.\tools\rerankers\manage.ps1 -Model gte -Action status
.\tools\rerankers\manage.ps1 -Model gte -Action stop
# Substitute bge or mxbai; start only one at a time.
```

Equivalent individual Compose commands:

```powershell
docker compose --profile reranker-gte up -d --no-deps reranker-gte
docker compose --profile reranker-gte stop reranker-gte
docker compose --profile reranker-bge up -d --no-deps reranker-bge
docker compose --profile reranker-bge stop reranker-bge
docker compose build reranker-mxbai
docker compose --profile reranker-mxbai up -d --no-deps reranker-mxbai
docker compose --profile reranker-mxbai stop reranker-mxbai
```

First startup automatically downloads the pinned model to its dedicated volume.
Readiness may take several minutes, depending on download speed. Health checks
run every 5 seconds during a 30-minute initialization grace period, then every
30 seconds. This grace period is for downloads, not a reason to ignore startup
errors. Readiness is available only once the model is loaded (TEI also warms up).

```powershell
.venv\Scripts\python.exe tools/rerankers/client.py gte ready --timeout 5
.venv\Scripts\python.exe tools/rerankers/client.py gte info
docker compose --profile reranker-gte ps -a reranker-gte
docker compose logs --tail 30 reranker-gte
docker inspect laew-reranker-gte-1 --format '{{json .State}}'
```

Inspect `Running`, `ExitCode`, `OOMKilled` and health status. An OOM kill is a
failure, not readiness or an automatic retry; services deliberately do not
restart themselves. Mixedbread initialization failures return 503 with
`startup_failed=true`, log the exception class, and remain unhealthy. TEI exits
on fatal startup errors. TEI may first log that no ONNX files exist, then fall
back successfully to Candle. Missing optional pooling/config files can also
produce download warnings. The native `/info` and readiness distinguish successful
fallback from a failed model. Request bodies and full document text are not logged;
TEI spans and Mixedbread access logs are disabled.

Mixedbread handles SIGTERM explicitly so an idle `docker stop` exits with code 0.
Stopping during an ongoing long inference can still require Docker's force-kill
after its stop grace period; inspect `OOMKilled` to distinguish that from OOM.
Transformers 4.51.3 also emits a generic Qwen2 SDPA/sliding-window warning because
`sliding_window=32768` is present. The pinned model has `use_sliding_window=false`,
and this lab stays well below that length; long-context behavior is untested.

## Common logical interface and native HTTP routes

`RerankerClient` in `client.py` is a standalone, standard-library-only adapter.
There is no proxy container. Future benchmark tools should use this client rather
than assume that TEI has the same HTTP routes as Mixedbread.

| Logical operation | Client method | GTE / BGE native HTTP | Mixedbread native HTTP |
|---|---|---|---|
| `GET /readyz` | `ready()` | `GET /health` | `GET /readyz` |
| `GET /v1/info` | `info()` | `GET /info` | `GET /v1/info` |
| `POST /v1/rerank` | `rerank(request)` | `POST /rerank` | `POST /v1/rerank` |

Inside `laew_default`, use `http://reranker-gte:80`,
`http://reranker-bge:80`, or `http://reranker-mxbai:8080`. Native ports are
published only on the host's IPv4 loopback interface. Services have no GPU
allocation, no host bind mounts, all Linux capabilities dropped and
`no-new-privileges`. Mixedbread runs as an unprivileged image user. The official
TEI image runs as root with capabilities dropped; it can write only its container
filesystem and dedicated cache, with no Docker socket or production mounts.

Example logical request is in `example-request.json`:

```json
{"query":"How should the controller be initialized?","documents":[{"id":"doc-1","text":"Initialize communication before enabling the actuator."},{"id":"doc-2","text":"Disconnect the actuator before updating firmware."}]}
```

```powershell
.venv\Scripts\python.exe tools/rerankers/client.py gte rerank `
  --input tools/rerankers/example-request.json --timeout 120 --stats `
  --output runtime/reranker-results.jsonl
# Use bge or mxbai with exactly the same input file after starting that service.
```

Python import example for a future benchmark, without importing production LAEW:

```python
import sys
sys.path.insert(0, "tools/rerankers")
from client import RerankerClient
result = RerankerClient("gte", timeout=120).rerank({
    "query": "How should the controller be initialized?",
    "documents": [{"id": "doc-1", "text": "Initialize communication before enabling the actuator."}],
})
```

Responses include `model_id`, `revision`, `backend`, `candidate_count`,
`inference_ms`, `request_ms`, `truncation`, and sorted `results` containing
`id`, original zero-based `index`, and finite `score`. The client validates a
complete one-to-one index mapping and sorts by descending score, then original
index, preserving ties. Duplicate texts are allowed; document IDs must be unique.
Scores are raw model-specific relevance values, not calibrated probabilities,
and are not comparable across models. The client checks actual backend identity
and revision on every reranking call.

Input limits: 1–16 documents; 1–2000 query characters; 1–16000 characters per
document; nonblank IDs up to 128 characters; 512 KiB JSON body. Unknown logical
fields are rejected, including authorization/scope fields. These character/ID
rules belong to the client and the Mixedbread API; native TEI accepts its own
schema and enforces body, document count and token limits. LAEW remains responsible
for selecting permitted knowledge and enforcing authorization before calling.

The default effective encoder limit is **1024 tokens including pair separators**.
For Mixedbread, the official library uses a **1024-token query/document budget**,
then adds its fixed chat/relevance template and padding; the models therefore do
not receive identical token sequences. Its query is capped
at 768 tokens; the document uses the remaining pair budget. The default logical
`truncate=false` rejects overflow. Set `"truncate": true` explicitly to permit
right truncation. TEI uses its native paired-input truncation rules; Mixedbread
caps the query first and then truncates the document to the remaining budget.
Mixedbread reports exact affected indices. TEI does not expose
per-pair truncation flags: the adapter reports `status="unknown"`, `indices=null`
when truncation is permitted, rather than pretending to know which input changed.

TEI Candle uses an approximate GeLU activation where the original configurations
specify exact GeLU. Minor numerical differences from Transformers/FlagEmbedding
are therefore expected; comparisons must retain backend and version metadata.

TEI 1.9.4 CPU reports an effective `max_batch_requests=4` even when requested as
1; the pinned backend overrides this during warmup. The 1024-token total batch
budget still applies. Mixedbread processes one pair at a time. Threads are capped
at two for compute, with one Mixedbread inter-op thread and one TEI tokenizer
worker. CPU quota is two cores; CPU percentages can therefore approach 200%.

Timeouts are configurable with client `--timeout` / `timeout=` (each HTTP call),
and Mixedbread `REQUEST_TIMEOUT_SECONDS` (default 120). Errors are explicit:
validation errors, unavailable models, backend HTTP status, malformed responses
and transport timeouts. Mixedbread uses 400/413 for malformed/bounded JSON,
422 for token overflow, 429 for a busy worker, 503 for unavailable model, 504 for
inference timeout, and 500 for inference failure. A timeout does not kill an
ongoing CPU inference; Mixedbread remains busy until that work finishes. TEI work
can also continue after a client timeout. Error output never includes backend
response bodies, which could echo private inputs.

`--stats` adds optional Docker CPU/RAM information: `docker stats` after the
request, cgroup current/peak memory, CPU time and average CPU percentage over the
request measurement window (including HTTP and Docker measurement overhead).
Both cgroup v1 and v2 are supported. These are null when Docker cannot be queried.
`request_ms` includes model identity lookup and the rerank HTTP call. TEI's
`inference_ms` is its native response header, which need not represent the same
timing boundary as Mixedbread's full sequential scoring time. Use total latency
for future comparisons and retain native latency as separate metadata. JSONL
contains rankings, IDs and metrics, not query or document text. CLI failures emit
an error record and return nonzero. This is sufficient for a future baseline/GTE/
BGE/Mixedbread comparison over externally supplied legacy or structure-v2 candidates.

## Tests and measurements

Offline regression tests and opt-in real inference tests must use the existing
isolated runner:

```powershell
.venv\Scripts\python.exe scripts/run_isolated.py pytest tools/rerankers/tests -q

# Start one service first. The live test restarts/stops ONLY that new container.
$env:LAEW_RERANKER_LIVE = 'gte'
$env:LAEW_RERANKER_REPORT = "$PWD\runtime\reranker-gte-smoke.json"
.venv\Scripts\python.exe scripts/run_isolated.py pytest tools/rerankers/tests/test_live.py -q -s
Remove-Item Env:LAEW_RERANKER_LIVE, Env:LAEW_RERANKER_REPORT
```

The live test checks English, Polish, German, cross-language retrieval, technical
text/code, duplicate and irrelevant documents. It also checks malformed requests,
token overflow, explicit truncation, finite scores, mapping and stable order.
It disconnects only the selected reranker from `laew_default`, restarts it without
network access, verifies readiness and unchanged cached blob sizes/mtimes,
reconnects the Compose alias, checks identical inference after restart, then stops
the service in cleanup. Existing service IDs/start times/running states must stay
unchanged across each test. Run this only on a lab service not serving other work.
Offline regressions additionally cover startup failure/503, malformed backend
mapping, revision mismatch, unavailable transport, timeout/504 and busy/429.

See `measurements-20261109.md` and its JSON report for measured latency, CPU/RAM,
storage and cache restart results. Measurements are short functional smoke tests,
not quality scores, throughput benchmarks or evidence that the models fit alongside
every primary LLM workload. At inspection, the host had 16 GiB RAM, 8 cores / 16
threads, about 176 GiB free on C:, and only about 1.4 GiB free physical RAM. Docker
Desktop exposed 16 CPUs and 7.72 GiB RAM (WSL2, cgroup v1); no explicit `.wslconfig`
override was found. Global resource settings were not changed. Test sequentially;
three simultaneously loaded models leave inadequate headroom on this workstation.

## Storage and cleanup

Expected model weights alone: GTE 611,934,706 bytes; BGE 2,271,071,852 bytes;
Mixedbread 988,097,536 bytes. Tokenizer/config files add roughly 17–23 MB each.
Allow at least 4 GiB for all three dedicated caches combined, plus Docker image
and build storage. The two TEI services share one image; their caches are separate.
Docker/WSL disk usage also includes layers, build cache and page cache. Removing
files inside WSL does not necessarily shrink its virtual disk immediately.

Stop/remove a selected container without touching production services or caches:

```powershell
docker compose --profile reranker-gte stop reranker-gte
docker compose --profile reranker-gte rm -f reranker-gte
# Repeat explicitly for reranker-bge or reranker-mxbai if desired.
```

To clear only a selected reranker cache, first stop and remove that container, then
remove its exact dedicated volume (this deletes its downloaded model):

```powershell
docker volume rm laew_reranker-gte-cache
# Other dedicated caches, only after removing their containers:
# docker volume rm laew_reranker-bge-cache
# docker volume rm laew_reranker-mxbai-cache
```

The next startup recreates the selected cache and downloads the same pinned model.
Do not use project-wide `down -v`, volume pruning, or remove Chroma/Horizon volumes
for this lab. No cache removal is performed by the tests or startup helper.
