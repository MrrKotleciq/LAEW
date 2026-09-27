---
type: index
title: Roadmap and Milestones
scope: planned work and milestones
read_when:
  - planning new work
  - understanding the project's direction
  - estimating remaining work
---

# Roadmap

This directory contains milestone documents describing planned work for LAEW.

## Milestone Index

| Milestone | Status | Document |
|-----------|--------|----------|
| M01 | ✅ Completed | [M01-Declarative_Foundation.md](M01-Declarative_Foundation.md) |
| M02 | ✅ Completed | [M02-Tool_Runtime_Wrappers_&_Programmatic_Security.md](M02-Tool_Runtime_Wrappers_&_Programmatic_Security.md) |
| M03 | ✅ Completed | [M03-Chief_Agent_Runtime_LLM_Provider_&_Orchestration.md](M03-Chief_Agent_Runtime_LLM_Provider_&_Orchestration.md) |
| M04 | ✅ Completed | [M04-Knowledge_System_&_RAG_Pipeline.md](M04-Knowledge_System_&_RAG_Pipeline.md) |
| M05 | ✅ Completed | [M05-Documentation_Synchronization_&_Integration_Scaffold.md](M05-Documentation_Synchronization_&_Integration_Scaffold.md) |
| M06 | ✅ Completed | [M06-Audit_Remediation_&_Technical_Debt.md](M06-Audit_Remediation_&_Technical_Debt.md) |
| M07 | ✅ Completed | [M07-Single-Agent_Stability_&_Hardening.md](M07-Single-Agent_Stability_&_Hardening.md) |
| M08 | ✅ Completed | [M08-Evaluation_Harness.md](M08-Evaluation_Harness.md) |
| M09 | ✅ Completed | [M09-Automation_&_Workflow_Runtime.md](M09-Automation_&_Workflow_Runtime.md) |
| M10 | ✅ Completed | [M10-Multi-Agent_Architecture.md](M10-Multi-Agent_Architecture.md) |
| M11 | ✅ Completed | [M11-Production_Hardening.md](M11-Production_Hardening.md) |
| M12 | ✅ Completed | [M12-Interactive_Testing_Console.md](M12-Interactive_Testing_Console.md) |
| M13 | ✅ Completed | [M13-Session_Memory_&_Conversation_Persistence.md](M13-Session_Memory_&_Conversation_Persistence.md) |
| M14 | ✅ Completed | [M14-Performance_&_Context-Efficiency_Audit.md](M14-Performance_&_Context-Efficiency_Audit.md) |
| M15 | ✅ Completed | [M15-Multi-Model_Routing_&_Provider_Fallback.md](M15-Multi-Model_Routing_&_Provider_Fallback.md) |
| M16 | ✅ Completed | [M16-Parallel_Multi-Agent_Execution_&_Semantic_Conflict_Detection.md](M16-Parallel_Multi-Agent_Execution_&_Semantic_Conflict_Detection.md) |
| M17 | 🚧 In Progress | [M17-Second_Brain_&_Global_Knowledge_Integration.md](M17-Second_Brain_&_Global_Knowledge_Integration.md) |
| M18 | 🚧 In Progress | [M18-Monitoring_Telemetry_&_Backup.md](M18-Monitoring_Telemetry_&_Backup.md) |
| M19 | 🚧 In Progress | [M19-MCP_Tools_Layer.md](M19-MCP_Tools_Layer.md) |
| M20 | 🚧 In Progress | [M20-Multi-Project_Workspace.md](M20-Multi-Project_Workspace.md) |
| M21 | 🚧 In Progress | [M21-v1.0_Stabilization_&_Release.md](M21-v1.0_Stabilization_&_Release.md) |
| M22 | 📋 Backlog | [BACKLOG.md](BACKLOG.md) |

## Milestone Completion Criteria

Each milestone is considered complete when:

1. **All key achievements** are implemented in the repository.
2. **All associated tests** pass (full test suite green).
3. **Documentation** is updated to reflect the implementation.
4. **The milestone document** is updated with completion details.

## Milestone Status Legend

- ✅ **Completed** — All criteria met; milestone is done.
- 🚧 **In Progress** — Work is ongoing; milestone is not yet complete.
- 📋 **Backlog** — Work is planned but not yet started.

## Milestone Dependencies

Milestones are ordered by dependency:

- M01 → M02 → M03 → M04 → M05 → M06 → M07 → M08 → M09 → M10 → M11 → M12 → M13 → M14 → M15 → M16 → M17 → M18 → M19 → M20 → M21

M05–M07 were reconstructed from git history and project context:
- **M05** (Documentation Synchronization): README, PROJECT_STATUS, ROADMAP updates with validation tests.
- **M06** (Audit Remediation): Medium/Low severity findings from the full technical audit.
- **M07** (Technical Debt Refactoring): Code quality improvements and test suite alignment.

## See Also

- [Architecture](../architecture/README.md)
- [Decisions](../decisions/README.md)
- [Project Status](../PROJECT_STATUS.md)
