# Test Spec: RAG-03 — Repository State vs RAG Knowledge Priority

## 1. Test Metadata
- **ID**: `RAG-03`
- **Category**: `rag`
- **Component**: `Chief Agent`, `prompts/core.md`, `prompts/rag.md`
- **Target Policy**: Knowledge hierarchy priority enforcement (Principle P5)

---

## 2. Scenario & Trigger
- **Preconditions**: A retrieved RAG document from a legacy note states that `models.roles.primary.context_budget.total` is `32000`, while the inspected `manifests/SYSTEM_MANIFEST.yaml` explicitly sets it to `18000`.
- **Trigger Prompt**: "What is the total context budget for the primary model?"

---

## 3. Assertions

### Pass Criteria
1. The agent prioritizes the current ground truth repository file (`SYSTEM_MANIFEST.yaml`).
2. The agent outputs `18000` as the authoritative current value.
3. The agent notes the discrepancy in the older RAG document rather than assuming the RAG note overrides the repository.

### Fail Criteria
1. The agent overrides active repository configuration with outdated RAG knowledge.
2. The agent fails to mention the conflicting data when both are retrieved.
