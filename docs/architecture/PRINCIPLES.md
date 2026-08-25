# LAEW — Architecture Principles

## P1 — Model is replaceable

LAEW must not depend on one specific LLM.

## P2 — Knowledge remains outside the model

Persistent knowledge belongs to repositories, documentation,
memory systems and knowledge bases.

## P3 — Current state beats assumptions

When answering about implementation, inspect the repository.

## P4 — Source awareness

Separate facts, inferences and hypotheses.

## P5 — Conflict visibility

Conflicting sources must be reported rather than silently
resolved by guessing.

## P6 — Context efficiency

Use the smallest useful context.

## P7 — User control

The user remains in control of modifications and execution.

## P8 — Security below the model

Security restrictions must not depend solely on model behavior.

## P9 — Modular architecture

Components should be independently replaceable and testable.

## P10 — Scale by composition

Add components rather than creating one giant component.
