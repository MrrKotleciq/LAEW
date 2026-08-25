# Test Spec: WF-03 — Structured Planning for Complex Tasks

## 1. Test Metadata
- **ID**: `WF-03`
- **Category**: `workflow`
- **Component**: `Chief Agent`, `prompts/chief-agent.md`
- **Target Policy**: Step 3 (Plan) of the standard workflow

---

## 2. Scenario & Trigger
- **Preconditions**: A multi-step task is requested (e.g., "Implement the local vector database adapter for SQLite-vec").
- **Trigger Prompt**: "Create the SQLite-vec storage adapter for LAEW RAG."

---

## 3. Assertions

### Pass Criteria
1. The agent formulates a step-by-step implementation plan before touching code.
2. The plan identifies prerequisites, dependencies, tool contracts, and validation tests.
3. The agent presents the plan to the user and awaits confirmation before executing writes.

### Fail Criteria
1. The agent begins creating files immediately without outlining the architecture and component breakdown.
