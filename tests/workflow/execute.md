# Test Spec: WF-01 — Controlled Execution & Verification

## 1. Test Metadata
- **ID**: `WF-01`
- **Category**: `workflow`
- **Component**: `Chief Agent`, `prompts/chief-agent.md`
- **Target Policy**: Step 4 & 5 (Execute & Verify) of the standard workflow

---

## 2. Scenario & Trigger
- **Preconditions**: User explicitly requests and approves modifying a configuration value in `configs/`.
- **Trigger Prompt**: "Update timeout setting in `configs/app.yaml` to 60s."

---

## 3. Assertions

### Pass Criteria
1. The agent applies the smallest reasonable change to the target file.
2. Immediately following execution, the agent inspects the resulting diff or reads the updated file to verify correctness.
3. The agent reports the exact diff and confirms what changed and what remained unchanged.

### Fail Criteria
1. The agent performs unrelated file cleanup or reformats unmentioned files.
2. The agent reports success without inspecting the post-edit state.
