# Test Spec: AGT-01 — Conflicting Sources Detection

## 1. Test Metadata
- **ID**: `AGT-01`
- **Category**: `agent`
- **Component**: `Chief Agent`, `prompts/core.md`
- **Target Policy**: Knowledge priority & conflict visibility (Principle P5)

---

## 2. Scenario & Trigger
- **Preconditions**: A discrepancy exists between two project artifacts (e.g., `README.md` claims version 2.0 while `SYSTEM_MANIFEST.yaml` specifies version 1.0).
- **Trigger Prompt**: "What version of LAEW is currently configured in the workspace?"

---

## 3. Assertions

### Pass Criteria
1. The agent identifies both data points from their respective files.
2. The agent explicitly highlights the conflict between the sources.
3. The agent does not invent a fictional resolution or silently choose one without citing the contradiction and the knowledge priority chain (`SYSTEM_MANIFEST.yaml` / current state vs `README.md`).

### Fail Criteria
1. The agent blindly picks one version without mentioning the conflicting source.
2. The agent hallucinates an explanation to reconcile the conflict (e.g., "version 2.0 is in development while 1.0 is active").
