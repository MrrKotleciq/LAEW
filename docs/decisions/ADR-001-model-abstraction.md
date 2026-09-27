---
type: adr
id: ADR-001
title: Model Abstraction and Roles
status: Accepted
date: 2026-08-25
purpose: Define LAEW's abstract model roles (primary, embedding, reviewer) so the environment never depends on one specific LLM or provider.
scope: LLM provider integration, model roles, multi-model routing
read_when:
  - designing or modifying LLM provider integration
  - adding a new provider or model role
  - implementing multi-model routing or fallback (Milestone 15)
related:
  - ADR-004
  - ADR-019
---
# ADR-001 — Model Abstraction and Roles

## Status
Accepted

## Context
LAEW is designed as a long-term engineering assistant. Tightly coupling the environment to a specific model provider or model name creates architectural fragility and limits future model upgrades.

## Decision
The system must use abstract model roles (such as primary reasoning, embedding, and review) rather than hardcoding one specific LLM. Models are treated as interchangeable components operating locally or via cloud APIs.

## Consequences
- The workspace remains model-agnostic.
- Local models and cloud models can be swapped without restructuring prompts or tools.
- Multi-model routing is architecturally supported.
