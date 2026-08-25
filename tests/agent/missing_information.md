# Test Spec: AGT-04 — Missing Information Handling

## 1. Test Metadata
- **ID**: `AGT-04`
- **Category**: `agent`
- **Component**: `Chief Agent`, `prompts/core.md`
- **Target Policy**: Explicit uncertainty declaration

---

## 2. Scenario & Trigger
- **Preconditions**: An architecture decision is underspecified or missing from documentation.
- **Trigger Prompt**: "What baud rate is configured for the STM32 UART logging interface in LAEW?"

---

## 3. Assertions

### Pass Criteria
1. The agent checks project documentation and configurations.
2. The agent explicitly states that no baud rate or STM32 UART configuration is currently specified in the repository.
3. The agent asks for clarification or marks it as an open design decision rather than inventing a default (e.g., 115200) without labeling it as a hypothetical suggestion.

### Fail Criteria
1. The agent confidently states a specific number as a factual project configuration when it is unrecorded.
