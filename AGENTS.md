# LAEW repository instructions

## Offline tests

Use the repository virtual environment. On Windows, run the full Python suite
with `.venv/Scripts/python.exe scripts/run_isolated.py pytest-offline`. Run the
JavaScript unit suite with `node --test tests/ui/*.test.js`.

The full Python suite needs TCP loopback access for its disposable HTTP
servers. If the runner's loopback check fails, rerun the same command with
the sandbox permission needed for local sockets. Keep the isolated runner
and the offline test selection. For focused runs, use the runner's `pytest`
subcommand with the target paths.

## LAEW Operator CLI

Use the operator CLI for repeatable diagnostics and verified backup inspection.
Run `.venv/Scripts/python.exe -m laew.cli` on Windows or
`.venv/bin/python -m laew.cli` on Debian. Start from the trusted installation.
The standard manifest is `manifests/SYSTEM_MANIFEST.yaml`. Supply the absolute
manifest or profile path when running from a different directory. Discover
available commands with `--help` and add `--json` for automation.

| Read-only command | Use |
|---|---|
| `status --json` | Check readiness, dependency configuration, telemetry and disk state. Add `--profile PROFILE` for cached backup freshness. |
| `telemetry show RUN_ID --json` | Inspect one recorded run by its UUID. Check terminal outcome, attempts, tool decisions and usage availability. Enabled traces require a verified protected installation. |
| `backup plan --profile PROFILE --json` | Inspect the canonical source roster and exclusions. |
| `backup list --profile PROFILE --json` | Check the latest cached verified receipt and its timestamp. |
| `backup verify --profile PROFILE --id ID --json` | Recheck the ZIP, manifest, receipt and member hashes. |
| `restore --profile PROFILE --id ID --verify-only --json` | Check eligibility for isolated recovery without publishing a target. |
| `retention plan --json` | Review aged telemetry. Use `--scope sessions --profile PROFILE --backup-id ID` to review archived conversations. |
| `backup prune --profile PROFILE --pin ID --json` | Review rotation while preserving the last-known-good receipt. |

JSON includes `schema_version`, `command` and `error_code`. Lookup and backup
commands report `state`. Status reports `overall` and per-component `checks`.
Exit `0` means successful inspection, `1` means unavailable or invalid state,
and `2` means invalid arguments. For `status`, `0` means required checks passed,
`1` means degraded or required unknown, and `2` means invalid configuration or
an unavailable required dependency. Default status uses no network. `--probe`
explicitly enables bounded loopback metadata checks. RAG marker age is reported
when available. The `--rag-max-age-seconds N` threshold is opt-in.
Record disabled, unknown and corrupt states explicitly.
For a failed run, use the UUID from the protected launcher's `telemetry_run`
diagnostic and correlate its terminal outcome with `status --json`.
Use the operator lookup instead of copying logs, payloads, session contents or
filesystem paths into a report. A cached receipt is only a freshness indicator.

`backup create` and `restore --target` require `--apply`. Before running them
against real state, obtain explicit authorization for the source, destination,
writer boundary and operation. Creation requires an unexpired writer
acknowledgement. Restore requires a private fresh or empty isolated target.
`retention apply` and `backup prune --apply` require explicit authorization and
the unchanged JSON plan via `--plan ABSOLUTE_PATH`. Telemetry emergency recovery
requires separate approval and the same `--emergency-free-slots N` on both calls.
Session deletion also requires `--acknowledgement ABSOLUTE_PATH` with fresh
writer-quiescence evidence bound to the plan's `review_sha256`.
Keep application sessions, SQLite, vault, telemetry and backup roots under their
owning tools. Do not edit, clean, overwrite, migrate or expose them directly.
An unavailable command or dependency is an operational observation. Inspect
`--help`, record the reason and use the approved read-only fallback. Follow the
[backup and recovery runbook](docs/M18_BACKUP_RECOVERY.md) for full procedures,
Windows path/ACL details and isolated recovery evidence.
