# Git Workflow

## Commits

Use:

<type>: <description>

Supported types:
feat, fix, refactor, docs, test, chore, perf, ci

Keep commits focused and describe the actual change.

## Before Commit

- Review the complete diff.
- Run relevant tests/checks.
- Remove temporary debugging changes.
- Do not commit secrets or local-only configuration.

## Pull Requests

When creating a PR:

- Review all relevant commits, not only the latest commit.
- Compare the full branch diff with the target branch.
- Include a concise change summary.
- Include a test/verification summary.