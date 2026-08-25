# LAEW Code Review Instructions

## 1. Purpose
Evaluate code modifications, pull requests, and diffs for architectural alignment, correctness, security, performance, and testability.

---

## 2. Review Checklist

1. **Architectural Alignment**:
   - Does the change adhere to LAEW principles (P1–P10) and `manifests/SYSTEM_MANIFEST.yaml`?
   - Does it preserve modularity without introducing tight coupling?
2. **Correctness & Edge Cases**:
   - Does the implementation fully solve the problem without regressions?
   - Are error conditions, timeouts, and boundary cases handled safely?
3. **Security Audit**:
   - Are file paths validated against workspace sandboxes (no path traversal)?
   - Are inputs sanitized and dangerous shell executions blocked?
   - Are secrets, keys, or credentials protected from exposure?
4. **Code Quality & Style**:
   - Is the code idiomatic, self-documenting, and concise?
   - Are existing comments and docstrings preserved or appropriately updated?
5. **Testing & Verification**:
   - Is the change covered by unit tests or repeatable verification procedures?

---

## 3. Required Output Structure
- **Summary of Changes**: High-level description of what the diff accomplishes.
- **Key Strengths**: Well-implemented areas.
- **Findings & Issues**:
  - `[CRITICAL]`: Must-fix bugs, security vulnerabilities, or architectural violations.
  - `[WARNING]`: Suboptimal patterns, missing error handling, or performance concerns.
  - `[SUGGESTION]`: Minor stylistic or readability enhancements.
- **Verification Status**: Confirmed test passes or missing test coverage.
- **Overall Recommendation**: `Approve`, `Request Changes`, or `Discuss`.
