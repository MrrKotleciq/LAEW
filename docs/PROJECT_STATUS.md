# LAEW — Current Project Status

## Status

Architecture: LAEW v1.0 documented
Implementation: Milestone 16 (Parallel Multi-Agent Execution & Semantic Conflict Detection) completed

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

## Milestone 13 Implementation (Completed)

- laew/console/session_store.py (new): Durable session persistence layer — `SessionStore` CRUD (save/load/list/delete/exists), path-traversal-safe name validation, atomic writes (tempfile + `os.replace`), best-effort file/directory permission hardening, `SessionRecord` metadata, `make_chat_payload` and `validate_conversation` helpers, `session_store_from_manifest` storage resolver.
- laew/console/state.py (extended): `SessionState.to_payload()` / `from_payload()` / `restore()` / `conversation_to_messages()` for serializing and resuming console session memory (overrides, approval, trace, history, conversation turns) without persisting project state (ADR-012).
- laew/console/commands/sessions.py (new): `session save|load|list|show|delete` command handlers; `_resolve_store` for manifest-to-store resolution with offline fallback; ADR-012 manifest re-verification on load.
- laew/console/commands/agent.py (extended): `_build_agent` seeds `agent.history` from `state.conversation_to_messages()`; `_record_exchange` persists user/assistant final responses to `state.conversation` after each successful run or chat turn.
- laew/cli.py (extended): `--resume`, `--session`, `--no-persist` flags for `laew chat`; seeds agent history from resumed conversation; persists exchanges after each turn via `make_chat_payload` + `SessionStore.save`.
- Payload schema: `laew.session.state` version 1 with `schema`, `version`, `kind` ("console"|"chat"), `manifest_path`, `overrides`, `approval`, `trace`, `history`, `conversation` fields; `created_at`/`updated_at` lifecycle timestamps (microsecond precision, ISO-8601 UTC).
- Security: session names validated via `^[A-Za-z0-9][A-Za-z0-9._-]*$`; all writes go through tempfile + `os.replace` for crash safety; file permissions set to `0o600` / `0o700` best-effort.
- Tests: test_session_store.py (45 tests: name validation, CRUD, atomic writes, corrupt handling, permissions, isolation, payload validation, timestamps, SessionRecord), test_console_session_cmds.py (18 tests: dispatcher, save/load/list/show/delete handlers, ADR-012 manifest re-verification), CLI resume/session/no-persist tests in test_cli.py (4 tests).

## Milestone 14 Implementation (Completed)

- Stream A — Benchmark fixtures + profiling: `pytest-benchmark>=4.0.0` added to dev extras; `tests/benchmarks/` (new, offline — no network, no models) with three suites: `test_profile_agent_executor.py` (full `AgentExecutor.run()` over a scripted stub provider, plus the cached system-prompt path), `test_profile_rag_retrieval.py` (in-memory cosine retrieval, ten-search batch, index build), `test_profile_workflow_dispatch.py` (sequential no-op plans). Numbers recorded in docs/performance/BASELINE.md (informational tolerances — record, not gate).
- Performance bug found & fixed: `AgentExecutor._trim_to_budget` was O(k²) — it re-joined/estimate-scanned the whole message list after every dropped turn. Rewritten as a single O(n) char-length pass (executor.py: `_message_char_count`/`_estimate_chars` helpers + linear trimming). Verified with a 5000-call growth script: worst single call 61.6 ms at 10 010 turns, no quadratic blow-up.
- Agent benchmark restructured: each measured round runs a fresh executor via `benchmark.pedantic(..., setup=...)` (setup runs per round, outside the timing window). An earlier draft reused one executor across rounds, compounding history and hanging the suite; agent full-run now isolates at ~133 µs mean, cache-hit at ~22 µs/run.
- Stream B — Token-estimator accuracy: `TokenEstimator.estimate(text, chars_per_token=None)` keeps the 4.0 default with a data-driven override; new `TokenCalibrator` records (estimated, actual) pairs and fits the best chars-per-token; `calibrate_with_ollama()` in ollama.py hits the `/api/tokenize` endpoint over a fixed probe corpus (offline-skipped when Ollama is unreachable).
- Stream C — Prompt/context caching + token accounting + budget enforcement: system prompt (static text + tool descriptions + instruction block) extracted into `_build_system_prompt()`, memoized once per executor so `inspect.signature()`-based operation hints run only on first call; `ExecutionResult` extended with `prompt_tokens`/`completion_tokens`/`total_tokens` accumulated from real provider counts after each `generate()`; `ContextBudget` loaded from the manifest into the executor, with estimated-token budget trimming of oldest conversation turns (never the system prompt or live user turn) plus a WARNING log; `AgentConfig` carries an optional `context_budget`. Console `agent run`/`chat` and CLI `chat` surfaces print prompt/completion tokens alongside elapsed time.
- Stream D — Streaming chat: abstract `generate_stream()` on `LLMProvider`; `OllamaProvider.generate_stream()` posts `/api/chat` with `stream: True`, yields content chunks per NDJSON frame, and assembles a terminal `LLMResponse` (prompt/eval counts + done reason) from the final `done` frame; mid-stream failures map to `LLMError(code="STREAM_ERROR")`. `laew chat` streams by default with a `--no-stream` escape; console `agent chat` streams too. Streaming path feeds the same token accounting as `generate()`.
- Tests: +24 unit tests across test_context_budget.py, test_agent_executor.py, test_agent.py, test_ollama.py, test_llm.py, test_prompts.py (calibration convergence, budget trimming, cached-prompt non-rebuild, token accumulation, streaming NDJSON parse + mid-stream error), plus 7 offline benchmark hooks in tests/benchmarks/.

## Milestone 6 Implementation (Completed)

- docker-compose.yml: ChromaDB service (`chromadb/chroma`) with a named volume for persistent storage, exposed on port 8000.
- laew/rag/vector_store.py: `ChromaVectorStore` — a persistent store mirroring the `VectorStore` interface, delegating to a remote ChromaDB collection via the HTTP client (cosine space, normalized embeddings).
- laew/rag/knowledge_base.py: `KnowledgeBase` now selects the store backend from manifest config (`rag.vector_store`); uses `ChromaVectorStore` when enabled and reachable, otherwise falls back to in-memory `VectorStore`.
- manifests/SYSTEM_MANIFEST.yaml: Added `rag.vector_store` section (`enabled`, `host`, `port`, `timeout`, `project_collection`, `global_collection`).
- setup.py: Added `chromadb>=0.4.0` to dev extras for the HTTP client.
- tests/unit/test_rag.py: Tests for `ChromaVectorStore` (skipped when chromadb absent) and manifest-config store selection with graceful fallback.

Audit remediation: all Critical (C1-C4), High (H1-H5), and Medium/Low (M1-M11, L1-L10) findings fixed with regression tests.

## Milestone 15 Implementation (Completed)

- laew/llm/registry.py: Provider registry extended with `get_provider_for_role(role, manifest, base_url, timeout, _registry)` implementing manifest-driven role dispatch across `primary`, `embedding`, `reviewer` roles per ADR-001/ADR-019. Tries ordered provider candidate list sequentially with error accumulation; raises typed `LLMError` codes (`NO_PROVIDER_FOR_ROLE`, `PROVIDER_NOT_FOUND`, `ALL_PROVIDERS_FAILED`).
- laew/runtime.py: Added `build_provider_for_role(manifest, role, base_url, timeout, _registry)` as the shared entry point for role-based provider resolution across CLI commands and console commands.
- laew/manifest.py: Enhanced schema validation to verify `agent.llm.roles` structure and ensure all referenced provider names exist within declared `agent.llm.providers`.
- laew/cli.py & laew/console/commands/agent.py: Refactored `cmd_chat`, `cmd_multiagent_run`, and console `_build_agent` to construct providers via `build_provider_for_role(manifest, "primary", ...)` preserving config precedence.
- manifests/SYSTEM_MANIFEST.yaml: Primary provider switched to `qwen2.5-coder:7b` for reliable agent reasoning and tool dispatch.
- Tests: `tests/unit/test_routing.py` (16 unit tests: role dispatch, fallback sequence, error handling, manifest validation, CLI integration, and override precedence).

## Milestone 16 Implementation (Completed)

- laew/multiagent/context.py: `SharedContext` journal made thread-safe with `threading.RLock()` protecting all mutations and reads (`post`, `get`, `all_for`, `keys`, `render`, `clear`, `__len__`) during concurrent specialist execution.
- laew/multiagent/coordinator.py: `MultiAgentCoordinator.run()` extended with `parallel=True` and `max_workers` parameters using `concurrent.futures.ThreadPoolExecutor` for concurrent subtask delegation while preserving per-specialist isolation (`AgentExecutor` per delegation, principle P8); deterministic result ordering maintained via pre-indexed collection matching `plan.subtasks`.
- Semantic conflict detection: `_detect_conflicts_semantic()` using `EmbeddingService.embed_batch()` and pairwise cosine similarity (`_cosine_similarity()`) against configurable `conflict_threshold` (default 0.85); resilient fallback to normalized text comparison (`_detect_conflicts_text()`) when embeddings fail or are omitted.
- Tests: `tests/unit/test_multiagent_parallel.py` (7 unit tests: deterministic parallel execution, shared-context thread safety under concurrent writes, semantic conflict detection on divergent outputs, semantic matching, error handling with graceful fallback, and helper functions).

Total: 609 unit tests collected across 30 test suites (in tests/unit).

## Important distinction

The architecture documentation describes the intended
LAEW v1.0 system.

The current repository represents the declarative foundation, tool runtime layer, CLI, LLM provider, prompt management, chief agent orchestration loop, knowledge retrieval (RAG) system, systematic evaluation harness, workflow automation runtime with approval gates and rollback, multi-agent architecture with chief-agent coordination and specialist roles, and manifest-driven role-based provider routing with ordered fallback.

## Current Focus

Milestones 1–15 are complete through Multi-Model Routing & Provider Fallback. LAEW is pip-installable (`pip install .` or `pip install laew`), has documented configuration (`LAEW_BASE_URL`, `LAEW_TIMEOUT`, `--provider`, `--timeout`), app-level logging, a bandit SAST gate in CI, an interactive `laew console` REPL, durable session persistence (`session save|load|list|show|delete`), offline benchmark baselines (docs/performance/BASELINE.md, `pytest tests/benchmarks`), calibrated token estimation, real prompt/completion token accounting with context-budget enforcement, streaming chat (`laew chat` defaults to streaming; `--no-stream` escapes), and manifest-driven provider dispatch across model roles with fallback chains. The roadmap (`docs/ROADMAP.md`) sequences Milestones 16–21; the agreed next objective is **Milestone 16** (documented in ROADMAP.md).