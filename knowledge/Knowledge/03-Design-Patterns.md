---
title: Design Patterns
tags:
  - design-patterns
  - software-architecture
backlinks:
  - 01-REST-API-Design
  - 001-global-second-brain
---

# Design Patterns

Reusable solutions to recurring software problems. Read [[01-REST-API-Design]]
for an applied example and [[001-global-second-brain]] for how to record the
decisions behind them.

## Common Patterns

- **Repository** — encapsulates data access behind a stable interface, hiding
  whether the data lives in a database, file, or cache.
- **Factory** — centralizes object creation so callers depend on an abstraction
  rather than a concrete class.
- **Strategy** — swaps a piece of behavior at runtime, replacing large conditionals
  with interchangeable algorithms.

## Choosing a Pattern

Do not reach for a pattern to look professional. Add structure only where it
removes duplication or clarifies a boundary. A well-named function is more
valuable than an over-engineered pattern. Prefer the simplest design that
holds as requirements change.
