# LAEW — Project Context

## 1. Project

LAEW means:

Local AI Engineering Workspace.

It is a self-hosted local AI environment intended to act as
a long-term engineering partner for software, electronics and
engineering projects.

The central architectural principle is:

> The model is only one component of the environment.

Project knowledge, documentation, memory and tools remain
outside the model and are provided when needed.

---

## 2. Goals

LAEW should provide:

- project-aware AI assistance,
- long-term engineering memory,
- access to project files and Git repositories,
- retrieval of relevant documentation and knowledge,
- controlled tool execution,
- engineering analysis and decision-making,
- modular and replaceable AI models,
- local-first operation with optional external APIs.

---

## 3. Architectural Philosophy

LAEW must not be designed around one specific model.

The intended architecture separates:

- agent/orchestration,
- knowledge,
- memory,
- tools,
- services,
- model providers.

A conceptual flow is:

User
  ↓
Agent
  ↓
Knowledge / Memory / Tools
  ↓
Services
  ↓
LLM

The model is replaceable.

Possible model roles include:

- Primary Model
- Embedding Model
- Future Specialist Models

The architecture should allow local and cloud models.

---

## 4. Second Brain

The knowledge system is intended to work together with
a Second Brain / Obsidian knowledge base.

The knowledge base should contain structured knowledge
rather than becoming a dumping ground.

Important conceptual areas include:

Knowledge/
Programming/
AI/
Linux/
Docker/
STM32/
Embedded/
Electronics/
Networking/
Mathematics/

University/
Research/
Hardware/
Books/
Decisions/
Templates/

Obsidian is intended to store knowledge, not source code.

Knowledge should be connected through links rather than
only through folders.

The purpose is a network of relationships between knowledge.

---

## 5. RAG

RAG is intended to function as an intelligent library.

The model should not receive an entire knowledge base.

Conceptual pipeline:

Documents
  ↓
Retrieval
  ↓
Candidate results
  ↓
Reranking
  ↓
Small relevant context
  ↓
LLM

The system should minimize unnecessary context.

A large context window does not mean that all available
information should always be provided to the model.

---

## 6. Context Budget

The architecture explicitly treats context as a limited resource.

Example conceptual budget:

System prompt       2k
Conversation         4k
RAG                 8k
Tool results        4k
-----------------------
Total              18k

The exact numbers are examples rather than implementation
requirements.

The principle is:

Do not maximize context merely because the model technically
supports a large context.

Leave room for reasoning and response generation.

---

## 7. Knowledge Priority

When sources conflict, the intended hierarchy is:

Repository
  ↓
Project documentation
  ↓
ADR
  ↓
Obsidian / project notes
  ↓
Internet / external documentation
  ↓
Model knowledge

The agent should report conflicts.

Example:

If README says one version but package.json shows another,
the agent should identify the discrepancy rather than
confidently inventing an explanation.

---

## 8. Source Awareness

The agent should distinguish:

FACT
Directly supported information.

INFERENCE
A conclusion derived from facts.

HYPOTHESIS
An explanation that has not been verified.

The agent should make uncertainty visible.

Whenever practical, answers should identify their source,
for example:

src/scheduler.c:142

---

## 9. Prompt Architecture

The project explicitly rejects one gigantic system prompt.

The intended approach is layered instructions.

Conceptually:

Second Brain
    ↓
Knowledge Layer
    ↓
RAG
    ↓
Agent
    ↓
Tools / MCP
    ↓
LLM

Instructions form another layer around the agent.

This is intended to reduce context bloat and allow
specialized behavior.

---

## 10. Automation

Automation is part of LAEW architecture.

The system should eventually automate repetitive tasks
while preserving user control and safety.

Automation should not bypass the architectural security model.

---

## 11. Scaling

LAEW v1.0 is designed so that scaling happens by adding
components rather than turning one component into a giant
system.

The intended direction is:

LAEW Core
  ├── Project A
  │     └── RAG
  ├── Project B
  │     └── RAG
  └── Project C
        └── RAG

The architecture should eventually support:

- multiple projects,
- multiple repositories,
- thousands of notes,
- large documentation sets,
- multiple models,
- multiple knowledge bases,
- multiple agents.

---

## 12. Final v1.0 Architecture

The documented architecture ultimately includes:

TOOLS
  ├── Git
  ├── Files
  └── Web

RAG
  └── Vector DB

MEMORY
  ├── Session
  └── Obsidian

These produce:

CONTEXT
  ↓
MODEL ROUTER
  ├── LOCAL LLM
  ├── LOCAL LLM
  └── CLOUD API

The whole system is surrounded by:

- Security
- Monitoring
- Backup
- Automation
- Evaluation
- Version Control

---

## 13. Architecture Status

The architecture documentation defines LAEW v1.0.

The repository currently represents the implementation
foundation rather than a completed implementation of every
component described by the architecture.

This distinction is critical.

Do not claim that RAG, memory, model routing, MCP, automation
or other components are implemented merely because they are
defined in the architecture.

Verify the repository before making implementation claims.
