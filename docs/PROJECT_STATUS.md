# LAEW — Current Project Status

## Status

Architecture: LAEW v1.0 documented
Implementation: Milestone 6 (Persistent Knowledge Store) completed

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
- setup.py (Package installation configuration)

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
- laew/cli.py: Command-line interface with `laew check` (manifest validation) and `laew tool` (tool execution) commands (16 unit tests)

## Milestone 3 Implementation (Completed)

- laew/llm/base.py: LLM provider abstract interface with MessageRole, LLMMessage, LLMResponse, and LLMProvider per ADR-001 (10 unit tests)
- laew/llm/ollama.py: Ollama local LLM provider with chat generation, model listing, health checks, and model pulling
- laew/prompts/context_budget.py: Context budgeting per ADR-004 and TokenEstimator heuristic (~4 chars/token)
- laew/prompts/loader.py: Layered prompt loader supporting single-file and directory-based section composition (45 unit tests for prompts module)
- laew/prompts/templates.py: Prompt template registry with {{variable}} substitution and validation
- laew/agent/base.py: Agent base class, AgentConfig, AgentRole enum, and history management
- laew/agent/executor.py: AgentExecutor orchestration loop (Thought -> Action -> Observation -> Response) with tool calling via JSON blocks (26 unit tests)
- laew/rag/embedding.py: EmbeddingService abstract interface and OllamaEmbedding implementation (20 unit tests)
- laew/rag/vector_store.py: In-memory vector store with cosine similarity search (8 unit tests)
- laew/rag/knowledge_base.py: Knowledge loading from project memory and global knowledge sources (4 unit tests)
- laew/rag/pipeline.py: RAG pipeline orchestrating retrieval, reranking, and context injection (4 unit tests)
- laew/rag/rag_tool.py: Tool wrapper for agent RAG queries (3 unit tests)
- laew/rag/__init__.py: Module exports

## Milestone 5 Implementation (Completed)

- README.md: Updated to reflect actual repository structure (removed stale references to non-existent `configs/`, `docker/`, `scripts/` directories).
- docs/ROADMAP.md: New development roadmap with milestones 5–11 in dependency order.
- docs/history/CHANGELOG.md: Rewritten with correct chronological order and complete sections for Milestones 1–4 plus the code audit.
- tests/unit/test_integration_scaffold.py: Integration tests verifying agent + tools, agent + RAG, RAG + knowledge base + embeddings, and CLI + tools work together.
- tests/unit/test_documentation_validation.py: Tests ensuring README, PROJECT_STATUS, and manifest accurately reflect repository state.
- .github/workflows/ci.yml: CI baseline running the full test suite on push and pull request.

## Milestone 6 Implementation (Completed)

- docker-compose.yml: ChromaDB service (`chromadb/chroma`) with a named volume for persistent storage, exposed on port 8000.
- laew/rag/vector_store.py: `ChromaVectorStore` — a persistent store mirroring the `VectorStore` interface, delegating to a remote ChromaDB collection via the HTTP client (cosine space, normalized embeddings).
- laew/rag/knowledge_base.py: `KnowledgeBase` now selects the store backend from manifest config (`rag.vector_store`); uses `ChromaVectorStore` when enabled and reachable, otherwise falls back to in-memory `VectorStore`.
- manifests/SYSTEM_MANIFEST.yaml: Added `rag.vector_store` section (`enabled`, `host`, `port`, `timeout`, `project_collection`, `global_collection`).
- setup.py: Added `chromadb>=0.4.0` to dev extras for the HTTP client.
- tests/unit/test_rag.py: Tests for `ChromaVectorStore` (skipped when chromadb absent) and manifest-config store selection with graceful fallback.

Total: 266 unit tests passing across 14 test suites

## Important distinction

The architecture documentation describes the intended
LAEW v1.0 system.

The current repository represents the declarative foundation, tool runtime layer, CLI, LLM provider, prompt management, chief agent orchestration loop, and knowledge retrieval (RAG) system;
workflow automation capabilities are planned for future milestones.

## Current Focus

Having completed Milestones 1-6, the project is ready to begin Milestone 7 per
`docs/ROADMAP.md`. The RAG knowledge store now persists embeddings across restarts
via a Docker-hosted ChromaDB instance, with graceful fallback to the in-memory store
when the container is not running.