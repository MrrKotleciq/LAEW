---
type: roadmap
id: M03
title: Chief Agent Runtime, LLM Provider & Orchestration
status: completed
purpose: Implement the model-agnostic LLM provider interface, context budgeting, layered prompt loading, and the chief agent execution loop (Thought → Action → Observation → Response).
read_when:
  - working on the agent loop, LLM provider, or prompt management
  - understanding context budgeting or tool calling
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
