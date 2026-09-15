# LAEW — Current Project Status

## Status

Architecture: LAEW v1.0 documented
Implementation: Milestone 12 (Interactive Testing Console) completed

## Currently present in repository

- README.md
- manifests/SYSTEM_MANIFEST.yaml (System manifest v1.0)
- tools/ (Tool contracts for filesystem, git, terminal, web)
- prompts/ (Layered prompt templates)
- tests/ (Test specifications for security, agent, rag, workflow)
- docs/ (Architecture, principles, decisions, context, status)
- .claude/ (Agent SDK configuration, settings, prompts)
- package-lock.json
- .gitignore
- laew/ (Python package with tool runtime wrappers, CLI, LLM provider, prompt management, agent loop)
- laew/runtime.py (Shared provider/tool/config helpers used by both CLI and console)
- laew/console/ (Interactive testing console REPL and command handlers)
- laew/llm/registry.py (Provider registry and factory dispatching on manifest provider `type`)
- laew/logging_config.py (App-level stdlib logging: console + optional rotating file handler)
- laew/multiagent/ (Multi-agent architecture: message types, shared context, specialist roles, plan schema, chief coordinator)
- laew/eval/ (Evaluation harness with metrics, tasks, runner, and benchmark datasets)
- laew/workflow/ (Workflow runtime with definitions, execution engine, approval gates, and rollback)
- pyproject.toml (PEP 621 packaging metadata, console script, bandit config)
- setup.py (Package installation compatibility shim for pyproject.toml)

## Milestone 1 Implementation (Completed)

- manifests/SYSTEM_MANIFEST.yaml: Declarative specification of workspace boundaries, model roles, tool policies, memory layers, and RAG configuration.
- tools/: 4 modular tool contracts (`filesystem/CONTRACT.md`, `git/CONTRACT.md`, `terminal/CONTRACT.md`, `web/CONTRACT.md`).
- prompts/: 8 layered prompt templates (`core.md`, `chief-agent.md`, `architecture.md`, `research.md`, `code-review.md`, `debugging.md`, `documentation.md`, `rag.md`).

## Milestone 2 Implementation (Completed)

- laew/manifest.py: YAML manifest loader and schema validation engine (20 unit tests)
- laew/security/path_resolver.py: Multi-root workspace resolver with ADR-010 path aliasing, traversal prevention, and sensitive file blacklisting (18 unit tests)
- laew/tools/base.py: Abstract Tool class, standardized ToolResult, ErrorCode enum, and ADR-016 structured invocation logging (28 unit tests for filesystem, 24 for git, 19 for terminal, 15 for web, 4 for logging)
- laew/tools/filesystem.py: Filesystem operations with read-only defaults, mutation approval gates, and @project-only write constraints
- laew/tools/git.py: Git operations with inspect-first policy, mutation approval gates, blocked destructive subcommands, and LC_ALL=C locale enforcement
- laew/tools/terminal.py: Subprocess execution engine with command allowlists, dangerous pattern blacklists, and workspace boundary confinement
- laew/tools/web.py: HTTP reader with markdown conversion, protocol restriction (http/https), and web search interface
- laew/cli.py: Command-line interface with `laew check` (manifest validation), `laew tool` (tool execution), `laew workflow run` (workflow execution), and `laew chat` (interactive local LLM chat) commands

## Milestone 3 Implementation (Completed)

- laew/llm/base.py: LLM provider abstract interface with MessageRole, LLMMessage, LLMResponse, and LLMProvider per ADR-001 (10 unit tests)
- laew/llm/ollama.py: Ollama local LLM provider with chat generation, model listing, health checks, and model pulling
- laew/prompts/context_budget.py: Context budgeting per ADR-004 and TokenEstimator heuristic (~4 chars/token)
- laew/prompts/loader.py: Layered prompt loader supporting single-file and directory-based section composition (45 unit tests for prompts module)
- laew/prompts/templates.py: Prompt template registry with {{variable}} substitution and validation
- laew/agent/base.py: Agent base class, AgentConfig, AgentRole enum, and history management
- laew/agent/executor.py: AgentExecutor orchestration loop (Thought -> Action -> Observation -> Response) with tool calling via JSON blocks, dynamic operation hints in prompts, and a safety net that feeds malformed tool-call attempts back to the model for correction — including detection of raw shell commands in fenced code blocks. Added repetition guard to break out of repeated tool calls and forced final-answer fallback at max_iterations (34 unit tests)
- laew/rag/embedding.py: EmbeddingService abstract interface and OllamaEmbedding implementation (20 unit tests)
- laew/rag/vector_store.py: In-memory vector store with cosine similarity search (8 unit tests)
- laew/rag/knowledge_base.py: Knowledge loading from project memory and global knowledge sources (4 unit tests)
- laew/rag/pipeline.py: RAG pipeline orchestrating retrieval, reranking, and context injection (5 unit tests)
- laew/rag/rag_tool.py: Tool wrapper for agent RAG queries (4 unit tests)
- laew/rag/__init__.py: Module exports

## Milestone 5 Implementation (Completed)

- README.md: Updated to reflect actual repository structure (removed stale references to non-existent `configs/`, `docker/`, `scripts/` directories).
- docs/ROADMAP.md: New development roadmap with milestones 5–11 in dependency order.
- docs/history/CHANGELOG.md: Rewritten with correct chronological order and complete sections for Milestones 1–4 plus the code audit.
- tests/unit/test_integration_scaffold.py: Integration tests verifying agent + tools, agent + RAG, RAG + knowledge base + embeddings, and CLI + tools work together.
- tests/unit/test_documentation_validation.py: Tests ensuring README, PROJECT_STATUS, and manifest accurately reflect repository state.
- .github/workflows/ci.yml: CI baseline running the full test suite on push and pull request.

## Milestone 11 Implementation (Completed)

- laew/llm/registry.py: provider registry + factory dispatching on manifest `agent.llm.providers[].type` (only `ollama` registered); unknown types raise `LLMError(code="UNSUPPORTED_PROVIDER")`; config precedence CLI flag > env var (`LAEW_BASE_URL`, `LAEW_TIMEOUT`) > manifest > provider default.
- laew/llm/ollama.py: `OllamaProvider` now accepts a `timeout` parameter (was hardcoded to 120s — the root cause of CPU-model E2E timeouts).
- laew/cli.py: `chat` and `multiagent run` build providers via `create_provider()`; new `--provider` and `--timeout` flags; `configure_logging()` invoked at `main()`.
- manifests/SYSTEM_MANIFEST.yaml: provider entries accept optional `timeout`; manifest validation rejects non-positive `timeout` and empty provider `type`.
- pyproject.toml: PEP 621 packaging (name `laew`, version 0.1.0, console script `laew = laew.cli:main`), dev extras (pytest, html2text, chromadb, build), `[tool.bandit]` SAST config.
- setup.py: reduced to compatibility shim reading metadata from pyproject.toml.
- laew/logging_config.py: idempotent `configure_logging()` — console StreamHandler to stderr + optional `RotatingFileHandler` (1 MiB, 3 backups); leaves `laew.tools` logger untouched.
- docs/INSTALL.md: full install guide (Windows/Unix venv, pip install, Ollama setup, env-var table).
- docs/security/SECURITY_REVIEW.md: bandit audit record — 0 High/Medium findings.
- .github/workflows/ci.yml: adds bandit SAST gate (`bandit -r laew -lll`), sdist+wheel build, and fresh-venv wheel-install verification.

## Milestone 12 Implementation (Completed)

- laew/console/ (new package): `laew console` interactive REPL (`cmd.Cmd`, stdlib only) driving every implemented surface in one session — state (SessionState), session (ConsoleSession parse/dispatch/history/`!N`), and command handlers in commands/ (core, tool, agent, rag, automation).
- laew/runtime.py (new): shared runtime helpers extracted verbatim from cli.py (`provider_cfg_from_manifest`, `terminal_allowlist_from_manifest`, `resolve_model_name`) plus `build_provider` and `build_shared_tools`; CLI and console share the same config-resolution and tool-building code (DRY).
- laew/cli.py: `laew console` subcommand registers the console entry; chat/multiagent/tool/workflow import the shared runtime helpers.
- Console commands: `check`, `info`, `set`, `provider info|models|health|generate`, `tools`, `tool <name> <op> [k=v]`, `agent run|chat`, `trace on|off`, `rag query|embed|stats`, `workflow discover|show|run`, `multiagent discover|show|run`, `eval datasets|tasks|task|dataset`, `prompt list|show`, `budget`, `history`, `!N`, `help`, `exit`.
- Approval gates (P8) are togglable per session (`set approval auto|ask|deny`); all tool mutations still route through the `Tool` classes.
- Offline-first: manifest/tool/workflow/multiagent-parse/eval/prompt/budget commands work with Ollama down; provider, agent, and RAG-embed show `[!]` when unreachable.
- Tests: ~85 new unit tests across test_runtime.py + 7 console suites + CLI wiring (test_console_agent_cmds, test_console_automation_cmds, test_console_core_cmds, test_console_rag_cmds, test_console_session, test_console_tool_cmds).

## Milestone 6 Implementation (Completed)

- docker-compose.yml: ChromaDB service (`chromadb/chroma`) with a named volume for persistent storage, exposed on port 8000.
- laew/rag/vector_store.py: `ChromaVectorStore` — a persistent store mirroring the `VectorStore` interface, delegating to a remote ChromaDB collection via the HTTP client (cosine space, normalized embeddings).
- laew/rag/knowledge_base.py: `KnowledgeBase` now selects the store backend from manifest config (`rag.vector_store`); uses `ChromaVectorStore` when enabled and reachable, otherwise falls back to in-memory `VectorStore`.
- manifests/SYSTEM_MANIFEST.yaml: Added `rag.vector_store` section (`enabled`, `host`, `port`, `timeout`, `project_collection`, `global_collection`).
- setup.py: Added `chromadb>=0.4.0` to dev extras for the HTTP client.
- tests/unit/test_rag.py: Tests for `ChromaVectorStore` (skipped when chromadb absent) and manifest-config store selection with graceful fallback.

Audit remediation: all Critical (C1-C4), High (H1-H5), and Medium/Low (M1-M11, L1-L10) findings fixed with regression tests.
Full test suite: 557 passed, 1 skipped.

Total: 471 unit tests collected across 26 test suites (in tests/unit); 558 total tests collected.

## Important distinction

The architecture documentation describes the intended
LAEW v1.0 system.

The current repository represents the declarative foundation, tool runtime layer, CLI, LLM provider, prompt management, chief agent orchestration loop, knowledge retrieval (RAG) system, systematic evaluation harness, workflow automation runtime with approval gates and rollback, and multi-agent architecture with chief-agent coordination and specialist roles.

## Current Focus

Milestones 1–12 (through the Interactive Testing Console) are complete. LAEW is pip-installable (`pip install .` or `pip install laew`), has documented configuration (`LAEW_BASE_URL`, `LAEW_TIMEOUT`, `--provider`, `--timeout`), app-level logging, a bandit SAST gate in CI, and an interactive `laew console` REPL for exploratory testing of every implemented surface. The roadmap (`docs/ROADMAP.md`) sequences Milestones 13–21; the agreed next objective is **Milestone 13: Session Memory & Conversation Persistence** (durable, resumable agent sessions per ADR-012).