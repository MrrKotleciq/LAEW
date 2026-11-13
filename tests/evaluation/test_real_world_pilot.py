"""Pilot draft provenance/span/isolation checks; frozen-source reads only."""
import hashlib
import os
from pathlib import Path
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools/corpus"))
import prepare_real_world_pilot as pilot


@pytest.fixture(scope="module")
def artifacts():
    root = os.environ.get("LAEW_FROZEN_CORPUS_ROOT")
    dataset = os.environ.get("LAEW_REAL_WORLD_PILOT_ROOT")
    if not root or not dataset:
        pytest.skip("Set frozen corpus and external pilot workspace paths")
    return Path(root), Path(dataset)


def test_four_families_twelve_agent_authored_variants_and_labels(artifacts):
    _, out = artifacts
    families = pilot.load(out / "families.json")
    questions = pilot.load(out / "questions.json")
    labels = pilot.load(out / "draft-labels.json")
    assert len(families) == 4 and len(questions) == len(labels) == 12
    assert len({q["id"] for q in questions}) == 12
    assert {q["id"] for q in questions} == {l["question_id"] for l in labels}
    for f in families:
        assert {q["language"] for q in questions if q["family_id"] == f["id"]} == {"en", "pl", "de"}
    assert all(q["origin"] == "agent" and not q["human_reviewed"] for q in questions)
    assert all(l["status"] == "agent_draft" and not l["human_reviewers"] and l["review_time"] is None for l in labels)


def test_spans_rebase_to_exact_full_file_offsets_and_preserve_original_attribution(artifacts):
    root, out = artifacts
    spans = pilot.load(out / "evidence-spans.json")
    assert len(spans) == 25
    for s in spans:
        p = root / "corpus" / s["normalized_path"]
        text = p.read_text(encoding="utf-8")
        assert text[s["start"]:s["end"]] == s["text"]
        assert hashlib.sha256(s["text"].encode()).hexdigest() == s["text_sha256"]
        assert pilot.digest(p) == s["normalized_sha256"]
        assert s["location"]["normalized_heading_path"]
        assert s["qa"]["origin"] == "agent" and not s["qa"]["human_reviewed"]
        if s["id"].startswith("G-"):
            assert s["start"] > 250  # Body map offsets must be rebased beyond YAML.
            assert s["location"]["source_line_from"] > 0
        if s["id"].startswith("M-"):
            assert s["qa"]["original_priority_unchanged"]
            assert (root / "corpus" / s["location"]["render_path"]).is_file()
        if s["id"].startswith("R-release"):
            assert s["location"]["section"].startswith("E.23.2.")
            assert s["location"]["html_anchor"] == "id-1.11.6.28.4"


def test_every_minimal_set_covers_all_facts_and_multidocument_requires_two_units(artifacts):
    _, out = artifacts
    spans = {s["id"]:s for s in pilot.load(out / "evidence-spans.json")}
    for family in pilot.load(out / "families.json"):
        for evidence_set in family["minimal_sufficient_evidence_sets"]:
            assert all(any(set(alt) <= set(evidence_set) for alt in fact["evidence_alternatives"]) for fact in family["facts"])
            docs = {spans[s]["source_id"] for s in evidence_set}
            if family["category"] == "single_document":
                assert len(docs) == 1
            if family["category"] == "multi_document":
                assert len(docs) == 2
    mini = next(f for f in pilot.load(out / "families.json") if f["id"] == "P02")
    locations = [spans[s]["location"]["section"] for s in mini["minimal_sufficient_evidence_sets"][0]]
    assert any(s.startswith("5.3.") for s in locations) and any(s.startswith("9.1.") for s in locations)


def test_restricted_visual_material_and_derived_annotations_never_become_evidence(artifacts):
    root, out = artifacts
    regions = pilot.load(root / "review/r3d/restricted-regions.json")["regions"]
    for s in pilot.load(out / "evidence-spans.json"):
        assert "[Derived" not in s["text"] and "Visual information unavailable" not in s["text"]
        for region in regions:
            if region["source_id"] == s["source_id"]:
                for r in region["component_ranges"] + region["related_context_ranges"]:
                    assert max(r["start"],s["start"]) >= min(r["end"],s["end"])
    qa = pilot.load(out / "targeted-source-qa.json")
    assert qa["priorities_cleared"] == 0 and qa["remaining_uninspected_high"] == 329
    unit = next(u for u in pilot.load(root / "corpus/source-manifest.json")["source_units"] if u["id"] == "prusa-mini-pl")
    with pytest.raises(ValueError, match="Derived/visual"):
        pilot.make_span(root, dict(id="bad", section="9.2.", block_id="prusa-mini-pl:p45:r3b-availability", language="pl"), unit)


def test_table_scope_and_cross_page_cleaning_warning_are_not_dropped(artifacts):
    root, out = artifacts
    spans = {s["id"]:s for s in pilot.load(out / "evidence-spans.json")}
    selected = spans["M-smooth-table"]
    mapping = pilot.load(root / "corpus/maps/prusa-mini-pl.json")
    table = next(r for r in mapping["records"] if r["id"] == selected["location"]["block_id"])
    # Headers plus every value/risk cell of the selected product row are retained;
    # other product rows must not be silently attributed to that row.
    for cell in table["cells"]:
        if cell["end"] > cell["start"] and cell["row"] <= 1:
            assert selected["start"] <= cell["start"] < cell["end"] <= selected["end"]
        if cell["row"] >= 2:
            assert selected["end"] <= cell["start"]
    assert spans["M-clean-start"]["location"]["pdf_page"] == 42
    assert spans["M-clean-tail"]["location"]["pdf_page"] == 43
    family = next(f for f in pilot.load(out / "families.json") if f["id"] == "P02")
    assert ["M-clean-start", "M-clean-tail"] in next(f for f in family["facts"] if f["id"] == "P02-F2")["evidence_alternatives"]


def test_unknown_version_is_clarification_not_absence_or_positive_recall(artifacts):
    _, out = artifacts
    labels = [l for l in pilot.load(out / "draft-labels.json") if l["family_id"] == "P04"]
    assert len(labels) == 3 and all(not l["positive_evidence_recall_applicable"] for l in labels)
    assert all(not l["minimal_sufficient_evidence_sets"] for l in labels)
    scan = pilot.load(out / "corpus-wide-inspection.json")
    assert len(scan["records"]) == 24 and all(r["inspected"] for r in scan["records"])
    assert not scan["absence_assertion"] and scan["human_whole_corpus_adjudication"] == "pending"


def test_sealed_capacity_reserved_and_blind_second_view_does_not_show_draft_labels(artifacts):
    _, out = artifacts
    reserved = pilot.load(out / "split-reservation.json")
    assert reserved["sealed_questions_authored"] == 0
    assert reserved["sealed_families_reserved"] == 16 and reserved["sealed_questions_reserved"] == 48
    blind = (out / "blind-second-review.html").read_text(encoding="utf-8")
    assert "P03-F1" not in blind and "Draft answerability:" not in blind
    review = pilot.load(out / "review-requirements.json")
    assert review["independently_second_label_families"] == ["P02", "P04"]
    assert not review["reviewers"] and review["independently_reviewed_labels"] == 0


def test_html_anchors_and_visible_text_normalization(artifacts):
    root, out = artifacts
    source = pilot.load(out / "authoring-plan.json")
    units = {u["id"]:u for u in pilot.load(root / "corpus/source-manifest.json")["source_units"]}
    spec = dict(next(s for s in source["spans"] if s["id"] == "R-release-move"), anchor="nonexistent-anchor")
    with pytest.raises(ValueError, match="anchor absent"):
        pilot.make_span(root, spec, units[spec["source_id"]])
    assert pilot.plain_markdown('See [label](https://example/a\\(b\\) "Title") and `wal_name`.') == "See label and wal_name."


def test_hash_freeze_is_read_only_and_rejects_label_tampering(artifacts, tmp_path):
    root, out = artifacts
    anchor = pilot.digest(out / "pilot-integrity-manifest.json")
    assert pilot.verify(root, out, anchor)["verified"]
    copied = tmp_path / "tampered-pilot"
    shutil.copytree(out, copied)
    (copied / "draft-labels.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="Pilot artifact changed"):
        pilot.verify(root, copied, anchor)
    with pytest.raises(ValueError, match="trust anchor"):
        pilot.verify(root, out, "0" * 64)
