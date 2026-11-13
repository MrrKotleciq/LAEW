"""Freeze preflight provenance/integrity checks; never execute a freeze."""
from copy import deepcopy
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/corpus"))
import preflight_prusa_r3e as preflight


@pytest.fixture(scope="module")
def inputs():
    root = os.environ.get("LAEW_PRUSA_R3C_ROOT")
    review = os.environ.get("LAEW_PRUSA_R3D_ROOT")
    if not root or not review:
        pytest.skip("Set LAEW_PRUSA_R3C_ROOT and LAEW_PRUSA_R3D_ROOT to the pinned local snapshots")
    return Path(root), Path(review)


@pytest.fixture(scope="module")
def package(inputs, tmp_path_factory):
    parent = tmp_path_factory.mktemp("r3e-preflight")
    out, target = parent / "preflight-v1", parent / preflight.FREEZE_ID
    summary = preflight.prepare(*inputs, out, target)
    return out, target, summary


def test_approval_is_exact_and_never_becomes_freeze_or_semantic_certification(inputs, package):
    _, review = inputs
    out, target, summary = package
    approval = preflight.r3d.load(out / "admission-approval.json")
    assert approval["status"] == "restricted-policy-approved" and approval["origin"] == "human"
    assert approval["approved_policy"]["sha256"] == preflight.r3d.digest(review / "admission-policy-proposal.json")
    assert not approval["full_semantic_certification"] and approval["priorities_cleared"] == 0
    assert not approval["freeze_execution_approved"] and not approval["question_generation_approved"]
    assert approval["approval_timestamp"] is None
    assert not target.exists() and not summary["freeze_executed"]
    assert summary["readiness"]["technical_preflight_passed"]
    assert summary["readiness"]["freeze_authorization_blockers"]
    assert summary["readiness"]["task_3c2b_blockers"]


def test_readiness_file_is_original_external_artifact_and_missing_copy_is_not_recreated(inputs, package, tmp_path):
    root, review = inputs
    out, _, _ = package
    report = preflight.r3d.load(out / "readiness-discrepancy.json")
    assert report["status"] == "reported-missing-file-not-reproduced" and not report["recreated"]
    assert all(e["matches_original_inventory"] for e in report["evidence"])
    copied = tmp_path / "r3d-missing-readiness"
    shutil.copytree(review, copied)
    (copied / "readiness.json").unlink()
    with pytest.raises(ValueError, match="Missing required artifact"):
        preflight.discrepancy(root, copied)
    assert not (copied / "readiness.json").exists()


@pytest.mark.parametrize("source_id,field,value", [
    ("prusa-mk4s-en", "revision", "other-edition"),
    ("postgresql-17-runtime-config-wal", "commit", "0" * 40),
    ("progit-config-pl", "language_status", "authentic-pl"),
    ("progit-submodules-de", "source_path", "other-section.asc"),
    ("prusa-xl-de", "license", {"id": "invented-permission"}),
])
def test_revision_wal_language_license_and_source_substitutions_are_rejected(inputs, monkeypatch, source_id, field, value):
    root, _ = inputs
    real_load = preflight.r3d.load
    def changed(path):
        result = deepcopy(real_load(path))
        if path == root / "source-manifest.json":
            next(u for u in result["source_units"] if u["id"] == source_id)[field] = value
        return result
    monkeypatch.setattr(preflight.r3d, "load", changed)
    with pytest.raises(ValueError, match="identity/revision/license/language changed"):
        preflight.source_identities(root)


def test_plan_retains_all_files_24_identities_and_exact_risk_queue(inputs, package):
    root, review = inputs
    out, target, summary = package
    plan = preflight.r3d.load(out / "freeze-manifest.draft.json")
    entries = {e["destination"]: e for e in plan["copy_entries"]}
    expected_corpus = {f["path"] for f in preflight.r3d.load(root / "r3c-integrity-inventory.json")["files"]} | {"r3c-integrity-inventory.json"}
    assert {p.removeprefix("corpus/") for p in entries if p.startswith("corpus/")} == expected_corpus
    assert len(plan["identities"]) == 24
    assert plan["risk_summary"]["uninspected_high"] == 329
    assert plan["risk_summary"]["exact_high_queue"]["sha256"] == preflight.r3d.digest(review / "uninspected-high.json")
    assert plan["risk_summary"]["severity_counts"] == dict(Critical=0, High=388, Medium=10, Low=20)
    assert not target.exists()
    for u in plan["identities"]:
        for prefix in ("original", "normalized"):
            assert entries["corpus/" + u[prefix + "_path"]]["sha256"] == u[prefix + "_sha256"]
    assert plan["procedure_sha256"] == preflight.r3d.digest(out / "freeze-procedure.ps1")
    assert summary["copy_files"] == len(entries)


def test_changed_high_queue_is_not_implicitly_approved(inputs, monkeypatch):
    root, review = inputs
    real_load = preflight.r3d.load
    def changed(path):
        result = deepcopy(real_load(path))
        if path == review / "uninspected-high.json":
            result.pop()
        return result
    monkeypatch.setattr(preflight.r3d, "load", changed)
    with pytest.raises(ValueError, match="Exact uninspected High"):
        preflight.risk_check(root, review)


def test_verification_is_read_only_and_rejects_tampered_or_existing_targets(inputs, package, tmp_path):
    out, target, summary = package
    anchor = summary["r3e_inventory_sha256"]
    assert preflight.verify(*inputs, out, anchor)["verified"]
    assert not target.exists()
    with pytest.raises(ValueError, match="trust anchor"):
        preflight.verify(*inputs, out, "0" * 64)
    copied = tmp_path / "r3e-tampered"
    shutil.copytree(out, copied)
    preflight.r3d.write(copied / "admission-approval.json", {"freeze_execution_approved": True})
    with pytest.raises(ValueError, match="artifact integrity mismatch"):
        preflight.verify(*inputs, copied, anchor)
    target.mkdir()  # A directory, not a performed freeze, blocks reuse.
    with pytest.raises(ValueError, match="pending unexecuted"):
        preflight.verify(*inputs, out, anchor)


def test_preflight_refuses_snapshot_or_repository_reuse(inputs, package):
    out, target, _ = package
    with pytest.raises(ValueError, match="new preflight"):
        preflight.prepare(*inputs, out, target)
    with pytest.raises(ValueError):
        preflight.prepare(*inputs, inputs[0] / "nested-preflight", target)
