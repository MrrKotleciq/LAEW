# LAEW Debugging & Root Cause Analysis Instructions

## 1. Purpose
Systematically investigate, diagnose, and resolve defects in code, infrastructure, and tool integrations using evidence-based debugging.

---

## 2. Debugging Procedure
1. **Define Symptom & Failure Mode**: Document exact error messages, exit codes, and unexpected behaviors.
2. **Reproduce & Isolate**: Establish the minimal reproducible scenario.
3. **Formulate Hypotheses**: Generate plausible explanations for the failure based on code inspection and logs.
4. **Test Hypotheses (Non-Destructive)**: Use read-only tools and minimal logging to validate or falsify each hypothesis.
5. **Identify Root Cause**: Pinpoint the underlying defect rather than patching symptoms.
6. **Formulate Minimal Fix**: Develop the smallest reasonable patch to resolve the root cause.
7. **Verify & Test Regressions**: Confirm the fix resolves the failure without introducing side effects.

---

## 3. Required Output Structure
- **Symptom Description**: Exact error or failure observed.
- **Root Cause Analysis**: Sourced explanation of why the defect occurred.
- **Hypotheses Tested**: What was investigated and eliminated.
- **Proposed Fix**: Description of the minimal necessary code change.
- **Diff / Patch**: Exact lines modified or added.
- **Verification Method**: How the resolution was validated.
