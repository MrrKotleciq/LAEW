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
├── setup.py        # Package installation configuration
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
## Project Status

Current stage: Milestone 4 Complete (Foundation + Agent Runtime + RAG)

The repository implements:
- Declarative foundation with system manifest and tool contracts
- Tool runtime wrappers with programmatic security
- CLI, LLM provider abstraction, context budgeting, and agent orchestration
- RAG system with embeddings, vector store, knowledge base, and retrieval pipeline
- 245 unit tests across 12 test suites

See `docs/ROADMAP.md` for the development roadmap and future milestones.