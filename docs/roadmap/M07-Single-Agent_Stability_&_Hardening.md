---
type: roadmap
id: M07
title: Single-Agent Stability & Hardening
status: completed
purpose: Establish a stable, well-tested single-agent runtime as the foundation for multi-agent scaling; add structured logging; implement provider registry/factory; harden CI.
read_when:
  - establishing a stable single-agent baseline
  - preparing for multi-agent scaling
  - understanding the foundation for M10-M11
related:
  - ADR-017
  - ADR-019
  - M08
---

## [2026-09-09] Milestone 7: Single-Agent Stability & Hardening Completed

### Context & Motivation

Before scaling to multi-agent systems (Milestones 10+), LAEW needed a stable, well-tested single-agent runtime. Milestones 5–6 addressed documentation synchronization and audit remediation. This milestone consolidates the remaining hardening work:

- **Structured logging** (ADR-016) — move from `print()` to a proper logging framework with rotating file handler.
- **Provider registry & factory** (ADR-019) — decouple provider construction from CLI code, enabling manifest-driven provider selection.
- **Packaging** — migrate to PEP 621 (`pyproject.toml`), add bandit SAST gate to CI.
- **Documentation** — add `INSTALL.md` with complete installation and usage instructions.
- **Security hardening** — bandit audit, CI SAST gate.

These changes establish the single-agent runtime as a production-ready foundation.

### Key Achievements

- **Structured logging** (`laew/logging_config.py`): Idempotent `configure_logging()` with console `StreamHandler` to stderr and optional `RotatingFileHandler` (1 MiB max size, 3 backups, UTF-8 encoding). The `laew.tools` structured logger is left untouched.

- **Provider registry & factory** (`laew/llm/registry.py`): A type-keyed registry maps manifest `agent.llm.providers[].type` strings to builder callables. Only `ollama` is registered (YAGNI — the registry is the documented seam for future providers). `create_provider(cfg, base_url=None, timeout=None)` resolves config with layer precedence **CLI flag > env var (`LAEW_BASE_URL`, `LAEW_TIMEOUT`) > manifest > provider default**. Unknown types raise `LLMError(code="UNSUPPORTED_PROVIDER")`.

- **OllamaProvider timeout**: Made the hardcoded 120-second timeout configurable via the `timeout` parameter, fixing the E2E timeout issue that surfaced in multi-agent runs with CPU models.

- **Packaging** (`pyproject.toml`): Migrated to PEP 621 metadata, console script `laew = laew.cli:main`, dev extras (`pytest`, `html2text`, `chromadb`, `build`), and `[tool.bandit]` SAST configuration. `setup.py` reduced to a compatibility shim.

- **`laew check` CLI command**: Validates the system manifest, reports schema violations, and exits with a non-zero code on failure.

- **`laew tool` CLI command**: Executes a tool operation with optional logging (`--log` flag writes the invocation to `laew_logs/<timestamp>.json` in the workspace root).

- **`--provider` and `--timeout` CLI flags**: Added to `chat` and `multiagent run` commands for runtime override of manifest configuration.

- **`--manifest` option**: Added to all four CLI subparsers (`check`, `workflow run`, `chat`, `tool`) so the terminal allowlist and other manifest-driven settings are available everywhere.

- **Bandit SAST gate in CI**: Configured in `pyproject.toml` to exclude `tests/` and `docs/`, skip B101 (assert statements used as runtime invariants), and run on HIGH+ severity only. CI runs `bandit -r laew -lll --configfile pyproject.toml` before the build step.

- **`docs/INSTALL.md`**: Complete installation guide for Windows and Unix, covering Python 3.10+ venv setup, pip installation, Ollama setup, and basic usage.

### Decisions & Consequences

- **Provider registry as the documented seam**: Adding a new provider is additive (new `LLMProvider` subclass + one `register()` call). No existing call site needs modification.

- **Config precedence is explicit**: CLI flag > env var > manifest > provider default. This means ops can override a manifest without editing it, but the manifest is still the authoritative source.

- **`setup.py` as a shim**: The old `setup.py` is now a forwarding shim that reads metadata from `pyproject.toml`. This preserves `pip install laew` compatibility while using PEP 621 as the source of truth.

- **Bandit as a CI gate**: SAST is now part of the CI pipeline. Any new HIGH or CRITICAL finding will fail the build. This prevents security regressions from being merged.

### Verification

- Full test suite: **456 collected, 455 passed, 1 skipped** (369 unit tests / 19 suites).
- Bandit: **0 High, 0 Medium** over `laew/`.
- All CLI commands verified functional.
- Packaging verified with `pip install laew` from a clean venv.

### Milestone 7 → Milestone 8 Transition

Milestone 7 establishes the single-agent runtime as production-ready. The next milestone (M08) adds the evaluation harness to enable quantitative quality measurement, which is a prerequisite for workflow automation (M09) and multi-agent scaling (M10+).

---

## See Also

- [M08](M08-Evaluation_Harness.md) — Evaluation harness
- [M10](M10-Multi-Agent_Architecture.md) — Multi-agent architecture
- [M11](M11-Production_Hardening.md) — Production hardening (provider registry, logging, packaging)
- [ADR-019](../decisions/ADR-019-provider-registry-and-factory.md) — Provider registry and factory
- [ADR-016](../decisions/ADR-016-structured-tool-invocation-logging.md) — Structured tool invocation logging
- [Security Review](../security/SECURITY_REVIEW.md) — Bandit audit record
