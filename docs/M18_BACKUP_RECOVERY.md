# LAEW backup and recovery

The M18 backup profile describes one authoritative host. The current deployment has Windows Workbench, local sessions and SQLite, a separate Knowledge vault, and a local Chroma volume in Docker. Chroma and freshness markers are derived state. The archive contains the approved canonical sources from which the indexes can be rebuilt. The phase register records the evidence for each supported operation. [M18 execution and verification register](reports/M18_IMPLEMENTATION_READINESS_AND_PLAN_20261118.md)

## Inspect and verify

From the trusted installation, use the repository environment for inspection. Supply the absolute path to the operator-owned JSON profile. On Debian use `.venv/bin/python` in place of `.venv/Scripts/python.exe`.

```powershell
.venv/Scripts/python.exe -m laew.cli backup --help
.venv/Scripts/python.exe -m laew.cli backup plan --profile <ABSOLUTE_PROFILE> --json
.venv/Scripts/python.exe -m laew.cli backup list --profile <ABSOLUTE_PROFILE> --json
.venv/Scripts/python.exe -m laew.cli backup verify --profile <ABSOLUTE_PROFILE> --id <BACKUP_UUID> --json
```

`plan` resolves the sources and exclusions without opening session payloads or creating stores. `list` reports cached receipts. `verify` independently checks the receipt, archive, manifest and member hashes. Both receipt commands can operate when the original sources are missing. Exit `0` means success, `1` means the state or data is unavailable or invalid, and `2` means the command arguments are invalid. JSON responses contain `schema_version`, `command`, `state`, `error_code` and `data`.

### Profile inputs

The backup profile is an operator-owned JSON object with `schema_version: 1`,
stable `profile_id` and `host_id`, absolute `manifest_path`, `launch_cwd`,
`workspace_root`, `vault`, `destination` and `fence` paths, and `config_files`
mapping approved aliases to absolute paths. Set `memory_enabled` and
`knowledge_enabled` to match the source launchers. Supply absolute
`memory_storage` and `knowledge_storage` for launcher overrides, or `null` when
those launchers use their defaults. Include the exact vault spelling. Use
`installation.lock` for the preprovisioned fence and put operator media outside
the workspace aliases and runtime source trees. Check `backup plan --json`
before accepting the profile and its source inventory.

### Protected telemetry profile

Retained telemetry is opt-in for a separate installation and service identity.
The authorized operator sets `LAEW_PROTECTED_PROFILE` to its private absolute
JSON profile path. Version 1 has `legacy_installation`, `manifest`,
`telemetry_root`, `backup_roots`, `projects`, and `executables` in addition to
`schema_version`. Use an absolute path for every root and executable. The legacy
installation must have a different owner. Place the manifest inside the
protected installation and set `telemetry.enabled: true` and `telemetry.root` to
the same private root as the profile. Each project maps `root`, `scratch` and an
`appcontainer` label on Windows. On Debian use `null` for `appcontainer` and
provide the profile's separate `readonly_roots` allowlist for trusted
dependencies. Approve and verify the operating system boundary before enabling
retained traces. The implementation refuses unsupported AppContainer or
Landlock configurations. Keep retained traces and backup media outside
project aliases and protect them with the installation owner's ACLs.

For diagnosis, take the UUID from the protected launcher's `telemetry_run`
diagnostic. Call `laew telemetry show <RUN_UUID> --json`, then
`laew status --manifest <ABSOLUTE_MANIFEST> --json`. Look at the terminal outcome,
provider attempts and tool decisions first. For unavailable dependencies, an
operator can request `status --probe` to check supported loopback metadata.
Keep project data and diagnostic output on the protected installation.

## Capture under an approved maintenance window

1. Obtain approval for the production scope, destination and downtime. Confirm the profile, available capacity, media ownership and access rights, launch directories, environment overrides and writer roster. Keep the destination and installation fence outside all project and knowledge roots. Keep archives on private media and use the deployment's approved encryption and transfer procedures.
2. Enroll cooperating launcher processes with `LAEW_INSTALLATION_FENCE` pointing to the same preprovisioned absolute `installation.lock` path. Drain and stop the Workbench, CLI/console, maintenance and other local writers. Confirm process exit and inhibit automatic restart. Confirm that Obsidian, editors and external sync are stopped for the cut. Include legacy and other uncooperative processes in the operator's acknowledgment.
3. Prepare the versioned acknowledgment in a private operator-owned directory. It records `schema_version`, `profile_id`, `host_id`, `backup_id`, `cut_id`, `roster`, `stopped`, `inventory_complete`, `restart_inhibited` and `valid_until`. The last field is an explicit UTC deadline with `+00:00`. `roster` and `stopped` must contain the same complete set of approved writer labels. Association by profile, host, cut and generation prevents reuse for a different generation. Keep the external writer barrier in place until capture and receipt publication finish.
4. Apply only once both approvals and quiescence are recorded. Independently verify the returned backup UUID before treating it as the new known-good generation.

```powershell
.venv/Scripts/python.exe -m laew.cli backup create --profile <ABSOLUTE_PROFILE> --acknowledgement <ABSOLUTE_ACK> --apply --json
```

The capture refuses an unconfirmed or expired acknowledgment and an active cooperating writer. SQLite databases are backed up through SQLite's backup interface, including committed WAL state. The manifest preserves file digests, logical names, directory layout and the approved configuration evidence. An archive without a published receipt is incomplete. Keep the previous verified generation so it remains available after a failed capture. Operator-approved cleanup of orphan staging is a separate maintenance action.

## Validate isolated recovery

Choose a committed receipt and independently verify the archive. Isolated recovery requires an operator-owned target separate from active stores, the archive destination, all project aliases and the source installation. Prevent application workers, provider calls, editor sync and derived indexes from starting during verification.

```powershell
.venv/Scripts/python.exe -m laew.cli restore --profile <ABSOLUTE_PROFILE> --id <BACKUP_UUID> --verify-only --json
.venv/Scripts/python.exe -m laew.cli restore --profile <ABSOLUTE_PROFILE> --id <BACKUP_UUID> --target <ABSOLUTE_EMPTY_TARGET> --apply --json
```

`--verify-only` opens no target. A target can be new or positively verified empty under a preprovisioned private operator directory. Restore writes into private staging, verifies extracted content and writes `restore.receipt.json` before publishing the target. A completed target cannot be overwritten. For an archive with project-scoped records, add `--project-root <ABSOLUTE_EQUIVALENT_ROOT>` separately for each independently recovered project. An archive from an earlier fixture format without capture topology is eligible for verification only.

Use the archive's logical roots to map named sessions, conversations, vault, private configuration and enabled databases as one generation. When the capture used one physical session directory, preserve that relationship. Verify supported session formats, SQLite integrity, pending jobs, outbox entries and curation state before activation. A staged verification must keep recorded lease and publication state intact. Exercise interrupted-session recovery in a disposable runtime copy and confirm that it resumes without replaying historical tool or provider effects.

Read the `recovery_validation` fields in the response or durable isolated
receipt. `activation_blocked: true` means a pending or running job has a missing
conversation. Keep workers stopped and reconcile the missing source under an
approved procedure. `missing_historical_references` counts references handled
as historical evidence. `memory_namespace: unknown` requires independent
verification of the original override and collection before activation.

Project-scoped records depend on the canonical absolute project path. Preserve the project identities in an isolated path-equivalent environment. Refuse unknown project references or an unverified path change. The project repositories and their worktrees have an independently managed backup. Preserve the exact vault spelling used by each launcher. Windows commonly treats `Knowledge` and `KNOWLEDGE` as the same name, while Debian can distinguish them.

Use the recorded manifest and installed Python package digests to select the compatible runtime. Re-provision provider credentials from their original approved stores. Use the existing model and embedding identities. Start derived recovery from an empty private index endpoint or namespace and rebuild from approved isolated sources. Verify scope, attribution and memory outbox completion before approving production exposure. Real embedding generation has its own authorization and capacity check.

## Production cutover and rollback journal

Activation requires explicit approval and a complete representative drill. Keep the current roots and settings available as the last known-good environment until verification and owner sign-off. Keep the journal on private operator media with the source receipt and restoration evidence.

1. Record the change ID, approvals, target manifest and installed-code digests, backup and restore receipt identifiers, host and profile, and the planned mappings for every authoritative root. Record the old and new root aliases as a consistent set.
2. Record writer drain, restart inhibition, active fence and the last known-good generation. Verify the isolated generation with workers and external sync disabled. Record compatibility, data and derived-index drill results separately.
3. Apply the approved root/configuration switch as one cut. Record each completed switch and the active generation before starting any writer. Verify local sessions, curation state and dependency probes before permitting external sync or model work.
4. If a gate fails, stop writers and record the failure phase. Re-select the recorded complete old generation, verify its mappings and dependency status, and record the rollback before restarting it. Keep the failed generation isolated for diagnosis.

Fixture targets are a 24-hour recovery point and two-hour canonical recovery time. Representative production data size, writer drain, real embeddings and index reconstruction determine the deployed objectives. Schedule installation, archive rotation, session deletion and production activation each require separate authorization.

## Review retention and rotation

Save the successful `--json` response in a private, operator-owned review file as UTF-8. Keep the file outside the stores it describes. Inspect its `data` and obtain explicit authorization before passing its absolute path to `--plan` with `--apply`. Run the same profile, scope and policy options at apply time. A stale plan requires a new review. If an I/O failure interrupts an apply, inspect the current state and produce a fresh plan before retrying.

```powershell
laew retention plan --json
laew retention apply --plan <ABSOLUTE_REVIEW> --apply --json
laew retention plan --scope sessions --profile <ABSOLUTE_PROFILE> --backup-id <BACKUP_UUID> --json
laew retention apply --scope sessions --profile <ABSOLUTE_PROFILE> --backup-id <BACKUP_UUID> --plan <ABSOLUTE_REVIEW> --acknowledgement <ABSOLUTE_ACK> --apply --json
laew backup prune --profile <ABSOLUTE_PROFILE> --pin <LAST_KNOWN_GOOD_UUID> --json
laew backup prune --profile <ABSOLUTE_PROFILE> --pin <LAST_KNOWN_GOOD_UUID> --plan <ABSOLUTE_REVIEW> --apply --json
```

Telemetry keeps a 30-day window with 256 KiB per run and 256 MiB per protected installation. At capacity the sink stops admitting traces while application work can continue. With separate approval, add `--emergency-free-slots N` to both telemetry commands to recover up to the requested admission headroom. The mode evaluates ordinary age eligibility first and selects the oldest additional verified terminal traces as needed. Active and unverified data stay protected. An insufficient plan is blocked. Operator-owned legacy `--log` exports remain under their existing private handling policy.

Only an explicitly marked archived conversation can qualify. The private operator-owned `session-archive-marks.json` sidecar in the backup destination contains `schema_version: 1`, the matching `profile_id` and `host_id`, a UUID `revision`, and a `marks` array. Each mark has the logical `member`, its `sha256` digest, UTC `archived_at`, and boolean `pinned` and `inactive` fields. Supply marks only after confirming the archive and the operator decision, and advance the revision when updating the ledger. Removal requires 90 days since archiving, the exact current digest in the verified backup, and checks for active state, references, pending work and pins. The legacy named-session format stays protected.

Before session apply, drain and inhibit the restart of every session, memory and curation writer, including older launchers. Create a fresh acknowledgment with the same fields as backup capture, a new `cut_id`, the selected `backup_id`, and `review_sha256` copied from the session plan's `data`. Use a private operator-owned file in a private directory (mode `0600` for the file on Debian, inherited operator ACL on Windows). Keep all writers stopped through apply. Eligibility requires an exact verified copy at the time of deletion. Its later availability follows the reviewed rotation policy and any explicitly maintained last-known-good pin.

Rotation retains the newest verified generations in seven daily and four weekly UTC buckets and the explicit last-known-good pin. Apply rechecks the selected generations under the installation fence and requires a verified backup no older than 24 hours. Unrecognized or corrupt artifacts require separate investigation. The disabled Windows and Debian examples include a missed-window fixture procedure. [Scheduling templates](examples/m18/SCHEDULING.md)

After an interrupted capture or prune, use `backup list` and `backup verify`
to confirm the previous good generation. Incomplete staging and a ZIP lacking
its receipt are orphan artifacts. Record them separately and keep them outside
the set of eligible generations. `backup prune` skips them. Retire them only
through an approved operator maintenance procedure after confirming no capture
or recovery still owns them. Treat stale receipts as a missed recovery point
and investigate writer or schedule failures before the next capture window.
