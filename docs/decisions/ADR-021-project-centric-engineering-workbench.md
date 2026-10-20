---
type: adr
id: ADR-021
title: Project-Centric Engineering Workbench
name: Project-Centric Engineering Workbench
description: Defines LAEW as a project-focused engineering workbench rather than a generic chat product.
tags: [ui, ux, workspace]
status: Accepted
date: 2026-10-20
purpose: Establish the information architecture and presentation principles for the local web app.
scope: product direction, workspace layout, technical state presentation
related: [ADR-006, ADR-009, ADR-017, ADR-020]
---
# ADR-021 — Project-Centric Engineering Workbench

## Status
Accepted

## Decision
LAEW presents a desktop-first project workbench: shared runtime bar, workspace navigation, a central Chief Agent conversation, and a collapsible context/run/sources panel. Technical detail is compact by default and expandable when it is real. Empty or unavailable states are explicit; the UI never represents candidate context or fabricated progress as model input or execution.

## Rationale and trade-offs
Engineering work needs project state and controlled operations beside conversation, not a generic chatbot with settings. This increases layout and responsive-design complexity, but keeps the operational model legible. Detailed component behavior is maintained in the [UI architecture](../architecture/UI_ARCHITECTURE.md), rather than overloading this decision record.
