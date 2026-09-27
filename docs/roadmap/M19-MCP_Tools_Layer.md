---
type: roadmap
id: M19
title: MCP Tools Layer
status: completed
purpose: Open the tool layer to the Model Context Protocol ecosystem so external MCP servers appear as LAEW tools while enforcing existing security boundaries.
read_when:
  - implementing MCP tool adapter
  - Milestone 19 (MCP Tools Layer)
---

### Milestone 19: MCP Tools Layer
**Goal:** Open the tool layer to the tool ecosystem via the Model Context Protocol.
**Scope:** MCP client adapter so external MCP servers appear as LAEW tools, enforcing existing approval/boundary rules (P8); keep the base `Tool` contract as the adapter interface so no tool behavior is bypassed.
**Dependencies:** Milestone 18 (telemetry covers MCP tool calls).
**Tests:** MCP tool discovery/adapter mapping, boundary enforcement, approval propagation, error mapping.
**Definition of Done:** An external MCP server's tools are usable by agents behind the same security and logging controls as native tools.