# LAEW

## Local AI Engineering Workspace

LAEW is a self-hosted local AI environment designed to act as a long-term engineering partner for software, electronics and engineering projects.

The system is designed around the principle that the model is only one component of the environment. Project knowledge, documentation, memory and tools remain outside the model and are provided to it when needed.

## Goals

LAEW should provide:

- project-aware AI assistance,
- long-term engineering memory,
- access to project files and Git repositories,
- retrieval of relevant documentation and knowledge,
- controlled tool execution,
- support for engineering analysis and decision-making,
- modular and replaceable AI models,
- local-first operation with optional external APIs.

## Core Architecture

```text
User
  ↓
Odysseus
  ↓
Chief Agent
  ↓
Knowledge / Memory / Tools
  ↓
Services
  ↓
LLM

```
The Chief Agent coordinates the task, selects the required context and tools, evaluates results and decides what to do next.

## Repository Structure
```

LAEW/
├── laew/           # Python package (core implementation)
├── docs/           # Project documentation
├── manifests/      # System manifests
├── prompts/        # Version-controlled prompts
├── tests/          # Unit and specification tests
├── tools/          # Tool contracts
├── pyproject.toml  # Package build configuration (PEP 621)
└── README.md
```

## Development Principles
```
Knowledge remains outside the model.
Source data has a single source of truth.
Components should be modular and replaceable.
AI should work from the current project state.
Read and analysis operations are separated from execution.
Security restrictions must be enforced below the model layer.
Every major component should be testable independently.
```
## Installation

LAEW requires **Python 3.10+** and (for chat/multi-agent features) a running local
LLM — the built-in provider is **Ollama** ([ollama.com](https://ollama.com)).

Install into an isolated virtual environment:

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

From a source checkout: `pip install -e .[dev]` (editable install + test/build
toolchain). Verify the install with `laew --version` and `laew --help`. For a
full walkthrough including Ollama setup, troubleshooting, and the manifest
configuration schema, see `docs/INSTALL.md`.

## Configuration

Provider configuration lives under `agent.llm.providers` in the system manifest
(`manifests/SYSTEM_MANIFEST.yaml`) and can be overridden by environment variables
and CLI flags:

- Environment: `LAEW_TIMEOUT` (request timeout in seconds), `LAEW_BASE_URL` (LLM
  API base URL).
- CLI: `laew chat --provider ollama --timeout 600 --model llama3.1`.

Precedence is **CLI flag > environment variable > manifest > provider default**.
The provider selection is dispatch by manifest `provider.type` through the
provider registry (`laew/llm/registry.py`).

## Project Status

Current stage: Milestone 11 (Production Hardening)

The repository implements:
- Declarative foundation with system manifest and tool contracts
- Tool runtime wrappers with programmatic security
- CLI, LLM provider abstraction, context budgeting, and agent orchestration
- RAG system with embeddings, vector store, knowledge base, and retrieval pipeline
- Persistent knowledge store backed by ChromaDB in Docker (falls back to in-memory store when unavailable)
- Provider registry + factory with timeout/base_url configuration (Milestone 11)
- PEP 621 packaging via `pyproject.toml` with install guides (Milestone 11)
- 369 unit tests across 19 test suites

See `docs/ROADMAP.md` for the development roadmap and future milestones.