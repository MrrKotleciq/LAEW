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
├── configs/        # System configuration
├── docker/         # Infrastructure and container configuration
├── docs/           # Project documentation
├── manifests/      # System manifests
├── prompts/        # Version-controlled prompts
├── scripts/        # Automation and validation scripts
├── tests/          # Agent, RAG, security and workflow tests
├── tools/          # Tool contracts and implementations
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

Current stage: Foundation / Architecture

The repository currently contains the initial project structure and architecture specification. Implementation is being developed incrementally.