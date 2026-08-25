# Test Spec: AGT-05 — Unnecessary Tool Use Avoidance

## 1. Test Metadata
- **ID**: `AGT-05`
- **Category**: `agent`
- **Component**: `Chief Agent`, `tools/`
- **Target Policy**: Minimal tool invocation & context conservation (Principle P6)

---

## 2. Scenario & Trigger
- **Preconditions**: Conversation history already contains the relevant information (e.g., `README.md` was read in the previous step).
- **Trigger Prompt**: "Based on the README you just read, what is the third goal of LAEW?"

---

## 3. Assertions

### Pass Criteria
1. The agent answers directly using the existing in-context message history.
2. The agent DOES NOT execute redundant `view_file` or `run_command` tool calls to re-read the identical file.

### Fail Criteria
1. The agent repeatedly executes tool calls for data already loaded in the immediate conversation turn.
