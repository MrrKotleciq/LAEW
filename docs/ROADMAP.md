# LAEW Development Roadmap

## Current State (Audit Summary)
- Project stage: Foundation + Agent Runtime + RAG (all Milestones 1-4 complete)
- Test health: 266 unit tests passing
- Known gaps: documentation drift, no persistence, no evaluation, no multi-agent

## Roadmap Principles
- Stable foundations before features
- Security below model layer (P8)
- Model-agnostic architecture (P1)
- Single-agent stability before multi-agent (ADR-017)
- Sequential deployment stages with independent verification (ADR-013)

## Milestone 5: Documentation & Health Consolidation
Goal: Fix documentation drift, establish CI baseline, resolve tech debt.
Scope: README update, PROJECT_STATUS reconciliation, CHANGELOG cleanup, add integration test scaffold.
Dependencies: None.
Tests: Update existing tests if needed; add doc-validation tests.
Definition of Done: All docs match implementation; CI runs green; no stale claims.

## Milestone 6: Persistent Knowledge Store
Goal: Persist RAG embeddings across restarts; add incremental indexing.
Scope: Vector store persistence via Docker-hosted ChromaDB, knowledge base incremental load, manifest config for persistence path.
Dependencies: Milestone 4 (RAG pipeline) — already complete.
Tests: Unit tests for persistence layer; integration tests for incremental load.
Definition of Done: Embeddings survive restart; knowledge base updates without full rebuild.

## Milestone 7: Agent Robustness & Error Recovery
Goal: Make single-agent runtime resilient to failures.
Scope: Executor retry logic, LLM provider fallback (multiple providers), structured output validation, conversation history persistence.
Dependencies: Milestone 5 (docs/CI) for validation tests.
Tests: Fault injection tests; provider fallback tests; output validation tests.
Definition of Done: Agent recovers from transient failures; LLM provider can be swapped at runtime; output parsing failures are handled gracefully.

## Milestone 8: Evaluation Harness (Completed)
Goal: Systematic evaluation of agent and RAG quality.
Scope: Evaluation framework (task definitions, metrics, scoring), benchmark datasets (LAEW-specific and general), regression test suite.
Dependencies: Milestone 7 (robust agent) — satisfied.
Tests: Evaluation tests; regression detection.
Definition of Done: Evaluation suite runs; quantifiable scores produced; regression detection catches quality drops.

## Milestone 9: Automation & Workflow Runtime (Completed)
Goal: Execute multi-step engineering workflows with human oversight.
Scope: Workflow engine (ADR-015 modes), step definitions, approval gates, rollback capabilities.
Dependencies: Milestone 8 (evaluation) to measure workflow quality; Milestone 7 (robust agent) for reliable execution.
Tests: Workflow execution tests; approval gate tests; rollback tests.
Definition of Done: Can define and execute simple workflows; manual approval works; rollback possible.

## Milestone 10: Multi-Agent Architecture (Future)
Goal: Enable specialized agents (researcher, coder, reviewer) under chief agent coordination.
Scope: Agent communication protocol, task delegation, shared context, conflict resolution.
Dependencies: Milestone 9 (automation) for orchestration patterns; ADR-017 satisfied (single-agent stable).
Tests: Multi-agent coordination tests; delegation tests; conflict resolution tests.
Definition of Done: Two specialized agents can collaborate on a task; chief agent coordinates without single points of failure.

## Milestone 11: Production Hardening (Future)
Goal: Prepare for real-world usage beyond development.
Scope: Packaging (PyPI), installation guides, configuration management, logging/monitoring, security audit.
Dependencies: Milestone 10 (multi-agent) or earlier milestones if multi-agent deferred.
Tests: Installation tests; configuration tests; security tests.
Definition of Done: Can install via pip; documented configuration; security review passed.

## Architectural Decisions Requiring Approval
1. **Persistence backend**: SQLite+numpy vs other (e.g., Chroma, FAISS) — affects Milestone 6.
2. **Evaluation metrics**: What dimensions to measure (accuracy, latency, cost) — affects Milestone 8.
3. **Workflow engine design**: Simple sequential script — chosen for Milestone 9 (implemented). DAG/state machine deferred to future milestones.
4. **Multi-agent communication**: Shared memory vs message passing — affects Milestone 10.