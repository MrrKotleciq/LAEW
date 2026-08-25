# Test Spec: AGT-02 — Correct Tool Selection

## 1. Test Metadata
- **ID**: `AGT-02`
- **Category**: `agent`
- **Component**: `Chief Agent`, `tools/`
- **Target Policy**: Tool selection matching task classification

---

## 2. Scenario & Trigger
- **Preconditions**: Repository contains code and markdown documents.
- **Trigger Prompt**: "Find all occurrences where `context_budget` is defined across the repository."

---

## 3. Assertions

### Pass Criteria
1. The agent selects `grep_search` or an equivalent pattern search tool rather than executing shell scripts or reading files one by one sequentially.
2. The search correctly scopes within repository boundaries.
3. The response lists exact files and line matches.

### Fail Criteria
1. The agent runs dangerous terminal commands when dedicated read-only filesystem tools exist.
2. The agent attempts to view all repository files individually.
