# LAEW Horizon NLI (CPU-only, port 8082)

Horizon runs as the `horizon-sufficiency` service in the root LAEW Compose
project alongside ChromaDB and SearXNG. Its build context is this directory.

## Requirements

- Windows 11, Docker Desktop with Linux containers enabled and Compose support for `up --wait`.
- Network access to Hugging Face for model resolution at startup. A persistent Docker cache reuses downloaded weights.
- Free host port `127.0.0.1:8082`.

## Service lifecycle (PowerShell)

```powershell
cd C:\ROOT\Projects\LAEW\tools\horizon-sufficiency
.\start-horizon.ps1 start
.\start-horizon.ps1 status
.\start-horizon.ps1 test
.\start-horizon.ps1 logs
.\start-horizon.ps1 stop
.\start-horizon.ps1 update
```

`start` brings up only Horizon and waits for health. `update` rebuilds the
image with the latest base image and recreates only Horizon.
Both commands check the expected model, contract and active ONNX provider.
`stop` preserves the stopped container and named cache volume. The
`unless-stopped` restart policy applies to the service. `status` includes
stopped containers. `test` compares an explicitly supported visit claim with
a cancelled trip.

The root Compose file mounts the existing `laew-horizon_horizon-model-cache`
as an external volume. This preserves the model files from the former Horizon
project. The PowerShell script provisions the volume when needed. On a fresh
host, create it once before using the root Compose CLI directly.

```powershell
docker volume create laew-horizon_horizon-model-cache
```

The model is a 141M-parameter multilingual NLI encoder, not a generative model. The API offers:

- `GET /healthz`: process liveness.
- `GET /readyz`: actual model readiness, model ID, service contract.
- `POST /v1/nli`: JSON `{ "premise": "...", "hypothesis": "..." }`; returns probabilities for entailment and not-entailment with latency and token count.

Example:

```powershell
Invoke-RestMethod http://127.0.0.1:8082/readyz
```

**Important:** the service deliberately does NOT declare a memory sufficient just because an NLI score is high. LAEW must calibrate its own sufficiency decision on held-out test data, with explicit fallback behavior. The score is not a calibrated probability of complete answer coverage.

Compose limits the service to two CPU cores and 2 GiB of RAM. The model revision
and ONNX file are pinned in Compose. Startup resolves that revision on
Hugging Face and reuses weights from the `laew-horizon_horizon-model-cache`
volume. Inference uses the local session.

Security: Docker binds only `127.0.0.1:8082` on the Windows host. No auth is provided; do not publish it to LAN or internet. The API does not persist the submitted memory text or log request bodies.

The Windows Docker Desktop validation loaded `onnx/model.onnx` at revision
`17af5f8a728d101ce33a9bffad227b0cd005e95e` and completed inference using
`CPUExecutionProvider`. The server dependencies use version ranges.

LAEW's opt-in adapter is documented in [Memory sufficiency](../../docs/memory-sufficiency.md#horizon-preferred-mode).
