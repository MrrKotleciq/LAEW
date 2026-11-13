"""Fail-closed provenance and admission-boundary checks; no models or stores."""
from copy import deepcopy
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/corpus"))
import review_prusa_r3d as review


@pytest.fixture(scope="module")
def candidate():
    value = os.environ.get("LAEW_PRUSA_R3C_ROOT")
    if not value:
        pytest.skip("Set LAEW_PRUSA_R3C_ROOT to the pinned R3C-v2 workspace")
    return Path(value)


@pytest.fixture(scope="module")
def package(candidate, tmp_path_factory):
    out = tmp_path_factory.mktemp("r3d-review") / "new-overlay"
    summary = review.build(candidate, out)
    return out, summary


def test_observations_do_not_certify_pages_or_add_nonextracted_text(package):
    out, summary = package
    decisions = review.load(out / "human-review-decisions.json")["decisions"]
    images = [r for r in decisions if r["observation"]["category"] == "readable-image-text"]
    unreadable = [r for r in decisions if r["observation"]["category"] == "cannot-read"]
    assert len(images) == 4 and len(unreadable) == 6
    assert sum(r["observation"]["image_language_relation"] == "different-unspecified" for r in images) == 3
    assert next(r for r in images if r["source_id"] == "prusa-mk4s-en")["observation"]["image_language_relation"] == "same-as-document"
    for row in decisions:
        assert row["observation"]["origin"] == "human" and row["reconciliation_origin"] == "agent"
        assert row["observation"]["review_timestamp"] is None
        assert not row["independent_expert_certification"] and not row["complete_page_certified"]
        assert not row["normalized_crosscheck_by_user"] and not row["inherited_priority_cleared"]
        assert row["scope_approval"] == "pending" and row["admission_status"] == "not-admitted"
    for row in images + unreadable:
        assert row["text_only_visual_status"].startswith("unavailable")
        assert not row["technical_interpretation_resolved"] and row["support_restriction"]
    assert all(r["observation"]["original_quote"] == "nie da się odczytać" for r in unreadable)
    assert not summary["freeze_ready"] and not summary["task_3c2b_authorized"]


def test_table_reviews_are_component_scoped_and_keep_xl_footnote(package):
    out, _ = package
    rows = review.load(out / "human-review-decisions.json")["decisions"]
    tables = [r for r in rows if r["table_observation_satisfied"]]
    assert len(tables) == 5
    assert all(len(r["component_ranges"]) == 1 and r["component_ranges"][0]["id"].endswith(":r3b-table") for r in tables)
    assert not any(r["source_id"] == "prusa-xl-de" and r["pdf_page"] == 81 for r in tables)
    xl = next(r for r in tables if r["source_id"] == "prusa-xl-de")
    assert [r["id"] for r in xl["related_context_ranges"]] == ["prusa-xl-de:p9:b16"]


def test_nine_limits_plus_pdu_gate_preserve_safety_and_neighbor_boundaries(package):
    out, _ = package
    regions = review.load(out / "restricted-regions.json")["regions"]
    assert len(regions) == 10
    xl_reset = next(r for r in regions if r["source_id"] == "prusa-xl-de" and r["pdf_page"] == 35)
    assert {s["id"] for s in xl_reset["component_ranges"]} == {f"prusa-xl-de:p35:b{i}" for i in (7, 8, 9)}
    pdu = next(r for r in regions if r["source_id"] == "prusa-xl-de" and r["pdf_page"] == 83)
    assert len(pdu["component_ranges"]) == 3 and len(pdu["related_context_ranges"]) == 5
    assert pdu["availability_marker"] is None  # No marker invented in R3C.
    assert sum(r["availability_marker"] is not None for r in regions) == 9


def test_risk_queue_and_original_snapshots_are_unchanged(candidate, package):
    out, summary = package
    for name in ("availability-register.json", "mandatory-human-review-gates.json", "unresolved-risk-register.json", "warning-applicability-reviewed.json"):
        assert (candidate / name).read_bytes() == (out / f"inherited-{name}").read_bytes()
    assert len(review.load(out / "uninspected-high.json")) == 329
    assert summary["integrity_before"] == summary["integrity_after"]
    assert summary["integrity_after"]["r3c_files"] == 750
    assert not (out / "normalized").exists() and not (out / "originals").exists()
    assert not review.load(out / "admission-policy-proposal.json")["corpus_admitted"]


def test_wrong_page_missing_gate_or_changed_availability_fail_closed(candidate, monkeypatch):
    real_load = review.load
    for filename, mutation in (
        ("mandatory-human-review-gates.json", lambda x: x.pop()),
        ("mandatory-human-review-gates.json", lambda x: x[0].update(page=46)),
        ("availability-register.json", lambda x: x[0]["source_ranges"][0].update(start=0)),
    ):
        def corrupted(path):
            value = deepcopy(real_load(path))
            if path.name == filename:
                mutation(value)
            return value
        with monkeypatch.context() as patch:
            patch.setattr(review, "load", corrupted)
            with pytest.raises(ValueError):
                review.reconcile(candidate)


@pytest.mark.parametrize("field,value", [("page", 2), ("start", -1), ("end", 99), ("id", "missing")])
def test_invalid_component_attribution_is_rejected(field, value):
    span = dict(id="block", page=1, start=0, end=3)
    changed = dict(span, **{field: value})
    with pytest.raises(ValueError):
        review.checked_ranges([changed], {"records": [span]}, "abc", 1)


def test_refuses_existing_output_and_tampering(candidate, package, tmp_path):
    out, _ = package
    with pytest.raises(ValueError, match="NEW external"):
        review.build(candidate, out)
    anchor = review.digest(out / "r3d-integrity-inventory.json")
    assert review.verify(candidate, out, anchor)["verified"]
    with pytest.raises(ValueError, match="trust anchor"):
        review.verify(candidate, out, "0" * 64)
    copied = tmp_path / "tampered-overlay"
    import shutil
    shutil.copytree(out, copied)
    (copied / "human-review-decisions.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="integrity mismatch"):
        review.verify(candidate, copied, anchor)
