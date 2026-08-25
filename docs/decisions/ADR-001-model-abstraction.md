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
