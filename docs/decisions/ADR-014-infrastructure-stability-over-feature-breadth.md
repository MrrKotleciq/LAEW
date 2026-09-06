# ADR-014 — Infrastructure Stability Over Feature Breadth

## Status
Accepted

## Context
A system with many features but unreliable infrastructure is less valuable than a system with fewer features but dependable tool calling, stable model interaction, and trustworthy retrieval. Adding features to an unstable foundation compounds technical debt and erodes user trust.

## Decision
Prioritize infrastructure stability over feature expansion. The investment sequence is:

1. Stability (model backend, session handling, core tool execution)
2. Tool calling reliability and correctness
3. Accurate current project state retrieval
4. RAG quality and relevance
5. Second Brain knowledge integration
6. Automation pipelines
7. Evaluation and testing
8. Performance optimization
9. Multi-model routing
10. Multi-agent orchestration

Features at any level are not added until the preceding levels are stable and verified.

## Consequences
### Positive
- Core functionality remains dependable as the system grows.
- Debugging and optimization are performed on a known-stable baseline.
- User trust is built through consistent reliability.

### Negative
- Feature development is gated by infrastructure maturity.
- May delay introduction of advanced capabilities (multi-agent, multi-model) until foundational layers are production-ready.
