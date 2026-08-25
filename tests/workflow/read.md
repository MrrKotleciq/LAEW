# Test Spec: WF-04 — Minimal Context Reading & Inspection

## 1. Test Metadata
- **ID**: `WF-04`
- **Category**: `workflow`
- **Component**: `Chief Agent`, `tools/filesystem`, `prompts/core.md`
- **Target Policy**: Step 2 (Inspect) & Principle P6 (Context Efficiency)

---

## 2. Scenario & Trigger
- **Preconditions**: User asks a targeted question about a single principle in `docs/architecture/PRINCIPLES.md`.
- **Trigger Prompt**: "What does Principle P8 state in LAEW architecture?"

---

## 3. Assertions

### Pass Criteria
1. The agent inspects `docs/architecture/PRINCIPLES.md` (or reads only the relevant section/file).
2. The agent DOES NOT load unrelated directories, logs, or external web searches.
3. The response cites Principle P8 directly with line/file references (`docs/architecture/PRINCIPLES.md`).

### Fail Criteria
1. The agent triggers broad searches across all documentation files for a known file location.
2. The agent attempts to read the entire workspace into context.
