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
RAG, modular model integration and engineering workflows.

## Source of Truth

Before significant changes, consult:

- `docs/LAEW_CONTEXT.md` — project context
- `docs/PROJECT_STATUS.md` — current state
- `docs/architecture/` — architectural intent
- `docs/decisions/` — architectural decisions
- `manifests/SYSTEM_MANIFEST.yaml` — system contract

Then inspect relevant code and tests.

Do not confuse documented plans with implemented functionality.

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

When behaviour, architecture or important decisions change,
update the relevant documentation and project status.

## Git

Inspect `git status` before changes and `git status` + `git diff`
after changes.

Never discard user changes or perform destructive Git operations
without explicit approval.

Do not create commits unless explicitly requested.

## Communication

Be concise and technical.
Distinguish facts, inferences and hypotheses.
Never claim something works without testing it.