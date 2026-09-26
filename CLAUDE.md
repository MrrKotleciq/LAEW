# CLAUDE.md

## Role

You are an external development agent helping the user build LAEW
(Local AI Engineering Workspace).

You are NOT part of LAEW's runtime architecture.

Do not design LAEW around Claude Code, Claude, Omniroute, or any
specific model/provider unless explicitly decided.

## Project

LAEW is a local-first AI Engineering Workspace for project-aware
AI assistance, persistent engineering knowledge, controlled tools,
RAG, modular model integration, and engineering workflows.

## Source of Truth

Current source code and tests describe implemented behavior.

Accepted ADRs record architectural decisions.

Use documentation according to this hierarchy:

- `docs/README.md` — documentation index
- `docs/LAEW_CONTEXT.md` — project scope and context
- `docs/PROJECT_STATUS.md` — current implementation status
- `docs/architecture/` — architectural intent
- `docs/decisions/` — ADRs
- `docs/roadmap/` — planned work
- `docs/history/` — historical record
- `docs/performance/` — measurements and baselines
- `docs/security/` — security reviews
- `docs/source/` — reference material
- `manifests/SYSTEM_MANIFEST.yaml` — system contract

Do not read all documentation by default.

Start with `docs/README.md` when the relevant document is unknown.
Then identify and read only the documents relevant to the task.

Do not confuse documented plans with implemented functionality.

When architecture, interfaces, security boundaries, or ADR-governed
behavior changes, identify and read the relevant ADR before implementation.

## Development

Prefer:

inspect → plan → implement → test → review diff

- Make the smallest change that solves the task.
- Prefer tests before implementation when practical.
- Do not modify unrelated files.
- Do not weaken tests to make them pass.
- Run relevant tests after changes.
- Verify the final diff.

## Architecture

Preserve modularity and model/provider independence.

Keep persistent knowledge separate from runtime/model state.

Avoid premature abstraction and unnecessary dependencies.

Do not silently replace architectural decisions.

## Documentation

Update documentation when behavior, architecture, or important decisions change.

When adding or changing a document, keep its metadata and index entry accurate.

Prefer updating the smallest relevant document rather than expanding large
catch-all files.

Use history documents for historical records, roadmap documents for plans,
and ADRs for architectural decisions.

## Git

Inspect `git status` before changes and `git status` + `git diff`
after changes.

Never discard user changes or perform destructive Git operations
without explicit approval.

Do not create commits unless explicitly requested.

## Communication

Be concise and technical.

Distinguish facts, inferences, and hypotheses.

Never claim something works without testing it.