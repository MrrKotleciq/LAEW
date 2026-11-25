# M18 implementation and verification

**IMPLEMENTED AND FIXTURE-VERIFIED.** Seven phases and 20 tasks completed on
`codex/m18-monitoring-telemetry-backup`. The integration and recovery verification
commit is `ca134ff77eb84d0a0102773b4621fe94d386c93c`. Production validation and
deployment remain pending separate authorization.

The execution register records the task gates and the owner's decisions. The
operator runbook describes the supported procedures. [Execution register](M18_IMPLEMENTATION_READINESS_AND_PLAN_20261118.md) · [Operator runbook](../M18_BACKUP_RECOVERY.md)

## Verification record

| Environment | Command | Result |
|---|---|---|
| Windows 11, Python 3.14.4, Chroma 1.5.9 | `.venv/Scripts/python.exe scripts/run_isolated.py pytest-offline` | 2,182 passed, 201 skipped, two deselected, 39 dependency warnings in 355.25 s. The preceding full run had the same totals in 306.55 s. Neither A18 nor the earlier Chief HNSW failure recurred. |
| Windows, Node 24.20.0 | `node --test tests/ui/*.test.js` | 30 passed. |
| Windows focused integration and portability | `scripts/run_isolated.py pytest` with the CLI retention, recovery drill, telemetry, console, RAG paths, terminal and installation documentation tests | 74 passed in 33.19 s. |
| Windows final documentation | `scripts/run_isolated.py pytest tests/unit/test_documentation_validation.py tests/unit/test_install_docs.py -q` | 15 passed in 6.18 s. |
| Debian 12, Node 24.20.0, `--network none` | `node --test tests/ui/*.test.js` | 30 passed. |
| Debian 12, Python 3.11.11, pytest 9.1.1, Chroma 1.5.9, Git 2.39.5 | `/tmp/laew-venv/bin/python scripts/run_isolated.py pytest-offline` | 2,153 passed, 230 skipped, two deselected, one dependency warning in 207.89 s. The container had no external network or production mounts. |
| Debian 12, Python 3.11.11, `--network none` | `scripts/run_isolated.py --keep-diagnostics pytest` with session retention, rotation, telemetry retention and operator backup tests | 70 passed in 7.43 s. |
| Debian focused recovery, retention and Landlock | `scripts/run_isolated.py --keep-diagnostics pytest` with the session retention CLI, restore drill and Landlock tests | Four passed, one skipped in 5.99 s. The skip was the unavailable Landlock ABI 9. |

The pre-M18 Windows baseline was 1,901 passed, 197 skipped and two deselected.
The offline selection excludes `live` and `ollama` tests. Remaining skips cover
external evaluation artifacts, optional browser and experimental dependencies,
and platform filesystem or kernel capabilities. The Windows run included the
fixture-based project scope and unified cloud tool regressions.
Debian skipped Windows-only checks and the positive Landlock enforcement case
because ABI 9 was unavailable. The tested Debian configuration kept retained
telemetry disabled. Both platforms ran the local Chroma recovery fixture.

The first full Debian attempt used Python 3.11.11 and Chroma 1.5.9 in an offline
disposable container. It had 2,114 passes, nine failures, 30 setup errors,
230 skips and two deselections. The snapshot lacked Git and the tracked CI
workflow directory and preceded the unit-test count correction. Other failures
identified fixture assumptions about Windows paths, POSIX mark modes, and MSYS
path conversion. Fixture corrections preserve the established runtime path and
tool behavior. A second run with Git reported 2,152 passes, one failure and
230 skips. The path-only source allowlist check counted 36 entries because the
snapshot omitted nine tracked knowledge paths. The follow-up mirrors just those
nine names using synthetic Markdown and passes the complete offline selection.
Windows verified the actual tracked tree.

## Operator interface

Run `laew` from the repository environment or use `python -m laew.cli`. The
existing console and Workbench entry points stay supported. Use `--help` for
options and `--json` for automated inspection.

| Operation | Entry point | Evidence and guard |
|---|---|---|
| Readiness | `status` | Metadata by default. Only explicit `--probe` makes loopback requests. Profile receipts show cached freshness. |
| Run diagnosis | `telemetry show RUN_UUID` | Correlated outcomes, dispatches, tool decisions and usage availability. Retained records require a verified protected installation. |
| Backup inspection | `backup plan`, `backup list`, `backup verify` | Explicit profile. Verification reads the entire archive and compares its receipt, manifest and members. |
| Backup capture | `backup create` | Explicit `--apply`, a current complete writer acknowledgment, and an exclusive maintenance fence. |
| Isolated recovery | `restore --verify-only` or `restore --target TARGET --apply` | Private fresh or empty target. Integrity and semantic validation precede publication. A durable receipt records activation blocks. |
| Retention and rotation | `retention plan`, `retention apply`, `backup prune` | Dry-run by default. Apply requires the unchanged reviewed plan. Session apply adds plan-bound writer evidence. Rotation retains the explicit pin. |

Operator responses expose v1 schemas and stable error identifiers. Common exit
codes are 0 for completed inspection or operation, 1 for unavailable or invalid
state, and 2 for invalid arguments. `status` uses 0 for healthy required checks,
1 for degraded or required unknown and 2 for invalid configuration or an
unavailable required dependency. Scripts should read `overall` and `error_code`.

## Recovery and privacy evidence

- Backup and restore tests exercise committed SQLite WAL state, writer and
  acknowledgment failures, mid-process interruption, receipt-last publication,
  corrupt archives, path and alias checks, private staging, existing target
  refusal, and exact restoration of current and legacy histories.
- A CLI exercise captures a conversation, verifies the 90-day mark and exact
  archive digest, rejects missing, mismatched and expired acknowledgments,
  applies the reviewed plan and restores the same conversation bytes to an
  isolated root. The missed-window tests keep the previous receipt usable while
  a cooperating writer holds the fence or an external writer proof has expired.
- Recovery accepts the valid empty-conversation checkpoint `-1`. Pending or
  running jobs lacking an input conversation are preserved with a durable
  activation block. Historical references are reported separately. New backups
  bind the memory collection identity to the profile without including its
  filesystem path. Recovery detects mismatches and reports older evidence as
  unknown where applicable.
- The failed Workbench fixture is diagnosable with its run UUID and `status`.
  The trace excludes the prompt and error canary and distinguishes a dispatched
  failed provider attempt from unavailable usage accounting. Native boundary
  checks exercise filesystem protection, descendants and platform fail-closed
  behavior. Cloud providers continue through the shared LAEW permission and RAG
  path. The former separate text mode was retired before M18.
- Since `7ab7445`, Production A manifests are identical. The RAG package change
  is an annotation import for older Python, and the runtime change is the
  corresponding registry type import. Retrieval, ingestion, ranking and model
  choices stay on the existing production variant.

## Fixture measurements

| Check | Result |
|---|---|
| Windows telemetry added median / p95, ms | 2.126 / 2.934, 2.028 / 3.791, 2.530 / 3.605. One warm-up and three alternating batches of 500 no-network pairs. Targets were 3 ms median and 10 ms p95. |
| Retained telemetry resource bounds | 256 KiB per accepted run, 256 MiB per protected installation, 30-day ordinary retention. Active and unverified runs are protected during age and emergency review. |
| Windows telemetry disk sample | 20 synthetic four-event traces used 31,176 logical bytes, 1,557–1,559 per trace, plus 56 metadata bytes. Filesystem allocation and production event mixes can differ. |
| Status probes | Three-second aggregate budget with disposable timeout fixture. Default uses cached configuration and metadata. |
| Windows canonical drill | P07 Chroma case captured in 1.195 s and restored in 0.611 s. The archive used 277,424 logical bytes and the restored tree used 275,860 including its receipt. The earlier isolated P05 run took 0.889 s and 0.514 s. |
| Windows derived drill | P07 measured 0.928 s for the memory fixture rebuild and 0.105 s for local Chroma rebuild and retrieval with deterministic embeddings. The earlier isolated P05 run took 0.714 s and 0.084 s. The drill recovered 109 memory outbox versions. |
| Debian canonical and derived drill | The Chroma case captured in 0.098 s and restored in 0.042 s. Its archive used 277,393 logical bytes and the restored tree used 275,829 including its receipt. The memory fixture rebuild took 0.651 s and local Chroma rebuild and retrieval took 0.077 s. |
| Recovery objectives | Approved targets are 24 hours RPO and two hours canonical RTO. Fixture data establishes functionality at test scale. Production storage size, real writer-drain time and index reconstruction require a representative approved drill. |

## Operational disposition

The owner approved the isolated recovery and whole-generation rollback
procedure for the runbook. Production requires explicit approval for private
account and media provisioning, writer maintenance, capture of real data,
schedule activation, destructive retention, live inference and embeddings,
representative recovery, cutover and deployment. Keep the previous generation
and approved configuration available until verification and owner sign-off.
Scheduling examples are disabled and were exercised through synthetic
busy-fence and expired-acknowledgment scenarios.

The approved decisions preserve the current console pending separate migration,
minimize existing audit output, and restrict retained telemetry to a dedicated
protected installation. They also preserve the shared LAEW executor for cloud
models and make RAG freshness classification opt-in. The Windows installation
is the current single authoritative host. Debian is a fixture verification
environment. The approved lifecycle includes path-equivalent restoration,
plan-bound writer evidence for session deletion, an explicit emergency
telemetry quota mode, durable activation blocking for unresolved jobs and
reviewed backup rotation. The execution register records all alternatives and
the owner's rationale.
