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

## Starting the local LLM

1. Start Ollama: `ollama serve` (usually already running as a background service).
2. Confirm a model is available: `ollama pull llama3.1`.
3. Chat with the local model:

```console
$ laew chat --model llama3.1
```

Run a multi-agent plan:

```console
$ laew multiagent run tests/multiagent/test_plan.yaml --manifest manifests/SYSTEM_MANIFEST.yaml
```

## Interactive Testing Console

The console REPL lets you explore the full runtime surface in one session.
Start it with:

```console
$ laew console --manifest manifests/SYSTEM_MANIFEST.yaml
```

Inside the console, `help` lists all commands. Key groups:

| Group | Example commands |
|-------|------------------|
| System | `check`, `info`, `set timeout 600`, `set approval auto` |
| Provider | `provider info`, `provider models`, `provider health`, `provider generate "hi"` |
| Tools | `tool filesystem list_dir directory_path=@project`, `tool terminal run command=ls`, `tools` |
| Agent | `agent run "list files in docs/"`, `agent chat`, `trace on` |
| RAG | `rag query "find docs" scope=project k=5`, `rag embed`, `rag stats` |
| Workflow | `workflow discover`, `workflow show test_flow.yaml`, `workflow run test_flow.yaml` |
| Multi-agent | `multiagent discover`, `multiagent show test_plan.yaml`, `multiagent run test_plan.yaml` |
| Evaluation | `eval datasets`, `eval tasks laew_specific`, `eval task 001`, `eval dataset laew_specific` |
| Prompts | `prompt list`, `prompt show code_review`, `budget "some text"` |
| Console | `history`, `!5` (re-run history item 5), `exit` |

All commands work **offline** (no Ollama required) except: `provider *` (needs a reachable model), `agent *` (needs a reachable model), and `rag embed` (needs embeddings). Offline commands show a clear `[!]` when the provider is unreachable.

Use `set approval auto` to auto-approve mutations for faster testing, `set approval deny` to verify gates block mutations, or `set approval ask` (default) for interactive prompts.

## Configuration

LAEW reads provider configuration from the system manifest
(`manifests/SYSTEM_MANIFEST.yaml`), then overlays environment variables, then CLI
flags. Precedence: **CLI flag > environment variable > manifest > provider default**.

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

`laew chat` and `laew multiagent run` select a provider by `type`. Only
`type: ollama` is registered in the provider registry today; unknown types raise
`UNSUPPORTED_PROVIDER`.

### Environment variables

The following `LAEW_*` variables override manifest values when set. They apply to
`laew chat` and `laew multiagent run`:

| Variable          | Type   | Purpose                                  | Example value          |
|-------------------|--------|------------------------------------------|------------------------|
| `LAEW_BASE_URL`   | string | LLM API base URL                         | `http://localhost:11434` |
| `LAEW_TIMEOUT`    | int    | Request timeout in seconds               | `600`                  |

### CLI flags

| Flag          | Applies to                          | Purpose                      |
|---------------|-------------------------------------|------------------------------|
| `--model`     | `chat`, `multiagent run`            | Override the manifest model      |
| `--base-url`  | `chat`, `multiagent run`            | Override the LLM API base URL    |
| `--provider`  | `chat`, `multiagent run`            | Select provider by type          |
| `--timeout`   | `chat`, `multiagent run`            | Request timeout in seconds       |
| `--manifest`  | All commands                        | Path to the system manifest      |

Example — chat with a slow CPU model and a longer timeout:

```console
$ laew chat --provider ollama --timeout 600 --model llama3.1
```

## Troubleshooting

- **`Connection refused` on `localhost:11434`** — Ollama is not running; start it
  with `ollama serve` (or the desktop app) first.
- **`[FAIL] All specialist delegations failed` in `multiagent run`** — small local
  models are slow; raise the request timeout via `LAEW_TIMEOUT`, `--timeout`, or a
  manifest `timeout` entry.
- **`Unsupported provider type`** — the manifest declares a provider `type` that is
  not registered; only `ollama` ships today.