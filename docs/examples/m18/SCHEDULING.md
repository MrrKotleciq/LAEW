# Disabled backup scheduling examples

These examples are inactive design templates. They do not create, enable, or
register a task. The owner must supply an absolute, independently provisioned
profile, a dedicated operator identity, and an approved maintenance window.
Do not put credentials in task arguments, environment variables, or this file.
The backup destination, installation fence, and writer acknowledgement must
already satisfy the backup runbook. Running a backup or prune is a separate
operator decision.

## Standalone worker verification

Use the [disabled Windows task](laew-backup-worker-verify-task.xml.example) or the
[Debian service](laew-backup-worker-verify.service.example) and [timer](laew-backup-worker-verify.timer.example)
as inert templates. They run the protected worker interpreter in isolated mode
and independently verify a single operator-approved generation. Review and
update the selected UUID after a new generation is approved. The advisory path
must be provisioned as described in the [operator runbook](../../M18_BACKUP_RECOVERY.md).
On Windows the example uses the approved operator's interactive token. A logged-out
task needs separate qualification of its logon mode and effective ACLs. On
Debian the worker identity must already be provisioned and non-root. Keep an
external freshness check for missed runs. Supervised capture remains an explicit
operator command with a current writer acknowledgement and release evidence.

## Windows Task Scheduler

Create a disabled task manually under the approved operator identity. Its
single action should invoke the approved LAEW executable with the approved
absolute profile and the runbook's backup command. Configure no overlapping
instances; do not configure wake, startup retry, or automatic elevation by
this template. Enable only after a fixture-host missed-window drill and owner
approval. Never schedule rotation apply without review of the exact ledger.

## systemd timer

Provision a disabled service and timer under the approved operator identity.
Set the service `Type=oneshot`, call the approved LAEW executable and absolute
profile, and omit automatic restart. Use a timer with `Persistent=false`; do
not enable or start either unit as part of installation. The exact unit file,
calendar expression and filesystem access policy are deployment decisions.
Never schedule rotation apply without review of the exact ledger.

## Result and missed runs

Treat exit code zero only as command completion; confirm the independently
verified receipt and surface failures to the operator. A busy fence, missing
writer acknowledgement, unavailable destination, unverified receipt or failed
backup means skip and alert, not a live-copy fallback. Do not run missed jobs
concurrently or launch an automatic catch-up; the owner investigates and
retries in a newly approved window. Retain the previous verified generation
and explicit last-known-good pin through any failed or interrupted run.

## Fixture missed-window procedure

Run only against disposable synthetic data. Use the isolated runner to execute
`tests/integration/test_m18_backup_crash.py`, including
`test_active_cooperating_writer_denies_capture` and the expired acknowledgement
case in `test_unconfirmed_external_writer_stops_capture`. These simulate a busy
fence and an acknowledgement that expired before the drain window. Confirm both
captures fail, no new receipt is published, and the previously verified fixture
archive remains available. Then, in a separate fixture run, provide a fresh
acknowledgement after writers stop and verify the new receipt. Never reuse an
expired acknowledgement, release another process's fence, or retry production
automatically. The example files are placeholders for owner review only; they
are not installed tasks or active units.
