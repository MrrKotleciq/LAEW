# LAEW Project History & Evolution

This document records significant milestone completions, conceptual shifts, and evolutionary decisions in the LAEW project.
For detailed code and file diffs, refer to Git commit history.

---

## [2026-08-25] Milestone 1: Declarative Foundation Completed

- **Context & Motivation**:
  Establish a formal ground truth specification, security policies, and tool contracts before writing executable runtime engines, ensuring the workspace remains model-agnostic and secure below the model layer.
- **Key Achievements**:
  - Authored system manifest (`manifests/SYSTEM_MANIFEST.yaml`) defining workspace boundaries, model roles, tool policies, memory layers, and RAG configuration.
  - Defined 4 modular tool contracts (`tools/filesystem/CONTRACT.md`, `tools/git/CONTRACT.md`, `tools/terminal/CONTRACT.md`, `tools/web/CONTRACT.md`).
  - Created 8 layered prompt templates in `prompts/` (`core.md`, `chief-agent.md`, `architecture.md`, `research.md`, `code-review.md`, `debugging.md`, `documentation.md`, `rag.md`).
  - Formulated 16 test scenario specifications across security, agent behavior, RAG, and workflow in `tests/`.
  - Committed baseline foundation to version control (`commit 653b28d`).
- **Decisions & Consequences**:
  - Established individual ADR records (`docs/decisions/README.md`).
  - Adopted English language convention for all repository artifacts (ADR-007).
  - Adopted modular tool contract layout (ADR-008).
  - Established documentation as long-term memory via `project-sync` (ADR-009).

---

## [2026-08-28] Milestone 2: Tool Runtime Wrappers & Programmatic Security Completed

- **Context & Motivation**:
  Implement security-enforced tool execution engines and manifest validation before building agent orchestration, ensuring the workspace operates securely below the model layer (Principle P8) with programmatic security boundaries.
- **Key Achievements**:
  - Implemented manifest validation engine (`laew/manifest.py`) with schema verification for workspace boundaries, model roles, tool policies, memory layers, and RAG configuration.
  - Implemented multi-root workspace resolver (`laew/security/path_resolver.py`) with ADR-010 path aliasing (@project, @projects, @knowledge), path traversal prevention, and sensitive file blacklisting.
  - Implemented abstract Tool base class (`laew/tools/base.py`) with standardized ToolResult and ErrorCode enum aligned with tool contracts.
  - Implemented filesystem tool (`laew/tools/filesystem.py`) with read-only defaults, mutation approval gates, and @project-only write constraints.
  - Implemented git tool (`laew/tools/git.py`) with inspect-first policy, mutation approval gates, blocked destructive subcommands, and LC_ALL=C locale enforcement.
  - Implemented terminal tool (`laew/tools/terminal.py`) with command allowlists, dangerous pattern blacklists, and workspace boundary confinement.
  - Implemented web tool (`laew/tools/web.py`) with markdown conversion, protocol restriction, and web search interface.
  - Created 124 unit tests across 6 test suites covering manifest validation, path resolution, and all 4 tool wrappers.
  - Added `setup.py` for package installation.
- **Decisions & Consequences**:
  - Established programmatic security below the model layer (Principle P8) with deny-by-default for destructive operations.
  - Implemented ADR-010 path aliasing with traversal prevention and restricted path enforcement.
  - Implemented approval gates for filesystem mutations, git state changes, and non-allowlisted terminal commands.
  - Standardized error handling with ToolResult and ErrorCode enum across all tools.
  - Added diagnostic logging capability foundation (preparing for ADR-016 structured tool invocation logging).

---

## [2026-09-03] Milestone 3: Chief Agent Runtime, LLM Provider & Orchestration Completed

- **Context & Motivation**:
  Build the chief agent orchestration layer that integrates LLM providers, context budgeting, prompt management, and tool execution, enabling the core agent loop (Thought → Action → Observation → Response) with structured tool calling.
- **Key Achievements**:
  - Implemented LLM provider abstraction (`laew/llm/base.py`) with MessageRole, LLMMessage, LLMResponse, and LLMProvider interface per ADR-001 model abstraction.
  - Implemented Ollama provider (`laew/llm/ollama.py`) with chat generation, model listing, health checks, and model pulling for local LLM support.
  - Implemented context budgeting (`laew/prompts/context_budget.py`) per ADR-004 with TokenEstimator heuristic (~4 chars/token).
  - Implemented layered prompt loader (`laew/prompts/loader.py`) supporting single-file and directory-based section composition.
  - Implemented prompt template system (`laew/prompts/templates.py`) with {{variable}} substitution and validation.
  - Implemented CLI commands (`laew/cli.py`): `laew check` for manifest validation and `laew tool` for tool execution with optional logging.
  - Implemented ADR-016 structured tool invocation logging in `laew/tools/base.py`.
  - Implemented agent base (`laew/agent/base.py`) with AgentConfig, AgentRole enum, and history management.
  - Implemented agent executor (`laew/agent/executor.py`) with orchestration loop parsing JSON tool_call blocks.
  - Created 100 new unit tests across 4 test suites (10 LLM, 45 prompts, 16 CLI, 26 agent, 4 logging).
- **Decisions & Consequences**:
  - Established model-agnostic LLM provider interface enabling swap between Ollama, OpenAI, or other providers (ADR-001).
  - Established explicit context budgeting preventing context window overflow (ADR-004).
  - Established single-agent stability prerequisite before multi-agent consideration (ADR-017).
  - Tool calling via structured JSON blocks in LLM responses, parsed by regex pattern.
  - Conversation history preserved across agent runs for multi-turn interactions.

---

## [2026-09-03] Documentation Synchronization: ADRs 012–017 Formalized

- **Context & Motivation**:
  Synchronize architectural decisions from 13 source chapters analysis with actual repository state, formalizing decisions that were previously documented but not captured as individual ADRs.
- **Key Achievements**:
  - Created ADR-012: Agent Memory vs Current State Separation (verifying current state from Git/filesystem, not memory).
  - Created ADR-013: Sequential Deployment Stages with Independent Verification.
  - Created ADR-014: Infrastructure Stability Over Feature Breadth.
  - Created ADR-015: Automation with Manual and Disabled Fallback Modes.
  - Created ADR-016: Structured Tool Invocation Logging.
  - Created ADR-017: Single-Agent Stability Before Multi-Agent.
  - Updated ADR index (README.md) with ADRs 012–017.
- **Decisions & Consequences**:
  - Established formal architectural decisions for deployment sequencing, infrastructure prioritization, automation modes, diagnostic logging, and agent evolution path.
  - Rejected/merged 20+ candidates from 13-chapter analysis into existing ADRs or non-architectural categories.

---

## [2026-09-06] Milestone 4: Knowledge System & RAG Pipeline Completed

- **Context & Motivation**:
  Implement the persistent knowledge retrieval subsystem enabling project-scoped, global-scoped, and hybrid-scoped retrieval with vector embeddings, semantic search, cosine similarity reranking, and context injection respecting token budgets (ADR-002, ADR-003, ADR-011).
- **Key Achievements**:
  - Implemented `EmbeddingService` interface and `OllamaEmbedding` provider (`laew/rag/embedding.py`) supporting local embedding models (e.g. `nomic-embed-text:latest`).
  - Implemented in-memory `VectorStore` (`laew/rag/vector_store.py`) with cosine similarity search and scope-based filtering using numpy.
  - Implemented `KnowledgeBase` (`laew/rag/knowledge_base.py`) with automatic Markdown file discovery, section-aware splitting, chunking with overlap, and multi-scope separation (`@project` vs `@knowledge`).
  - Implemented `RAGPipeline` (`laew/rag/pipeline.py`) orchestrating candidate retrieval, similarity reranking, and context synthesis with source attribution within `max_context_tokens` budget.
  - Implemented `RagTool` (`laew/rag/rag_tool.py`) as an agent-callable tool for on-demand knowledge retrieval.
  - Updated `manifests/SYSTEM_MANIFEST.yaml` with explicit embedding model configuration (`nomic-embed-text:latest`, target dimension 768).
  - Created 20 unit and integration tests (`tests/unit/test_rag.py`) covering all RAG subsystem components.
- **Decisions & Consequences**:
  - Preserved clear separation between project memory (`@project`) and global Obsidian vault knowledge (`@knowledge`) per ADR-011.
  - Enforced structured source attribution (`[SOURCE: file_path > section_header]`) on all retrieved context.
  - Adhered to strict context budgeting constraints per ADR-004 during context assembly.

---

## [2026-09-06] Code Audit: Technical Debt Refactoring

- **Context & Motivation**:
  Comprehensive code audit identified duplicated approval-checking logic across all tool implementations, violating DRY principle and creating maintenance burden. Critical issues in executor.py (incorrect ToolResult construction) and test platform compatibility (MSYS path handling) were also addressed.
- **Key Achievements**:
  - Added shared `_check_operation_approval` method to base `Tool` class (`laew/tools/base.py`) consolidating duplicated approval logic
  - Added `_validate_mutation_operation` helper in `FilesystemTool` combining approval checking with path validation
  - Refactored `FilesystemTool`, `GitTool`, and `TerminalTool` to use shared approval-checking mechanism
  - Fixed `AgentExecutor` ToolResult construction using correct `error_code`/`error_message` fields
  - Added MSYS path normalization for cross-platform test compatibility in terminal tests
  - Verified all 245 unit tests pass with no regressions
- **Decisions & Consequences**:
  - Established single source of truth for approval logic in base `Tool` class, reducing code duplication across tools
  - Preserved all existing security semantics while improving maintainability
  - Maintained backward compatibility with existing tool interfaces and error handling patterns

---

## [2026-09-09] Milestone 8: Evaluation Harness Completed

- **Context & Motivation**:
  Establish systematic, quantitative evaluation of agent and RAG quality to enable regression detection ahead of workflow automation work.
- **Key Achievements**:
  - Implemented evaluation framework (`laew/eval/`) with evaluation metrics (`metrics.py`), task definitions and registry (`tasks.py`), and an agent/RAG evaluation runner (`runner.py`).
  - Added benchmark datasets for LAEW-specific and general tasks (`laew/eval/datasets/`).
  - Added evaluation test suites (`tests/evaluation/test_evaluation_framework.py`, `tests/evaluation/test_benchmark_datasets.py`).
- **Decisions & Consequences**:
  - Evaluation produces quantifiable scores, enabling regression detection that protects agent and RAG quality during future development.

---

## [2026-09-09] Milestone 9: Automation & Workflow Runtime Completed

- **Context & Motivation**:
  Execute multi-step engineering workflows with human oversight, per ADR-015 (automation with manual and disabled fallback modes), building on the robust single-agent runtime (ADR-017).
- **Key Achievements**:
  - Implemented workflow runtime (`laew/workflow/`) with workflow definitions and step types (`definition.py`), execution engine (`engine.py`), approval gates (`approval.py`), compensating rollback actions (`rollback.py`), error types (`exceptions.py`), and YAML workflow loading (`yaml_loader.py`).
  - Added CLI entry point `laew workflow run` for executing YAML-defined workflows.
  - Added workflow test suite (`tests/workflow/test_workflow_engine.py`) and YAML workflow fixtures covering simple, approval-gated, agent, and rollback workflows.
- **Decisions & Consequences**:
  - Simple sequential script selected as the workflow engine design for Milestone 9; DAG/state-machine orchestration deferred to future milestones.
  - Human-in-the-loop approval gates and compensating rollback enable manual fallback modes per ADR-015.

---

## [2026-09-09] Feature: Interactive Chat CLI (`laew chat`)

- **Context & Motivation**:
  Provide an interactive, conversational entry point to the local-model-powered chief agent runtime, complementing the single-shot `laew tool` command.
- **Key Achievements**:
  - Added `laew chat` subcommand to `laew/cli.py`, wiring `OllamaProvider`, `Agent`, and `AgentExecutor` into a persistent multi-turn chat loop.
  - Model selection via `--model`, the manifest primary provider (`agent.llm.providers[0].model`), or a `llama3.1` default; configurable Ollama base URL (`--base-url`) and manifest (`--manifest`).
  - Graceful handling of unavailable Ollama instances and clean session exit (`exit`/`quit`/EOF/`Ctrl+C`).
  - Added `TestChatCommand` unit coverage (happy-path loop, missing manifest, no-LLM-available), bringing the unit suite to 287 tests.
- **Decisions & Consequences**:
  - Reuses the existing provider abstraction (ADR-001) and single-agent executor (ADR-017); no new architectural decision introduced.
  - Exposes the agent loop to interactive terminal use for the first time.

---

## [2026-09-10] Fix: Tool-Calling Reliability in Agent Executor

- **Context & Motivation**:
  `laew chat` sessions with `llama3.2:latest` produced malformed tool calls and mid-conversation give-ups. Two distinct defects surfaced: (1) the model emitted raw shell commands (`ls -l`, `dir`) in the tool `operation` field because the executor's introspection never advertised the terminal tool's valid operation, and (2) after the operations were advertised, the model would call `{"tool": "terminal", ...}` only to have it rejected — the tool registry keys are PascalCase class names (`TerminalTool`), while the executor's example tool calls taught the model lowercase names (`terminal`), so valid-looking calls hit "Tool 'terminal' not found" and the model concluded "none of the tools are available."
- **Key Achievements**:
  - TerminalTool gained an explicit `operations` dict (`run_command(command, cwd, timeout_ms)`), and the executor's `_operation_hints()` now prefers it over method-surface introspection, so the real operation contract is advertised to the model.
  - Fixed the tool-name mismatch: system-prompt examples now show the exact registry keys (`FilesystemTool`, `TerminalTool`, `GitTool`), and the executor resolves case variants of tool names so `"terminal"` still maps to `TerminalTool` — eliminating the spurious "Tool not found" give-up.
  - Expanded the executor system prompt with concrete `tool_call` examples and explicit instructions forbidding raw shell commands, plus guidance to stop and answer once a tool call succeeds instead of repeating calls until `max_iterations`.
  - Added a repetition guard (`_is_repeating`, default limit 3) that detects when the model calls the identical tool+operation consecutively, injecting a corrective instruction to stop calling tools and synthesize an answer from gathered data.
  - Added a forced final-answer fallback at `max_iterations`: prompts the model one last time to write a plain-text answer from accumulated context, converting over-researching failures into usable responses (while rejecting outputs that still look like tool calls).
  - Hardened the malformed-call safety net: `_looks_like_tool_call_attempt()` now also flags raw shell commands in fenced code blocks (e.g. ```ls -l```), feeding a corrective user message back to the model instead of treating them as a final answer.
  - Added `dir` to the `TerminalTool.ALLOWLIST` for Windows compatibility (safe read-only directory listing).
  - Verified: 312 unit tests pass; a live `laew chat` session now issues valid `FilesystemTool list_dir` and `GitTool git_status` calls, stops appropriately, and breaks out of failing repeated tool loops to produce a plain-text answer.
- **Decisions & Consequences**:
  - Kept the structured-JSON `tool_call` protocol rather than switching to native Ollama JSON-mode tool calling, preserving model/provider independence (ADR-001).
  - Corrective feedback loop remains in-band (messages), so multi-turn history stays coherent for the model.