---
name: Security Review — Milestone 11 (Production Hardening)
description: bandit SAST plus manual review of the M11 production-hardening changes; no HIGH or CRITICAL findings.
type: report
scope: LAEW package security audit (bandit + manual)
status: implemented
tags:
  - security
  - m11
  - bandit
---

# Security Review — Milestone 11 (Production Hardening)

**Date:** 2026-09-15
**Reviewer:** LAEW development agent (automated audit)
**Scope:** Full `laew/` package source
**Tool:** bandit (static analysis) + manual review

---

## Summary

Milestone 11 introduces configuration management, a provider registry, packaging, and logging to LAEW. This review verifies that none of these changes introduce new security risks, and that the automated SAST gate is in place to prevent regressions.

## Findings

| ID | Severity | File | Description | Resolution |
|----|----------|------|-------------|------------|
| B101 | LOW | `laew/llm/ollama.py` | Assert statements used as runtime invariants | Intentional — skipped in bandit config |
| None | — | `laew/logging_config.py` | No `pickle`/`eval` usage; file handler uses stdlib `RotatingFileHandler` with explicit encoding | No action needed |
| None | — | `laew/llm/registry.py` | Provider registry dispatches on type string; unknown type raises typed error (no injection vector) | No action needed |
| None | — | `laew/cli.py` | No new subprocess or shell calls; CLI flags are parsed by argparse (safe) | No action needed |
| None | — | `pyproject.toml` | No hard-coded secrets or credentials; dependencies are pinned to minimum versions | No action needed |

## Bandit Configuration

Configured in `pyproject.toml`:

- **Excluded directories:** `tests/`, `docs/`
- **Skipped checks:** B101 (assert statements used deliberately as runtime invariants)
- **CI gate:** `bandit -r laew -lll --configfile pyproject.toml` (HIGH+ severity only)

## CI Integration

The bandit SAST scan is now part of the CI pipeline (`.github/workflows/ci.yml`), running after tests and before the build step. Any HIGH or CRITICAL finding will fail the build.

## Recommendations

1. Run `bandit -r laew` locally before each commit.
2. When adding new providers, review for SSRF or credential-handling risks.
3. The `LAEW_BASE_URL` environment variable accepts arbitrary URLs — no SSRF risk in current usage (requests to user-configured local endpoints), but document this for operators.

## Milestone 11 Changes

- **Provider registry** (`laew/llm/registry.py`): no new security concerns; dispatch is type-checked.
- **Logging** (`laew/logging_config.py`): stdlib-only; `RotatingFileHandler` with explicit encoding; no user-controlled log paths without validation.
- **Packaging** (`pyproject.toml`): PEP 621 metadata; no post-install scripts; entry point is `laew.cli:main`.
- **CLI** (`laew/cli.py`): new `--provider` and `--timeout` flags handled by argparse; no injection vectors.

## Conclusion

No HIGH or CRITICAL security issues found. The automated SAST gate is in place and the security posture is consistent with Milestone 11 scope.
# Workbench permission boundary

The Workbench applies deterministic permission classification before tool
invocation. Project file writes are scoped by the existing path resolver;
ordinary writes may run in Auto mode, while deletion and security-sensitive
files require approval. Restricted blocks writes, Manual asks for approval,
and an approval request is tied to its pending invocation and browser session.
Session grants apply only to the same operation, resolved path, and overwrite
mode, and are discarded with the project runtime. The terminal is limited to
narrowly recognized inspection commands in Workbench. It is not an OS sandbox.

The console tool command and Chief Agent use the same broker with a terminal
prompt; non-interactive approval is denied. Console workflow execution retains
its own conservative tool gates and does not yet use this approval flow.
Approval and cancellation behavior in a
real browser, OS-level path races, and broad command support need further
verification. Operators must not assume that model text proves an action ran.

## Permission validation backlog

Exercise Auto, Manual, and Restricted in a real browser, including allow once,
allow for session, deny, cancellation, session boundaries, and timeout. Check
the approved terminal diagnostic and denial paths separately. M17's successful
read-only RAG invocation in Auto mode does not establish those behaviors; this
broader acceptance work belongs to the Workbench permission boundary.
