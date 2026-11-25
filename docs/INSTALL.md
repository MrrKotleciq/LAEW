---
name: LAEW Installation Guide
description: Installation and configuration instructions for the LAEW CLI across Windows, macOS, and Linux.
type: docs
scope: project
status: active
read_when:
  - setting up LAEW on a new system
---

# LAEW Installation Guide

This guide covers installing the **Local AI Engineering Workspace (LAEW)** CLI and
package on Windows, macOS, and Linux. LAEW is local-first: everything runs on your
machine; no cloud account or API key is required for the built-in Ollama provider.

## Prerequisites

- **Python 3.10 or newer** ([python.org](https://www.python.org/downloads/))
- **pip** (bundled with Python 3.10+)
- **Ollama** for the built-in local LLM provider — [ollama.com](https://ollama.com)
  - Linux/macOS: `curl -fsSL https://ollama.com/install.sh | sh`
  - Windows: install the Ollama desktop app, then pull a model, e.g.
    `ollama pull llama3.1`

## Install with pip

Install into an isolated virtual environment (recommended so LAEW dependencies
do not interfere with other packages).

### Windows

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install laew
```

### Unix (macOS / Linux / WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install laew
```

### From a source checkout

```bash
git clone <repo-url> laew
cd laew
python -m venv .venv
# Windows:
.\.venv\Scripts\Activate.ps1
# Unix:
source .venv/bin/activate
pip install -e .[dev]
```

`pip install -e .` installs LAEW in editable mode from `pyproject.toml` (PEP 621).
`[dev]` additionally installs the test and build toolchain (pytest, build, etc.).

## Using the `laew` CLI

Once installed, the `laew` command is available on `PATH`:

```console
$ laew --version
laew 0.1.0

$ laew --help
```

Validate the system manifest and workspace configuration:

```console
$ laew check --manifest manifests/SYSTEM_MANIFEST.yaml
```

## Start Workbench

Use an installed local model or choose a configured cloud provider in Workbench.

```console
laew ui
```

Run `laew ui --help` for the loopback port, workspace and browser options.

## Configuration

LAEW reads provider configuration from the system manifest
(`manifests/SYSTEM_MANIFEST.yaml`). Supported environment overrides apply to local
provider configuration. Select the provider and model in Workbench.

Manifest provider entries live under `agent.llm.providers`, for example:

```yaml
agent:
  llm:
    providers:
      - name: ollama_primary
        type: ollama
        model: llama3.1
        host: localhost
        port: 11434
        timeout: 300   # seconds; raises for slow CPU models
```

### Environment variables

| Variable | Purpose | Example |
|---|---|---|
| `LAEW_BASE_URL` | Local model API base URL | `http://localhost:11434` |
| `LAEW_TIMEOUT` | Model request timeout in seconds | `600` |

## Cloud models

Workbench uses cloud models through the same Chief Agent, permission broker and
scoped tools as local models. The backend reads API keys from its environment.
For ChatGPT account sign-in, install `python -m pip install ".[cloud]"` and use
**Continue with ChatGPT**. Choose an exact model before sending a message.
See [unified model providers](CLOUD_CHAT.md) for supported providers, credential
storage, scope and permissions.

## Operator CLI and recovery

Start with `laew status --json` from the repository environment. Run `laew --help`
to discover operator commands. Retained telemetry requires a separately
provisioned and verified protected installation. With it, use `laew telemetry
list --json` to discover a run UUID and `laew telemetry show RUN_UUID --json` to
diagnose it. Follow the [M18 recovery
runbook](M18_BACKUP_RECOVERY.md) for profile setup, backup verification,
isolated recovery, reviewed retention and disabled schedule examples.

`laew ui` remains the Workbench launcher and `laew check` remains the CI manifest
check. The public CLI retired `console`, `chat`, `memory`, `tool`, `workflow run`,
`multiagent run` and `rag-migrate`. Use Workbench for chat and memory management.
Scripts calling the retired commands must be migrated before using this version.

## Troubleshooting

### Local web search

Run `python scripts/setup_searxng.py` once to create the Git-ignored local secret,
then `docker compose up -d --no-deps searxng`. The UI and JSON API are bound to
`127.0.0.1:8888`; the container has a separate persistent cache. Do not put the
secret in version control. Search requests leave the host through external search
engines; local SearXNG does not make web search offline. Search results are
untrusted input. Restart existing LAEW processes to load the updated WebTool.

- **`Connection refused` on `localhost:11434`** — Ollama is not running; start it
  with `ollama serve` (or the desktop app) first.
- **`[FAIL] All specialist delegations failed` in `multiagent run`** — small local
  models are slow; raise the request timeout via `LAEW_TIMEOUT`, `--timeout`, or a
  manifest `timeout` entry.
- **`Unsupported provider type`** — the manifest declares a provider `type` that is
  not registered. Check the provider configuration and the supported selections
  in [unified model providers](CLOUD_CHAT.md).
