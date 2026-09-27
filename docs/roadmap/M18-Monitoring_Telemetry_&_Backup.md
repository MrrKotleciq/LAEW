---
type: roadmap
id: M18
title: Monitoring, Telemetry & Backup
status: completed
purpose: Surround the system with observability and backup layers: structured run telemetry, health/status summary, crash-safe session and vault backup/restore, and retention policy.
read_when:
  - implementing monitoring or backup
  - Milestone 18 (Monitoring, Telemetry & Backup)
---

### Milestone 18: Monitoring, Telemetry & Backup
**Goal:** Surround the system with the observability and backup layers from the v1.0 architecture.
**Scope:** Structured run telemetry (agent/tool/LLM events) into the existing logging framework; health/status summary (`laew status`); crash-safe session and vault backup/restore paths; retention policy for logs and sessions.
**Dependencies:** Milestones 13 (sessions to back up) and 17 (vault to backup).
**Tests:** Telemetry event integrity, `laew status` accuracy, backup/restore round-trips, retention enforcement.
**Definition of Done:** Every run produces inspectable telemetry; sessions and vault can be backed up and restored; operators can answer "what happened on run X."