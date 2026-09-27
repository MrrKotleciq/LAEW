---
type: roadmap
id: M09
title: Automation & Workflow Runtime
status: completed
purpose: Execute multi-step engineering workflows with human oversight, approval gates, compensating rollback, and manual/disabled fallback modes (ADR-015).
read_when:
  - implementing workflow automation
  - Milestone 9 (Automation & Workflow Runtime)
---

## [2026-09-09] Milestone 9: Automation & Workflow Runtime Completed

- **Context & Motivation**:
  Execute multi-step engineering workflows with human oversight, per ADR-015 (automation with manual and disabled fallback modes), building on the robust single-agent runtime (ADR-017).
- **Key Achievements**:
  - Implemented workflow runtime (`laew/workflow/`) with workflow definitions and step types (`definition.py`), execution engine (`engine.py`), approval gates (`approval.py`), compensating rollback actions (`rollback.py`), error types (`exceptions.py`), and YAML workflow loading (`yaml_loader.py`).
  - Added CLI entry point `laew workflow run` for executing YAML-defined workflows.
  - Added workflow test suite (`tests/workflow/test_workflow_engine.py`) and YAML workflow fixtures covering simple, approval-gated, agent, and rollback workflows.
- **Decisions & Consequences**:
  - Simple sequential script selected as the workflow engine design for Milestone 9; DAG/state-machine orchestration deferred to future milestones.
  - Human-in-the-loop approval gates and compensating rollback enable manual fallback modes per ADR-015.