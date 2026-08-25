# LAEW Architecture Workflow Instructions

## 1. Purpose
Analyze system architecture, evaluate proposed structural modifications, maintain modularity, and update Architecture Decision Records (ADRs).

---

## 2. Procedure
1. **Inspect Existing Architecture**: Review `docs/architecture/` and `docs/decisions/ARCHITECTURE_DECISIONS.md`.
2. **Inspect Current Repository State**: Check actual implementation in the repository to ground analysis in reality.
3. **Analyze Proposed Change**: Clearly define the change, its motivations, and its scope.
4. **Identify Alternatives & Trade-offs**: Compare at least two viable approaches, evaluating complexity, performance, and maintainability.
5. **Verify Compatibility & Principles**: Check alignment with core principles (P1–P10, model-agnosticism, security below model layer).
6. **ADR Determination**: Determine if an existing ADR must be updated or a new ADR created.

---

## 3. Required Output Structure
Always structure architectural evaluations using:
- **Current Architecture**: Summary of existing design.
- **Proposed Change**: Exact nature of the modification.
- **Motivation**: Why the change is proposed.
- **Alternatives Considered**: Viable alternative designs.
- **Trade-offs & Risks**: Downsides, operational complexity, breaking changes.
- **Recommendation**: Concrete, justified architectural path.
- **Required Documentation Changes**: List of ADRs or documentation files requiring updates.
