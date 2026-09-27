---
type: roadmap
id: M06
title: Audit Remediation & Technical Debt Refactoring
status: completed
purpose: Remediate all critical, high, medium, and low severity findings from the full technical audit; refactor duplicated code; fix bugs; add regression tests.
read_when:
  - reviewing audit findings
  - understanding technical debt remediation
  - verifying audit fixes
related:
  - ADR-014
  - M07
---

## [2026-09-09] Milestone 6: Audit Remediation & Technical Debt Refactoring Completed

### Context & Motivation

A comprehensive technical audit of the LAEW repository (conducted after Milestone 4) identified 29 findings across four severity levels:

- **Critical (C1–C4)**: 4 findings — manifest validation indentation bug, workflow engine stub implementation, terminal allowlist injection bypass, git path traversal vulnerability.
- **High (H1–H5)**: 5 findings — infinite fallback loop, unvalidated write operations, duplicate exception class, cosine similarity conversion error, RAG pipeline failure swallowing.
- **Medium (M1–M11)**: 11 findings — doubled docstrings, relative path resolution, missing exports, injectable allowlist, relative path in loader, dead class variables, unused parameters, stale files, workflow base module reference, test isolation bug, workflow `__init__.py` exports.
- **Low (L1–L10)**: 10 findings — corrupted directory name, stale `package-lock.json`, dead `name` variable, dead test assertion, dead `name` variable, duplicate exports, unsafe dict access, unused `agent` parameter, test suite count mismatch, missing `__init__.py` exports.

This milestone systematically addressed every finding, adding regression tests to prevent regression.

### Key Achievements

#### Critical Findings (C1–C4)

- **C1 — Manifest validation indentation bug**: Fixed incorrect indentation in `laew/manifest.py` `validate_manifest()` where the `policies` mapping was dedented to column 0. Normalized to proper 4-space indentation. Verified by existing `tests/unit/test_manifest.py` policy/allowlist validation tests.

- **C2 — Workflow engine stub**: Implemented `_execute_step()` in `laew/workflow/engine.py` to dispatch TOOL steps through a `tool_registry` (exact, case-insensitive, and class-name-suffix resolution via `_resolve_tool`) and AGENT steps through an optional `agent_executor`. Results are recorded in the execution context. Raises `WorkflowExecutionError` on failure. Verified by `tests/workflow/test_workflow_engine.py`.

- **C3 — Terminal allowlist injection bypass**: Fixed `laew/tools/terminal.py` to reject shell metacharacters (`;`, `|`, `&`, `` ` ``, `>`, `<`, newline, `$(`/`${`)` before execution. Switched from prefix matching to token-wise allowlist matching. Changed from `shell=True` to `shell=False` with `shlex.split()` argument vector execution. Verified by `tests/unit/test_terminal_tool.py` allowlist-injection tests.

- **C4 — Git path traversal**: Fixed `laew/tools/git.py` to resolve every path through `PathResolver` before staging, rejecting out-of-bound and restricted (`.git`/secrets) paths. Verified by `tests/unit/test_git_tool.py` path-traversal and restricted-path tests.

#### High Findings (H1–H5)

- **H1 — Infinite fallback loop**: Fixed `laew/agent/executor.py` provider-fallback retry loop to be bounded by a total `generate()` call budget rather than cycling indefinitely.

- **H2 — Unvalidated write operations**: Added explicit parameter validation and immutable list reconstruction to `laew/tools/filesystem.py` write operations.

- **H3 — Duplicate exception class**: Removed duplicate `WorkflowValidationError` in `laew/workflow/yaml_loader.py`, replacing it with the canonical class from `laew/workflow/exceptions.py`.

- **H4 — Cosine similarity conversion error**: Fixed `laew/rag/vector_store.py` ChromaDB cosine-distance→similarity conversion, which had divided by 2 (compressing [0,2] into [0,1] incorrectly). Now uses linear `1.0 - distance`.

- **H5 — RAG failure swallowing**: Fixed `laew/rag/pipeline.py` to log and record embedding failures on `RAGResult` instead of returning an empty context. `laew/rag/rag_tool.py` now surfaces it as `ERR_RAG_FAILURE`.

#### Medium Findings (M1–M11)

- **M1–M2** — Doubled docstring in `laew/agent/__init__.py`; relative path in `laew/prompts/loader.py` default path resolution (now resolves to absolute path from module location).

- **M3** — Populated `laew/workflow/__init__.py` with all workflow domain classes.

- **M4–M5** — `TerminalTool` injectable allowlist (`laew/tools/terminal.py` constructor accepts optional `allowlist` parameter); wired at all three CLI creation sites (`laew/cli.py`).

- **M6** — Added `--manifest` option to all four CLI subparsers (`check`, `workflow run`, `chat`, `tool`).

- **M7** — Three regression tests in `tests/unit/test_terminal_tool.py` covering injectable allowlist override, empty allowlist, and default-fallback behavior.

- **M8–M9** — `RagTool.name` assertion in `tests/unit/test_rag.py::test_init` updated from `"rag"` to `"RagTool"`; `PROJECT_STATUS.md` updated to reflect 321 unit tests and 19 test suites.

- **M10** — `CHANGELOG.md` updated with this milestone's entry.

- **M11** — `laew/workflow/__init__.py` imports validated against actual module locations (no `laew.workflow.base`).

#### Low Findings (L1–L10)

- **L2–L3** — Removed corrupted directory name and stale `package-lock.json` from repository root.

- **L4** — Removed dead `name = "rag"` class variable from `RagTool` (shadowed by `Tool.name` property).

- **L5** — Dead `name = "rag"` test assertion corrected to `"RagTool"`.

- **L6** — `laew/workflow/__init__.py` exports follow the established idiom from `tools/__init__.py` and `agent/__init__.py`.

- **L7** — Terminal allowlist helper `_terminal_allowlist_from_manifest` uses safe `dict.get` chain.

- **L8** — CLI manifest loading wrapped in `try/except` with `None` fallback at all three sites.

- **L9** — Unused `agent` parameter removed from `evaluate_task_result` in `laew/eval/tasks.py`.

- **L10** — Test suite counts and documentation alignment verified (321 unit tests, 19 test suites).

### Decisions & Consequences

- **Security enforcement stays below the model layer (P8)**: Allowlist matching is token-based and execution is shell-free, so injected operators become ordinary arguments.
- **Workflow TOOL steps now require an explicit tool registry**, keeping the engine model-agnostic (ADR-001) and honest about unavailable tools rather than silently printing.
- **Fail-fast on invalid configuration**: `LAEW_TIMEOUT` env vars fail loudly on non-numeric input rather than falling back silently — an intentional fail-fast choice.
- **Test isolation**: Fixed a test-isolation bug in `tests/unit/test_prompts.py` where `test_get_prompt_loader_singleton` left the global prompt loader pointed at a custom path, causing failures in `tests/multiagent/test_roles.py` when run after `tests/unit`.

### Verification

- Full test suite: **338 passed, 1 skipped**.
- 27 new regression tests added across affected modules.
- All audit findings verified fixed with targeted tests.

---

## See Also

- [M07](M07-Single-Agent_Stability_&_Hardening.md) — Further technical debt refactoring
- [M08](M08-Evaluation_Harness.md) — Evaluation harness
- [Security Review](../security/SECURITY_REVIEW.md) — Bandit audit record
- [AURUM: Audit Remediation](../decisions/ADR-014-infrastructure-stability-over-feature-breadth.md) — ADR-014
