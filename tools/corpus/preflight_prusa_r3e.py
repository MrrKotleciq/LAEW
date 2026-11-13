"""Record approved restricted scope and prepare an unexecuted corpus freeze plan.

Preparation and verification only. The generated PowerShell procedure is a
reviewable future action and is never invoked by this module or its tests.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil

import review_prusa_r3d as r3d


R3D_SHA = "07cb927d96d0153681f0034aed8502e46ca0334fcb4e1305b1b0e3a4b90f7d0f"
WAL = "220b5263dbb71bbe2966c6d47c0c456c14ed4e48"
FREEZE_ID = "stage-2b2-real-world-20261112-freeze-v1"
IDENTITY_KEYS = (
    "id", "family", "language", "language_status", "revision", "commit", "release_tag",
    "released_baseline_tag", "source_path", "upstream_path", "license", "printed_revision_date",
    "hardware", "applicable_versions", "firmware_pin", "canonical_url", "url", "publisher",
    "edition", "language_review", "original_sha256", "original_path",
)

FUTURE_PROCEDURE = r'''# Prepared by R3E. DO NOT RUN without separate human freeze approval.
param(
    [Parameter(Mandatory=$true)][string]$PlanPath,
    [Parameter(Mandatory=$true)][string]$ExpectedPlanSha256,
    [Parameter(Mandatory=$true)][string]$ApprovalRecordPath
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function CheckedFile([string]$Path, [string]$Sha256, [long]$Bytes) {
    $item = Get-Item -LiteralPath $Path -Force
    if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
        $item.Length -ne $Bytes -or (Hash $Path) -ne $Sha256) { throw "File integrity mismatch: $Path" }
}
if ((Hash $PlanPath) -ne $ExpectedPlanSha256) { throw 'Plan trust anchor mismatch' }
$plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($plan.status -ne 'prepared-not-executed' -or $plan.freeze_executed -ne $false) { throw 'Not a pending freeze plan' }
if ((Hash $PSCommandPath) -ne $plan.procedure_sha256) { throw 'Procedure differs from reviewed plan' }
$approval = Get-Content -LiteralPath $ApprovalRecordPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($approval.approved -ne $true -or $approval.origin -ne 'human' -or
    $approval.purpose -ne 'corpus-freeze-only' -or $approval.freeze_id -ne $plan.freeze_id -or
    $approval.plan_sha256 -ne $ExpectedPlanSha256 -or [string]::IsNullOrWhiteSpace($approval.user_instruction)) {
    throw 'Separate human freeze approval bound to this exact plan is required'
}
$target = [IO.Path]::GetFullPath($plan.target)
if (Test-Path -LiteralPath $target) { throw 'Freeze target already exists; never overwrite a snapshot' }
# Reject reparse-point ancestors before creating any destination.
$parent = [IO.DirectoryInfo]::new([IO.Path]::GetDirectoryName($target))
while ($null -ne $parent) {
    if ($parent.Exists -and ($parent.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Reparse-point target ancestor' }
    $parent = $parent.Parent
}
$entries = @($plan.copy_entries)
$seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$rootPrefix = $target.TrimEnd([char[]]'\/') + [IO.Path]::DirectorySeparatorChar
foreach ($entry in $entries) {
    $destination = [IO.Path]::GetFullPath([IO.Path]::Combine($target, $entry.destination))
    if (-not $destination.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $seen.Add($destination)) { throw 'Invalid or duplicate destination' }
    CheckedFile $entry.source $entry.sha256 $entry.bytes
}
# No source is modified, and no deletion, model, index or network command exists.
New-Item -ItemType Directory -Path $target | Out-Null
foreach ($entry in $entries) {
    $destination = [IO.Path]::Combine($target, $entry.destination)
    $directory = [IO.Path]::GetDirectoryName($destination)
    if (-not (Test-Path -LiteralPath $directory)) { New-Item -ItemType Directory -Path $directory | Out-Null }
    Copy-Item -LiteralPath $entry.source -Destination $destination
    CheckedFile $destination $entry.sha256 $entry.bytes
}
# Recheck source files and the plan/approval after the copy, before a receipt.
foreach ($entry in $entries) { CheckedFile $entry.source $entry.sha256 $entry.bytes }
if ((Hash $PlanPath) -ne $ExpectedPlanSha256) { throw 'Plan changed during copying' }
$approvalAgain = Get-Content -LiteralPath $ApprovalRecordPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (($approvalAgain | ConvertTo-Json -Depth 50 -Compress) -ne ($approval | ConvertTo-Json -Depth 50 -Compress)) { throw 'Approval changed during copying' }
Copy-Item -LiteralPath $PlanPath -Destination ([IO.Path]::Combine($target, 'freeze-manifest.json'))
Copy-Item -LiteralPath $ApprovalRecordPath -Destination ([IO.Path]::Combine($target, 'freeze-approval.json'))
if ((Hash ([IO.Path]::Combine($target, 'freeze-manifest.json'))) -ne $ExpectedPlanSha256) { throw 'Copied plan mismatch' }
$receipt = [ordered]@{
    status='frozen-restricted-text-only'; freeze_id=$plan.freeze_id
    plan_sha256=$ExpectedPlanSha256; copied_files=$entries.Count
    completed_at_utc=[DateTime]::UtcNow.ToString('o')
    approval_sha256=(Hash ([IO.Path]::Combine($target, 'freeze-approval.json')))
    semantic_certification=$false; questions_created=$false; indexed=$false; inference_run=$false
}
$receipt | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath ([IO.Path]::Combine($target, 'freeze-receipt.json')) -Encoding UTF8
Write-Output "Freeze copy complete. Verify every destination against freeze-manifest.json before subsequent use: $target"
'''


def file_record(root, relative):
    path = r3d.local(root, relative)
    if not path.is_file():
        raise ValueError("Missing required artifact: " + str(path))
    return dict(path=relative, sha256=r3d.digest(path), bytes=path.stat().st_size)


def source_identities(root):
    manifest = r3d.load(root / "source-manifest.json")
    accepted = r3d.load(Path(manifest["input_workspaces"]["accepted"]) / "source-manifest.json")
    baseline = {u["id"]: u for u in accepted["source_units"]}
    units = manifest["source_units"]
    if len(units) != 24 or {u["id"] for u in units} != set(baseline):
        raise ValueError("Source selection mismatch")
    if Counter(u["family"] for u in units) != Counter(prusa=6, progit=12, postgresql=6):
        raise ValueError("Source family counts changed")
    records = []
    for unit in units:
        prior = baseline[unit["id"]]
        if any(unit.get(k) != prior.get(k) for k in IDENTITY_KEYS):
            raise ValueError("Source identity/revision/license/language changed: " + unit["id"])
        record = {k: unit.get(k) for k in IDENTITY_KEYS}
        record["normalized_path"] = unit["normalized_path"]
        record["normalized_sha256"] = unit["normalized_sha256"]
        record["source_map"] = unit["source_map"]
        paths = [unit["original_path"], unit["normalized_path"], unit["source_map"], unit["license"]["notice_path"]]
        paths += [unit[k] for k in ("language_map", "upstream_path", "rendered_path") if unit.get(k)]
        record["artifact_hashes"] = [file_record(root, p) for p in dict.fromkeys(paths)]
        for field in ("original", "normalized"):
            if r3d.digest(r3d.local(root, unit[field + "_path"])) != unit[field + "_sha256"]:
                raise ValueError("Source content hash mismatch: " + unit["id"])
        if unit["family"] != "prusa" and unit["normalized_sha256"] != prior["normalized_sha256"]:
            raise ValueError("One of eighteen preserved text units changed")
        if unit["family"] == "prusa" and (not unit.get("revision") or not unit.get("printed_revision_date")):
            raise ValueError("Manual edition/date missing")
        if unit["family"] != "prusa" and (len(unit.get("commit", "")) != 40 or not unit.get("source_path")):
            raise ValueError("Source commit/path pin missing")
        record["verified_against_accepted_identity"] = True
        records.append(record)
    if next(u["commit"] for u in units if u["id"] == "postgresql-17-runtime-config-wal") != WAL:
        raise ValueError("Pinned WAL commit changed")
    return records


def discrepancy(root, review):
    result = dict(status="reported-missing-file-not-reproduced", recreated=False,
        explanation="R3D used an unlinked bare filename for an external artifact. Repository-relative readiness.json does not exist by design. The user's exact lookup/history is unknown; do not assert deletion or a specific UI failure.",
        correction="R3D report now links the exact historical external path and current R3E assessment; R3D and R3C files remain unchanged.")
    result["evidence"] = []
    for workspace, inventory in ((root, "r3c-integrity-inventory.json"), (review, "r3d-integrity-inventory.json")):
        current = file_record(workspace, "readiness.json")
        expected = next(f for f in r3d.load(workspace / inventory)["files"] if f["path"] == "readiness.json")
        if current != expected:
            raise ValueError("Historical readiness file missing or changed")
        result["evidence"].append(dict(workspace=str(workspace), **current, matches_original_inventory=True))
    return result


def risk_check(root, review):
    risks = r3d.load(root / "unresolved-risk-register.json")
    high = [p for p in risks if p["original_severity"] == "High" and not p["r3b_inspected"]]
    if high != r3d.load(review / "uninspected-high.json") or len(high) != 329:
        raise ValueError("Exact uninspected High queue changed")
    if risks != r3d.load(review / "inherited-unresolved-risk-register.json"):
        raise ValueError("Inherited risk register differs")
    counts = Counter(p["original_severity"] for p in risks)
    if len(risks) != 418 or counts != Counter(High=388, Medium=10, Low=20):
        raise ValueError("Priorities changed")
    return dict(records=418, severity_counts=dict(Critical=0, High=388, Medium=10, Low=20),
        uninspected_high=329, uninspected_medium=9, uninspected_low=20, priorities_cleared=0,
        risk_register=file_record(root, "unresolved-risk-register.json"), exact_high_queue=file_record(review, "uninspected-high.json"),
        interpretation="All priorities remain open; approval accepts restricted support, not technical certification or automatic clearance.")


def copy_entries(root, review, out):
    entries = []
    for workspace, inventory, prefix in ((root, "r3c-integrity-inventory.json", "corpus"), (review, "r3d-integrity-inventory.json", "review/r3d")):
        files = r3d.load(workspace / inventory)["files"] + [file_record(workspace, inventory)]
        for f in files:
            entries.append(dict(source=str(r3d.local(workspace, f["path"])), destination=prefix + "/" + f["path"], sha256=f["sha256"], bytes=f["bytes"]))
    for path in sorted(out.iterdir()):
        if path.is_file():
            entries.append(dict(source=str(path), destination="review/r3e/" + path.name, sha256=r3d.digest(path), bytes=path.stat().st_size))
    if len({e["destination"].casefold() for e in entries}) != len(entries):
        raise ValueError("Duplicate freeze destination")
    return entries


def prepare(root, review, out, target):
    root, review, out, target = [p.resolve() for p in (root, review, out, target)]
    repo = Path(__file__).resolve().parents[2]
    if out.exists() or target.exists():
        raise ValueError("Use new preflight and freeze target paths; never overwrite")
    all_paths = [root, review, out, target]
    if any(a != b and (a.is_relative_to(b) or b.is_relative_to(a)) for i, a in enumerate(all_paths) for b in all_paths[i + 1:]):
        raise ValueError("Workspaces must be separate siblings")
    if out.is_relative_to(repo) or target.is_relative_to(repo) or target.name != FREEZE_ID:
        raise ValueError("Use external versioned staging and the reviewed freeze ID")
    verified = r3d.verify(root, review, R3D_SHA)
    identities = source_identities(root)
    missing = discrepancy(root, review)
    risk = risk_check(root, review)
    approved_policy = file_record(review, "admission-policy-proposal.json")
    restrictions = r3d.load(review / "restricted-regions.json")
    if len(restrictions["regions"]) != 10 or restrictions["inherited_region_count"] != 9:
        raise ValueError("Availability scope changed")
    out.mkdir(parents=True)
    approval = dict(task="3C.2A-R3E", status="restricted-policy-approved", origin="human", recorded_date="2026-11-12",
        approval_timestamp=None, provenance="Direct current user instruction: LAEW Task 3C.2A-R3E Admission Approval & Freeze Preflight",
        supplied_statement="The user approves the restricted text-only corpus admission policy from R3D.",
        approved_policy=dict(workspace=str(review), **approved_policy), approved_restrictions=file_record(review, "restricted-regions.json"),
        administrative_admission="24-unit source selection accepted only under the approved text-only evidence restrictions",
        full_semantic_certification=False, priorities_cleared=0, corpus_frozen=False, freeze_execution_approved=False,
        question_generation_approved=False, benchmark_approved=False, inference_approved=False,
        historical_metadata="R3C/R3D candidate/pending labels remain historical. This overlay records the current scope approval without changing source bytes.")
    readiness = dict(task="3C.2A-R3E", status="restricted-admission-approved-freeze-preflight-ready-awaiting-freeze-approval",
        scope_approved=True, corpus_frozen=False, technical_preflight_passed=True, freeze_execution_authorized=False,
        technical_freeze_blockers=[], freeze_authorization_blockers=["Separate human approval of this exact versioned freeze plan and destination is required."],
        task_3c2b_authorized=False, task_3c2b_blockers=["Corpus freeze not executed/verified", "Separate Task 3C.2B authorization pending", "Domain, bilingual and independent second-review roles not assigned in the supplied instructions"],
        later_task_requirements=["Targeted source/span/prerequisite/warning QA before accepting evidence labels", "Verify six-manual answerability, language/distance quotas and pilot/sealed separation before dataset seal"],
        nonblocking_retained_limits=["Ten approved unavailable/relationship components", "329 uninspected High plus all other open priorities; unjudged until targeted QA", "No full semantic certification; graphics need not be reconstructed"],
        source_units=24, unchanged_git_postgresql_units=18, human_observations=15, restricted_regions=10, risk_summary=risk,
        freeze_target=str(target), freeze_id=FREEZE_ID,
        resource_review_trigger_exceeded=False, resource_basis="Unchanged R3C measurements: 2171 legacy / 2185 structure-v2 chunks; no embedding/index run",
        limitation="This is source-only freeze readiness. Question/gold/dataset sealing and benchmark execution remain separate.")
    r3d.write(out / "admission-approval.json", approval)
    r3d.write(out / "readiness-discrepancy.json", missing)
    r3d.write(out / "source-identity-verification.json", dict(units=identities, wal_commit=WAL, verification="Offline identity/hash/pin preservation, not live publisher freshness or complete semantic QA"))
    r3d.write(out / "availability-restrictions-approved.json", dict(status="scope-approved-unavailability-retained", approval_record="admission-approval.json", original_restrictions=restrictions,
        original_file=file_record(review, "restricted-regions.json"), no_transcription=True, technical_meaning_resolved=False))
    r3d.write(out / "risk-preservation.json", risk)
    r3d.write(out / "readiness.json", readiness)
    (out / "freeze-procedure.ps1").write_text(FUTURE_PROCEDURE, encoding="utf-8")
    (out / "FREEZE_PROCEDURE.md").write_text(
        "# Prepared source-only freeze procedure — NOT EXECUTED\n\n"
        "Restricted scope is approved; freeze execution is not. Keep this metadata workspace and all prior snapshots unchanged. "
        "The draft manifest identifies an exact new destination, all 24 source identities, hashes, pins, licenses, availability restrictions and every file to copy. "
        "It preserves complete R3C-v2 under corpus/ and historical R3D under review/r3d/, with current R3E approval metadata under review/r3e/. "
        "No rendering, source normalization, labels, vectors, indexes or inference are involved.\n\n"
        "1. Read the R3E report and freeze-manifest.draft.json. Obtain a NEW explicit user approval for this freeze ID, destination and exact manifest SHA-256. "
        "The R3E admission approval is not freeze approval. Record that later user instruction in a separate external JSON record with approved=true, "
        "origin=human, purpose=corpus-freeze-only, freeze_id, plan_sha256 and nonempty user_instruction. Do not fabricate a review timestamp or credentials.\n"
        "2. Re-run `python -B tools/corpus/preflight_prusa_r3e.py --verify --r3c <R3C> --r3d <R3D> --output <R3E> --expected-inventory-sha <R3E-report-anchor>`. "
        "It must pass all inventories, code hashes, exact copy entries and original source identities. Any change requires a new version/preflight/approval; do not update hashes in place.\n"
        "3. ONLY AFTER approval and successful preflight, use PowerShell: `& '<R3E>\\freeze-procedure.ps1' -PlanPath '<R3E>\\freeze-manifest.draft.json' "
        "-ExpectedPlanSha256 '<reviewed-plan-sha256>' -ApprovalRecordPath '<later-separate-human-freeze-approval.json>'`. "
        "The script checks the plan and its own hash, approval purpose/binding, source hashes and new destination before copying. "
        "It rechecks source/destination bytes before writing a completion receipt. Never overwrite/reuse a failed partial target or delete an earlier snapshot automatically.\n"
        "4. Independently read freeze-manifest.json in the new target. For EVERY copy_entries item, check the destination exists under the target with exact byte length and SHA-256; "
        "check freeze-receipt.json binds the reviewed plan and approval hashes, exact file count and completed status. "
        "Check no files exist other than all destinations plus freeze-manifest.json, freeze-approval.json and freeze-receipt.json. "
        "Use the read-only verification snippet below. A missing receipt/failed check means incomplete freeze, never a usable frozen corpus.\n"
        "5. Record completion and immutable hashes in a separate follow-up report. Logical hash freezing does not enforce filesystem immutability; verify before every later use. "
        "Archived R3C/R3D/R3E status fields and absolute staging references are historical; the plan/receipt define the completed source snapshot. "
        "Do not rewrite archived manifests to change historical status labels.\n"
        "6. Stop. Obtain separate Task 3C.2B authorization and reviewer assignments. This source freeze never authorizes question generation, gold labels, indexing or benchmarks.\n\n"
        "## Read-only verification after a separately approved copy\n\n"
        "```python\nimport hashlib, json\nfrom pathlib import Path\n"
        "target = Path(r'<approved-freeze-target>')\nplan = json.loads((target/'freeze-manifest.json').read_text(encoding='utf-8-sig'))\n"
        "receipt = json.loads((target/'freeze-receipt.json').read_text(encoding='utf-8-sig'))\n"
        "sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()\n"
        "assert sha(target/'freeze-manifest.json') == '<reviewed-plan-sha256>' == receipt['plan_sha256']\n"
        "assert receipt['status'] == 'frozen-restricted-text-only' and receipt['freeze_id'] == plan['freeze_id']\n"
        "assert receipt['approval_sha256'] == sha(target/'freeze-approval.json')\n"
        "assert receipt['copied_files'] == len(plan['copy_entries'])\n"
        "for entry in plan['copy_entries']:\n    p = (target/entry['destination']).resolve()\n"
        "    assert p.is_relative_to(target.resolve()) and p.is_file()\n    assert p.stat().st_size == entry['bytes'] and sha(p) == entry['sha256']\n"
        "expected = {e['destination'] for e in plan['copy_entries']} | {'freeze-manifest.json','freeze-approval.json','freeze-receipt.json'}\n"
        "assert {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} == expected\n```\n",
        encoding="utf-8")
    shutil.copyfile(Path(__file__), out / "preflight_prusa_r3e.py")
    after = r3d.verify(root, review, R3D_SHA)
    if verified != after:
        raise ValueError("Historical inputs changed during preflight")
    r3d.write(out / "preflight-verification.json", dict(before=verified, after=after, source_units_verified=24, source_or_prior_metadata_modified=False))
    code_names = ["tools/corpus/preflight_prusa_r3e.py", "tools/corpus/review_prusa_r3d.py", "scripts/run_isolated.py"]
    # Pin imported corpus helpers too; HEAD is insufficient in this dirty checkout.
    import sys
    for module in list(sys.modules.values()):
        value = getattr(module, "__file__", None)
        if value:
            path = Path(value).resolve()
            if path.is_relative_to(repo / "tools/corpus"):
                code_names.append(path.relative_to(repo).as_posix())
    code = [file_record(repo, name) for name in sorted(set(code_names))]
    plan = dict(schema_version=1, freeze_id=FREEZE_ID, status="prepared-not-executed", freeze_executed=False, target=str(target),
        scope="Source-only, restricted text-only; not dataset/question/gold freeze or full semantic certification",
        r3c_root=str(root), r3d_root=str(review), r3e_root=str(out), code_sha256=code,
        input_anchors=dict(r3c=r3d.R3C_SHA, r3d=R3D_SHA), identities=identities,
        admission_approval=file_record(out, "admission-approval.json"), restrictions=file_record(out, "availability-restrictions-approved.json"),
        risk_summary=risk, procedure_sha256=r3d.digest(out / "freeze-procedure.ps1"), copy_entries=copy_entries(root, review, out),
        self_exclusion="This draft manifest and later R3E integrity inventory are not recursively included in copy_entries. The procedure copies this exact manifest separately as freeze-manifest.json; the completion receipt binds its hash.",
        approval_required="NEW separate human corpus-freeze-only approval bound to freeze ID, destination and exact draft-manifest hash. Scope approval alone is insufficient.",
        unchanged_representation="Source-once Markdown; no H6 packets or per-chunk warning duplication",
        production_changes=False, question_generation_authorized=False, indexing_authorized=False, inference_authorized=False)
    r3d.write(out / "freeze-manifest.draft.json", plan)
    r3d.write(out / "r3e-integrity-inventory.json", dict(files=[file_record(out, p.name) for p in sorted(out.iterdir()) if p.is_file()]))
    return dict(status=readiness["status"], output=str(out), freeze_executed=False, source_units=24,
        r3e_inventory_sha256=r3d.digest(out / "r3e-integrity-inventory.json"), freeze_plan_sha256=r3d.digest(out / "freeze-manifest.draft.json"),
        copy_files=len(plan["copy_entries"]), copy_bytes=sum(f["bytes"] for f in plan["copy_entries"]), readiness=readiness)


def verify(root, review, out, expected):
    inventory = out / "r3e-integrity-inventory.json"
    if not expected or r3d.digest(inventory) != expected:
        raise ValueError("R3E inventory trust anchor mismatch")
    records = r3d.load(inventory)["files"]
    if {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} != {f["path"] for f in records} | {inventory.name}:
        raise ValueError("Missing or unexpected preflight artifacts")
    for f in records:
        if file_record(out, f["path"]) != f:
            raise ValueError("R3E artifact integrity mismatch: " + f["path"])
    historical = r3d.verify(root, review, R3D_SHA)
    if historical != r3d.load(out / "preflight-verification.json")["after"]:
        raise ValueError("Historical verification changed")
    plan = r3d.load(out / "freeze-manifest.draft.json")
    if plan["freeze_executed"] or plan["status"] != "prepared-not-executed" or Path(plan["target"]).exists():
        raise ValueError("Freeze is no longer a pending unexecuted plan")
    if source_identities(root) != plan["identities"] or risk_check(root, review) != plan["risk_summary"]:
        raise ValueError("Source identity/restriction/risk basis changed")
    repo = Path(__file__).resolve().parents[2]
    for f in plan["code_sha256"]:
        if file_record(repo, f["path"]) != f:
            raise ValueError("Preflight code changed: " + f["path"])
    for f in plan["copy_entries"]:
        p = Path(f["source"])
        if not p.is_file() or r3d.digest(p) != f["sha256"] or p.stat().st_size != f["bytes"]:
            raise ValueError("Planned source copy changed: " + f["source"])
    return dict(verified=True, freeze_executed=False, freeze_execution_authorized=False, source_units=24,
        r3e_inventory_sha256=expected, freeze_plan_sha256=r3d.digest(out / "freeze-manifest.draft.json"), copy_files=len(plan["copy_entries"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r3c", type=Path, required=True)
    parser.add_argument("--r3d", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-inventory-sha")
    args = parser.parse_args()
    if args.verify:
        result = verify(args.r3c, args.r3d, args.output, args.expected_inventory_sha)
    else:
        if args.target is None:
            parser.error("Preparation requires --target; the target will NOT be created")
        result = prepare(args.r3c, args.r3d, args.output, args.target)
    print(json.dumps(result, indent=2))
