## [2026-09-15] Milestone 11: Production Hardening Completed

- **Context & Motivation**:
  Prepare LAEW for real-world usage beyond development: pip-installable packaging, documented configuration, app-level logging, and a security gate. The trigger was a real E2E failure — a Qwen3-14B-on-CPU multi-agent run aborted because `OllamaProvider` hardcoded a 120-second timeout and every specialist generation exceeded it. That exposed a configuration-management gap: no timeout knob and no provider-extensibility seam.
- **Key Achievements**:
  - Introduced a provider registry and factory (`laew/llm/registry.py`) dispatching on manifest `agent.llm.providers[].type`; `create_provider()` resolves config with layer precedence **CLI flag > env var (`LAEW_BASE_URL`, `LAEW_TIMEOUT`) > manifest > provider default**; unknown types raise `LLMError(code="UNSUPPORTED_PROVIDER")`. Only `ollama` is registered — the dispatch is the documented seam for future providers (no dead stubs, YAGNI).
  - Made `OllamaProvider` timeout configurable (`timeout: int = 120`), fixing the hardcoded wall that caused CPU-model E2E timeouts.
  - Wired `chat` and `multiagent run` through `create_provider()` and added `--provider` / `--timeout` CLI flags; manifest validation now rejects non-positive `timeout` and empty provider `type`.
  - Migrated to PEP 621 packaging (`pyproject.toml`: metadata, console script `laew = laew.cli:main`, dev extras, `[tool.bandit]`); `setup.py` reduced to a compatibility shim.
  - Added app-level logging (`laew/logging_config.py`): idempotent `configure_logging()` with console StreamHandler (stderr) and optional rotating file handler (1 MiB, 3 backups); the `laew.tools` structured logger is left untouched.
  - Added docs: `docs/INSTALL.md` (Windows/Unix install guide), `docs/security/SECURITY_REVIEW.md` (bandit audit — 0 High/Medium findings), README Installation/Configuration sections.
  - Hardened CI: bandit SAST gate (`bandit -r laew -lll`), sdist+wheel build, fresh-venv wheel-install verification.
  - Verified: full suite **456 collected, 455 passed, 1 skipped** (369 unit tests / 19 suites); bandit reports 0 High/0 Medium over `laew/`.
- **Decisions & Consequences**:
  - Provider selection is registry-based: adding a new provider is additive (new class + registry entry), keeping the system model-agnostic (ADR-001).
  - Configuration precedence is explicit and layer-aware, so ops can override manifests via env vars without code changes.
  - Packaging is authoritative in pyproject.toml; setup.py is a forwarding shim rather than a dual source of truth.