---
name: Current Project Status
description: Summary of LAEW's current implementation state, milestones, and progress.
type: status
scope: project
status: active
read_when:
  - understanding what is currently implemented
  - verifying repository state matches documentation
  - onboarding to the project
---

# LAEW — Current Project Status

## Status

2026-11-06 Memory Sufficiency and Horizon. The optional assessor evaluates
recalled Memory evidence before Global RAG fallback. The default heuristic
policy stays in effect unless model assessment is enabled. The opt-in
Horizon-preferred mode records NLI signals and keeps the usual RAG fallback.
See [Memory Sufficiency](memory-sufficiency.md), the
[Ornith evaluation](reports/MEMORY_SUFFICIENCY_ORNITH_20261106.md), and the
[Horizon service setup](../tools/horizon-sufficiency/README.md).

2026-11-06 Knowledge Routing reliability. The shared CLI and Workbench routing
recognizes more saved-context questions in Polish and English, and carries
source restrictions through short follow-ups. The isolated comparison
delivered all 57 historical evidence targets to the Chief adapter, up from 53.
See the [routing comparison](reports/KNOWLEDGE_ROUTING_RELIABILITY.md) and the
[follow-up evaluations](retrieval-reliability-evaluation.md).

2026-11-04 Global Knowledge Curation: conversation proposals, versioned Review,
approved Obsidian publication, and retryable Global RAG synchronization. See
[Global Knowledge Curation](architecture/GLOBAL_KNOWLEDGE_CURATION.md) and the
[Stage 2A audit](reports/GLOBAL_RAG_AUDIT.md).

2026-11-02 Long-Term Memory: SQLite records/revisions/sources, scoped semantic
recall with FTS5 fallback, durable extraction jobs and transactional index outbox,
Review/Auto/Off, shared Workbench/CLI integration, Settings memory management,
workspace defaults and per-project language/memory overrides. Theme now lives in
Settings; permission mode is a quick control on the chat heading.
Validation: **1101 passed, 4 skipped, 1 deselected** in the full offline suite;
**24 JavaScript tests passed**. The memory unit suite has **34 passing cases**.
Disposable real Chroma tests exercised scope filtering, stale/deleted records and
rebuild. Isolated Gemini 3.5 Flash Lite acceptance passed extraction, review,
indexing, fresh-conversation recall and preference replacement, with a 61-second
pause after each request. A preceding text-output attempt failed JSON validation
without advancing its checkpoint. Browser checks used only disposable fixture
histories, projects and SQLite. See [Long-Term Memory](architecture/LONG_TERM_MEMORY.md)
and [ADR-023](decisions/ADR-023-sqlite-long-term-memory.md) for the contract and limits.

Workbench Cloud Chat supports OpenAI API keys and official ChatGPT account
sign-in as isolated text-only conversations. It includes model selection,
streaming, Stop, token usage and protected OAuth sessions; it does not enable
cloud agents or local tools. See [configuration and limitations](CLOUD_CHAT.md).
Offline regression during implementation: **909 passed, 3 skipped, 1 deselected**;
additional targeted cloud/Workbench verification: **60 passed**. Browser checks
used a disposable fixture. Live account inference remains unverified because
no API key or LAEW ChatGPT login was configured.

Architecture: LAEW v1.0 documented
Implementation: Milestone 17 (Second Brain & Global Knowledge Integration) completed

## Current Focus

Milestones 1–17 are complete. Milestones 18–21 remain in progress. The local
workbench reuses the Chief Agent with project selection and scoped RAG sources.
The approved Polish Global Knowledge vault is populated, indexed and verified
against actual content. Operational monitoring, backup/retention and later
roadmap work remain outside M17 completion.

## Milestone Summary

| Milestone | Status | Date |
|-----------|--------|------|
| M01 — Declarative Foundation | ✅ Completed | 2026-08-25 |
| M02 — Tool Runtime Wrappers & Programmatic Security | ✅ Completed | 2026-08-28 |
| M03 — Chief Agent Runtime, LLM Provider & Orchestration | ✅ Completed | 2026-09-03 |
| M04 — Knowledge System & RAG Pipeline | ✅ Completed | 2026-09-06 |
| M05 — Documentation Synchronization & Integration Scaffold | ✅ Completed | 2026-09-03 |
| M06 — Audit Remediation & Technical Debt | ✅ Completed | 2026-09-09 |
| M07 — Single-Agent Stability & Hardening | ✅ Completed | 2026-09-09 |
| M08 — Evaluation Harness | ✅ Completed | 2026-09-09 |
| M09 — Automation & Workflow Runtime | ✅ Completed | 2026-09-09 |
| M10 — Multi-Agent Architecture | ✅ Completed | 2026-09-14 |
| M11 — Production Hardening | ✅ Completed | 2026-09-15 |
| M12 — Interactive Testing Console | ✅ Completed | 2026-09-15 |
| M13 — Session Memory & Conversation Persistence | ✅ Completed | 2026-09-15 |
| M14 — Performance & Context-Efficiency Audit | ✅ Completed | 2026-09-16 |
| M15 — Multi-Model Routing & Provider Fallback | ✅ Completed | 2026-09-16 |
| M16 — Parallel Multi-Agent Execution & Semantic Conflict Detection | ✅ Completed | 2026-09-16 |
| M17 — Second Brain & Global Knowledge Integration | ✅ Completed | 2026-10-29 |
| M18 — Monitoring, Telemetry & Backup | 🚧 In Progress | — |
| M19 — MCP Tools Layer | 🚧 In Progress | — |
| M20 — Multi-Project Workspace | 🚧 In Progress | — |
| M21 — v1.0 Stabilization & Release | 🚧 In Progress | — |

## Currently present in repository

- **README.md** — Project overview and quick start
- **manifests/SYSTEM_MANIFEST.yaml** — System manifest v1.0 (workspace boundaries, model roles, tool policies, memory layers, RAG configuration)
- **tools/** — Tool contracts for filesystem, git, terminal, web (each with CONTRACT.md and Python implementation)
- **prompts/** — Layered prompt templates (core.md, chief-agent.md, architecture.md, research.md, code-review.md, debugging.md, documentation.md, rag.md)
- **tests/** — Test specifications for security, agent, rag, workflow, multi-agent, console, CLI, web, benchmarking, and documentation validation (1015 unit tests across 52 suites)
- **docs/** — Architecture, principles, decisions, context, status, history, roadmap, performance, security, and source reference material
- **.claude/** — Agent SDK configuration, settings, prompts, and skills (project-sync, research, architecture-review)
- **laew/** — Python package (tool runtime wrappers, CLI, LLM provider, prompt management, agent loop, multi-agent coordination, RAG, workflow, evaluation)
- **pyproject.toml** — PEP 621 packaging metadata, console script, dev extras, bandit SAST config
- **setup.py** — Package installation compatibility shim for pip install laew

## Test Suite Summary

- 2026-10-31 vault reorganization (M17 stays completed): the same vault now has
  ten Markdown files and eight indexed documents/35 chunks. Global ingestion
  excludes Inbox, templates and auxiliary folders; the Polish README remains
  searchable. Eight concept questions and three live Chief answers used the
  expected new sources. The dedicated global validator did not synchronize
  project collections; subsequent regression exposed an unintended LAEW index
  refresh (321 to 329 chunks) through insufficiently isolated CLI boot tests.
  Those scheduler paths are now isolated; the incident is recorded in the report.
  See [the reorganization verification](roadmap/M17-Vault-Reorganization-2026-10-31.md).
  Final regression: **937 passed, 2 skipped, 1 deselected**; **9 UI tests passed**.
  Obsidian configuration/link checks passed statically; no GUI/plugin run is claimed.

- 2026-10-29 production acceptance: **M17 completed** after explicit content
  approval. The actual global vault contains nine Polish documents/31 chunks
  (six reusable materials, two approved profile notes, one preserved test note).
  Seven topic queries and two live Chief global/hybrid cases used expected
  production sources. A real document update synchronized correctly; unchanged
  synchronization generated zero embeddings. All indexed chunk texts/metadata
  matched the actual files. Broad paraphrases can still miss the most relevant
  source; the evidence and limitation are recorded in
  [the verification matrix](roadmap/M17-Knowledge-Preparation-2026-10-29.md).
  Post-deployment documentation/configuration/ingestion regression: **58 passed**;
  JavaScript syntax and `git diff --check` passed. The earlier 924-test broad
  regression remains the unchanged application-code baseline.

- Earlier 2026-10-29 knowledge organization preparation: standard academic project Studia,
  optional per-project RAG source selection, documented promotion/profile policy,
  six proposed shared materials and two profile drafts. Isolated real embeddings
  retrieved all six expected topic sources; two live Chief runs used the expected
  project/global citations. At that stage actual global content approval and
  deployment were pending; the production acceptance above supersedes that gate. See
  [the preparation verification](roadmap/M17-Knowledge-Preparation-2026-10-29.md).
  Final offline/component regression: **924 passed, 2 skipped, 1 deselected**;
  UI regression: **9 passed**. Studia's separate production collection contains
  two documents/five chunks; unchanged synchronization embedded zero chunks.
  Existing LAEW and global collection records/vectors were unchanged.

- **1015 unit tests** collected across **52 test suites** (in `tests/unit`)
- Earlier offline unit and component verification for M17: 887 passed, 2 skipped. Separate isolated live tests exercised ChromaDB, embeddings, the Chief Agent and a browser; M17 was still in progress at that stage.
- 2026-10-28/29 final verification: 826 passed, 2 skipped, 1 deselected for
  `tests/unit tests/integration -m "not ollama"`; a focused RAG, process,
  provider and Workbench run passed 137 tests, including a new partial-upsert
  crash test using an isolated HTTP Chroma server. Live project/global/hybrid
  retrieval evidence is in `runtime/m17-validation-e1e30ef7467f/report.json`.
  At that stage M17 remained in progress because the target global vault contained only a
  synthetic test note, not the populated curated vault its Definition of Done
  requires. That content gate is now satisfied by the production acceptance above.
- Earlier unit suite: 748 passed, 2 skipped. Earlier full suite: 873 passed, 3 skipped; the 38 warnings are ChromaDB telemetry deprecations for `asyncio.iscoroutinefunction`. See the dated result above for the current broader run.
- Bandit SAST: 0 High, 0 Medium findings over `laew/`

## What Is Implemented

- **Workbench permissions:** project-scoped Auto, Manual and Restricted modes,
  streaming approval requests, one-time and narrowly scoped session decisions.
  Terminal execution is intentionally limited to narrowly recognized inspection
  commands in Workbench and does not provide an OS sandbox.

- **Local web workbench MVP**: `laew ui` serves a loopback-only browser workspace with real provider/model status, Chief Agent message submission, and executor step summaries. See [ADR-020](decisions/ADR-020-local-web-application.md), [ADR-021](decisions/ADR-021-project-centric-engineering-workbench.md), and [UI Architecture](architecture/UI_ARCHITECTURE.md).

LAEW v1.0 implements:

- **Declarative foundation**: System manifest, tool contracts, layered prompts, test scenario specifications.
- **Tool runtime wrappers**: Filesystem (read-only defaults, mutation approval gates), Git (inspect-first, mutation gates, blocked destructive commands), Terminal (command allowlist, dangerous pattern blacklist), Web (markdown conversion, protocol restriction).
- **LLM provider abstraction**: Model-agnostic interface with Ollama implementation, context budgeting, layered prompts.
- **Chief agent loop**: Thought → Action → Observation → Response with structured JSON tool calling, repetition guards, and forced final-answer fallback.
- **Knowledge system & RAG**: Embedding service, in-memory vector store, knowledge base with scope separation (@project vs @knowledge), RAG pipeline with reranking and context synthesis.
- **Curated Global Knowledge and academic projects**: Approved Polish shared notes and minimal user profile; standard Studia project, per-project source selection, incremental synchronization and verified project/global/hybrid retrieval. Native-language source documents may retain their original language.
- **Evaluation harness**: Metrics, tasks, runner, and benchmark datasets.
- **Workflow automation**: YAML workflow definitions, sequential execution engine, approval gates, compensating rollback.
- **Multi-agent architecture**: Message protocol, shared context journal, specialist roles, chief coordinator, YAML plan schema.
- **Production hardening**: Provider registry with factory dispatch, config precedence (CLI > env > manifest > default), PEP 621 packaging, app-level logging, bandit SAST gate in CI.
- **Interactive console**: REPL driving all implemented surfaces with approval gates, session history, and !N replay.
- **Session persistence**: Durable conversation state with atomic writes and hardened path validation.
- **Performance optimizations**: O(n) context trimming (previously O(k²)), token calibration, streaming chat, pytest-benchmark baselines.
- **Parallel multi-agent execution**: Concurrent subtask execution with thread-safe shared context and semantic conflict detection.

## What Is Planned

Milestones 18–21 extend LAEW with:

- **M18** (Monitoring, Telemetry & Backup): Session observability, metrics collection, automated backups.
- **M19** (MCP Tools Layer): Model Context Protocol tool definitions and integration.
- **M20** (Multi-Project Workspace): Multi-root workspace management, cross-project knowledge discovery.
- **M21** (v1.0 Stabilization & Release): Comprehensive testing, documentation, and release preparation.

## Principles

LAEW is built on these core principles:

- **Model-agnostic**: The model is only one component; LAEW never depends on one specific LLM or provider.
- **Security below the model layer**: Programmatic security boundaries exist independent of model behavior.
- **Explicit context budgeting**: Context is a limited resource; budgeting prevents overflow.
- **Documentation as long-term memory**: Repository documentation is the project's persistent memory.
- **Sequential deployment**: Each milestone is independently verified before the next proceeds.
- **Infrastructure stability over feature breadth**: A stable foundation is built before adding complexity.
- **Single-agent stability before multi-agent**: A reliable single-agent baseline precedes multi-agent scaling.
- **Automation with fallback**: Automation operates with manual and disabled fallback modes.
- **Local-first**: Everything runs locally; no cloud account or API key is required for built-in providers.

## See Also

- [Architecture](architecture/README.md)
- [Decisions](decisions/README.md)
- [Roadmap](roadmap/README.md)
- [History](history/README.md)
- [Performance](performance/README.md)
- [Security](security/README.md)
- [Installation](INSTALL.md)


- manifests/SYSTEM_MANIFEST.yaml: Declarative specification of workspace boundaries, model roles, tool policies, memory layers, and RAG configuration.
- tools/: 4 modular tool contracts (`filesystem/CONTRACT.md`, `git/CONTRACT.md`, `terminal/CONTRACT.md`, `web/CONTRACT.md`).
- prompts/: 8 layered prompt templates (`core.md`, `chief-agent.md`, `architecture.md`, `research.md`, `code-review.md`, `debugging.md`, `documentation.md`, `rag.md`).
