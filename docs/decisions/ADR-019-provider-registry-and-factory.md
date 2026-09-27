---
type: adr
id: ADR-019
title: Provider Registry and Factory
status: Accepted
date: 2026-09-15
purpose: Dispatch model roles across providers through a registry and factory with an ordered fallback chain, keeping provider selection manifest-driven.
scope: provider registry, role-based routing, fallback
read_when:
  - adding or changing a model provider
  - Milestone 15 (Multi-Model Routing & Provider Fallback)
  - resolving a model role to a provider
related:
  - ADR-001
  - ADR-015
  - ADR-016
---
# ADR-019 — Provider Registry and Factory

## Status
Accepted

## Context
Milestone 11 (Production Hardening) needed provider configuration to be resolvable and overridable. An E2E multi-agent run against a Qwen3-14B-on-CPU model aborted because `OllamaProvider` hardcoded a 120-second timeout and every specialist generation exceeded it — a configuration-management gap with no timeout knob and no provider-extensibility seam.

Before this decision, `laew/cli.py` constructed `OllamaProvider(base_url=...)` directly in both `cmd_chat` and `cmd_multiagent_run`. Adding a second provider (OpenAI, Anthropic) would have meant editing both call sites with branching on a provider type string — duplicated selection logic, no layer-aware config precedence.

Two design options were considered:
- **Direct factory function** — a single `build_provider()` dispatching on `cfg["type"]`. Simple, but no seam for tests or callers to swap provider sets.
- **Type-keyed registry + factory** — a `ProviderRegistry` mapping manifest provider `type` strings to builder callables, plus a `create_provider()` convenience entry point. Tests and callers can inject their own registry; new providers are additive.

## Decision
Adopt a type-keyed provider registry (`laew/llm/registry.py`) as the provider-selection mechanism:

1. **Registry keyed by manifest `agent.llm.providers[].type`**: a builder (callable) is registered per provider type. Only `"ollama"` is registered today (YAGNI); the registry is the documented seam for future providers — adding one is a new `LLMProvider` subclass plus one `register()` call.
2. **Single factory entry point**: `create_provider(cfg, *, base_url=None, timeout=None)` is used by both `cmd_chat` and `cmd_multiagent_run`, so provider selection lives in one place shared across CLI and multi-agent code.
3. **Layer-aware config precedence**, resolved inside the registry before reaching the builder, with the explicit ordering **CLI argument > environment variable (`LAEW_BASE_URL`, `LAEW_TIMEOUT`) > manifest field (`host`/`port`, `timeout`) > provider default**, so an ops override never requires code or manifest edits.
4. **Typed errors for unknown types**: an unknown or missing `type` raises `LLMError(code="UNSUPPORTED_PROVIDER")` listing the supported types, rather than a bare lookup failure.
5. **Injectable registry**: tests and advanced callers may supply their own `ProviderRegistry`, keeping dispatch deterministic and decoupled from the module-level default.

## Consequences
### Positive
- Provider selection is centralized and shared by every caller, keeping the system model-agnostic (ADR-001).
- Config is configurable at any layer — the 120-second timeout that broke CPU-model E2E runs is now a manifest field, an env var, or a CLI flag.
- Adding future providers is additive (class + registry entry) with no changes to existing call sites.
- CLI, multi-agent, and tests all exercise the same selection path, so precedence behavior is verified once.
- Bandit reports no injection concerns: dispatch is type-checked against a fixed registry.

### Negative
- There is now an indirection layer — a caller must go through the registry rather than constructing a provider directly.
- Env-var values (`LAEW_TIMEOUT`) are coerced with `int()` and fail loudly on non-numeric input rather than falling back silently — an intentional fail-fast choice, but operators must provide valid values.
- Only Ollama is registered; end users cannot yet select a non-Ollama provider (deliberate, YAGNI — the seam is ready).