"""Record supplied human observations and propose scope; never admit or freeze.

Uses only the pinned local R3C snapshot. No PDF interpretation, OCR, loader,
model, index, network or production configuration is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil

from finalize_prusa_r3c import verify as verify_r3c


R3C_SHA = "c63e3eddfc17b9c04f420d1ec3cb2e1c7196b3ffaeae9346a58fcadf600a93aa"
TASK = "3C.2A-R3D"
# These are observations from the user's current task instruction, not agent QA.
OBSERVATIONS = {
    ("prusa-xl-de", 35): ("readable-image-text", "different-unspecified"),
    ("prusa-mk4-de", 22): ("readable-image-text", "different-unspecified"),
    ("prusa-mk4-de", 33): ("readable-image-text", "different-unspecified"),
    ("prusa-mk4s-en", 19): ("readable-image-text", "same-as-document"),
    ("prusa-mk4-de", 7): ("table-no-visible-errors", None),
    ("prusa-mk4-de", 8): ("table-no-visible-errors", None),
    ("prusa-mk4s-en", 6): ("table-no-visible-errors", None),
    ("prusa-mmu3-en", 7): ("table-no-visible-errors", None),
    ("prusa-xl-de", 9): ("table-no-visible-errors", None),
    ("prusa-mk3s-pl", 16): ("cannot-read", None),
    ("prusa-mk3s-pl", 37): ("cannot-read", None),
    ("prusa-mini-pl", 45): ("cannot-read", None),
    ("prusa-mmu3-en", 6): ("cannot-read", None),
    ("prusa-xl-de", 81): ("cannot-read", None),
    ("prusa-xl-de", 83): ("cannot-read", None),
}
RELATION_LIMITS = {
    ("prusa-mk3s-pl", 16): "Graphical column polarity; do not infer advantages/disadvantages from column position.",
    ("prusa-mk3s-pl", 37): "Icon/callout association and feed-rate instruction scope remain unresolved.",
    ("prusa-mini-pl", 45): "Section 9.2 graphical column polarity; section 9.1 is not covered by this restriction.",
    ("prusa-mmu3-en", 6): "Safety-symbol-to-description mapping and symbol-dependent actions.",
    ("prusa-xl-de", 81): "Electrical symbol meaning/association and complete PDU operational support.",
    ("prusa-xl-de", 83): "PDU visual identification, numbered label-to-part/terminal geometry and connections.",
    ("prusa-mk4-de", 33): "Complete factory-reset sequence and screenshot-only confirmation qualifier.",
    ("prusa-xl-de", 35): "Complete factory-reset sequence and screenshot-only confirmation qualifier.",
    ("prusa-mk4-de", 22): "Complete sensor-test startup/screen-driven procedure.",
    ("prusa-mk4s-en", 19): "Complete sensor-test startup/screen-driven procedure.",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def local(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Path escapes pinned workspace")
    return path


def integrity(root):
    inputs = load(root / "source-manifest.json")["input_workspaces"]
    return verify_r3c(root, *(Path(inputs[k]) for k in ("accepted", "r2", "r3a", "r3b")), R3C_SHA)


def checked_ranges(ranges, mapping, text, page):
    records = {r["id"]: r for r in mapping["records"]}
    result = []
    for span in ranges:
        record = records.get(span["id"])
        if record is None or any(span[k] != record[k] for k in ("page", "start", "end")):
            raise ValueError("Source range differs from exact R3C record")
        if span["page"] != page or not 0 <= span["start"] < span["end"] <= len(text):
            raise ValueError("Wrong PDF page or invalid Unicode offsets")
        result.append(dict(span, sha256_utf8=hashlib.sha256(text[span["start"]:span["end"]].encode("utf-8")).hexdigest()))
    if not result:
        raise ValueError("Empty component mapping")
    return result


def reconcile(root):
    manifest = load(root / "source-manifest.json")
    units = {u["id"]: u for u in manifest["source_units"]}
    gates = load(root / "mandatory-human-review-gates.json")
    available = {(r["source_id"], r["page"]): r for r in load(root / "availability-register.json")}
    keys = [(g["source_id"], g["page"]) for g in gates]
    if len(keys) != 15 or len(set(keys)) != 15 or set(keys) != set(OBSERVATIONS):
        raise ValueError("The 15 supplied page decisions do not match the R3C gates")
    if len(available) != 9 or set(available) != set(RELATION_LIMITS) - {("prusa-xl-de", 83)}:
        raise ValueError("Unexpected unresolved-region coverage")
    rows = []
    for gate in sorted(gates, key=lambda g: (g["source_id"], g["page"])):
        sid, page = gate["source_id"], gate["page"]
        unit = units[sid]
        mapping_path = local(root, unit["source_map"])
        mapping = load(mapping_path)
        normalized = local(root, unit["normalized_path"])
        text = normalized.read_text(encoding="utf-8")
        if digest(normalized) != unit["normalized_sha256"] or mapping["source_pdf_sha256"] != unit["original_sha256"]:
            raise ValueError("Wrong source/normalized identity")
        pg = next(p for p in mapping["pages"] if p["page"] == page)
        if digest(local(root, pg["render_path"])) != pg["render_sha256"]:
            raise ValueError("Wrong original page raster")
        spans = checked_ranges(gate["source_ranges"], mapping, text, page)
        category, language = OBSERVATIONS[sid, page]
        is_table = category == "table-no-visible-errors"
        records = [r for r in mapping["records"] if r["page"] == page]
        if is_table and (len(spans) != 1 or not spans[0]["id"].endswith(":r3b-table")):
            raise ValueError("Table observation must target the repaired table only")
        if category == "readable-image-text" and not any(r["kind"] == "figure" for r in records):
            raise ValueError("Readable-image observation has no mapped figure")
        region = available.get((sid, page))
        marker = None
        if region:
            if region["source_ranges"] != gate["source_ranges"]:
                raise ValueError("Availability/gate source ranges disagree")
            marker_record = next(r for r in records if r["kind"] == "derived-availability")
            marker = checked_ranges([{k: marker_record[k] for k in ("id", "page", "start", "end")}], mapping, text, page)[0]
            if (marker["start"], marker["end"]) != (region["start"], region["end"]):
                raise ValueError("Availability marker offsets disagree")
        # PDU identification's inherited gate maps images only. Add the literal
        # numbered labels as dependency context, without inventing their geometry.
        context = [r for r in records if sid == "prusa-xl-de" and page == 83 and r["kind"] == "step"]
        # Keep XL product-table footnote with its starred radio applicability.
        if sid == "prusa-xl-de" and page == 9:
            context += [r for r in records if r["id"] == "prusa-xl-de:p9:b16"]
        context_spans = checked_ranges([{k: r[k] for k in ("id", "page", "start", "end")} for r in context], mapping, text, page) if context else []
        rows.append(dict(
            id=f"R3D:{sid}:pdf-{page:03d}", source_id=sid, pdf_page=page,
            page_number_basis="1-based physical PDF page, not printed page label",
            normalized_path=unit["normalized_path"], source_pdf_path=unit["original_path"],
            original_sha256=unit["original_sha256"], normalized_sha256=unit["normalized_sha256"],
            revision=unit["revision"], document_language=unit["language"],
            source_map_sha256=digest(mapping_path), render_path=pg["render_path"], render_sha256=pg["render_sha256"],
            page_range={k: pg[k] for k in ("start", "end")}, component_ranges=spans,
            related_context_ranges=context_spans, availability_marker=marker,
            offset_basis="LF-normalized full-file Unicode characters; half-open [start,end); hashes use UTF-8",
            observation=dict(origin="human", supplied_by="requesting user; identity/credentials not provided",
                provenance="Direct observations in the current Task 3C.2A-R3D user instruction, section 4",
                review_timestamp=None, category=category, image_language_relation=language,
                original_quote="nie da się odczytać" if category == "cannot-read" else None,
                scope="Inspected PDF page/component only; no expert or whole-manual certification",
                statement=("No visible errors reported in the inspected table." if is_table else
                    "Image text is human-readable; its language relation is reported without transcription." if category == "readable-image-text" else
                    "Cannot be read; visual/textual unavailability or interpretation remains unresolved.")),
            reconciliation_origin="agent", human_response_recorded=True,
            table_observation_satisfied=is_table, normalized_crosscheck_by_user=False,
            technical_interpretation_resolved=False, independent_expert_certification=False,
            complete_page_certified=False, inherited_priority_cleared=False,
            inherited_availability_limit_retained=region is not None,
            text_only_visual_status="unavailable; no transcription or inferred interpretation" if not is_table else "not adjudicated outside table",
            support_restriction=RELATION_LIMITS.get((sid, page)),
            proposed_gate_disposition="table-observation-recorded-limited-scope" if is_table else "unavailability-recorded-scope-restriction-proposed",
            scope_approval="pending", admission_status="not-admitted", frozen=False,
        ))
    return rows


def policy():
    return dict(
        status="proposal-only-awaiting-user-approval", corpus_admitted=False, corpus_frozen=False,
        representation="Unchanged R3C-v2 source-once Markdown; all 24 full units retained",
        source_universe="After separate authorization, use the same complete 24-unit candidate universe in A/B/C; no query-dependent document/chunk filtering",
        evidence_rule="Only literal source text with verified product/version, table/condition/warning scope and exact original/normalized spans can support a claim. This is not a whitelist of gold evidence.",
        table_rule="Five human no-visible-errors observations supplement existing agent repairs and structural checks, for mapped tables only. Preserve labels, units, headers, shared values and footnotes. No user PDF-to-Markdown certification is asserted.",
        unavailable_rule="Images, links, derived placeholders and sidecars are not technical textual evidence. Readability to a person, including same-language screenshots, does not add text to the corpus.",
        relation_rule="Ten mapped regions retain relation/completeness restrictions. Literal neighboring text may be considered only with independently checked scope; do not infer graphical polarity, symbol mapping, screen state or PDU connection geometry.",
        open_risk_rule="All 418 original priorities stay open. Unreviewed High/Medium/Low text is unjudged, never automatically valid, irrelevant or unsupported. Before using any such span as evidence, perform targeted source/normalization/context QA without retrieval outputs; otherwise leave it unjudged or avoid the topic.",
        blocker_rule="Actual value/unit/negation/order/table/applicability corruption, ambiguous attribution or missing required conditions blocks the affected use until repaired in a new version or excluded by approved scope. Unavailable graphics alone do not block a limited textual benchmark.",
        procedure_rule="A complete procedure requires all actual textual prerequisites, warnings and exceptions, possibly across chunks/pages. A sidecar does not count as delivered evidence. Missing retrieved context is a system failure only when sufficient valid source text exists.",
        safety_rule="No complete electrical/PDU operation, symbol-based action or image-dependent reset/selftest may be certified from these observations. Qualified review is required only to expand into those uses; approved unavailability can close the bounded preparation task without reconstructing graphics.",
        unknown_rule="Insufficient review is not proof of corpus absence. Future unsupported judgments require whole-corpus search including translations/versions and separate review. Unexpected valid evidence requires versioned arm-blind adjudication across all arms.",
        exposure_rule="Preserved unresolved passages can still be retrieved. Report unavailable/unjudged context exposure separately; do not score it as established support or automatically as irrelevant, and do not alter production retrieval to hide it.",
        language_rule="Preserve publisher language, authentic PL/EN Git fallback and untranslated passages; record actual evidence language. Do not infer screenshot language beyond the user's same/different observation.",
        coverage_rule="Before question generation, approve restricted coverage and reviewer roles. Later confirm the six-manual answerability and multilingual/long-distance quotas without changing scope from retrieval results. Failure to meet quotas requires design review, not invented evidence.",
        approvals_required=["restricted corpus admission/scope", "versioned corpus freeze", "Task 3C.2B question/evidence preparation", "indexing or benchmark execution", "separately authorized maximum-36-call live pilot"],
        production_settings="Unchanged: legacy / cosine / K2 / top2 / 500 estimated tokens per scope",
        comparison_arms=["A: legacy/cosine/K2/top2/500", "B: legacy/cosine/K10/ranked_fill/1000", "C: structure-v2/cosine/K10/ranked_fill/1000"],
        full_review_not_required="Do not require reconstruction of all graphics or clearance of all 329 uninspected High pages for restricted scope; require review of any source spans and dependencies actually proposed for supported evidence.",
    )


def build(root, out):
    root, out = root.resolve(), out.resolve()
    repo = Path(__file__).resolve().parents[2]
    if out.exists() or out.is_relative_to(root) or out.is_relative_to(repo) or root.is_relative_to(out):
        raise ValueError("Use a NEW external sibling staging workspace, outside repository and R3C")
    before = integrity(root)
    rows = reconcile(root)
    risks = load(root / "unresolved-risk-register.json")
    if len(risks) != 418 or Counter(r["original_severity"] for r in risks) != Counter(High=388, Medium=10, Low=20):
        raise ValueError("Unexpected inherited risk queue")
    uninspected = [r for r in risks if r["original_severity"] == "High" and not r["r3b_inspected"]]
    if len(uninspected) != 329:
        raise ValueError("Uninspected High queue changed")
    out.mkdir(parents=True)
    for name in ("availability-register.json", "mandatory-human-review-gates.json", "unresolved-risk-register.json", "warning-applicability-reviewed.json"):
        shutil.copyfile(root / name, out / f"inherited-{name}")
    write(out / "human-review-decisions.json", dict(task=TASK, record_date="2026-11-12", review_timestamp=None,
        notice="Record date is packaging date, not a fabricated human review time. Human observations and agent reconciliations have separate origins.", decisions=rows))
    with (out / "page-reconciliation.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["id", "source_id", "pdf_page", "observation", "image_language_relation", "component_ids", "disposition", "restriction", "admission_status"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(id=r["id"], source_id=r["source_id"], pdf_page=r["pdf_page"], observation=r["observation"]["category"],
                image_language_relation=r["observation"]["image_language_relation"], component_ids=";".join(s["id"] for s in r["component_ranges"]),
                disposition=r["proposed_gate_disposition"], restriction=r["support_restriction"], admission_status=r["admission_status"]))
    write(out / "restricted-regions.json", dict(status="proposed-not-approved", inherited_region_count=9, additional_gate_only_region_count=1,
        regions=[{k: r[k] for k in ("id", "source_id", "pdf_page", "component_ranges", "related_context_ranges", "availability_marker", "support_restriction", "normalized_sha256")} for r in rows if r["support_restriction"]]))
    write(out / "admission-policy-proposal.json", policy())
    write(out / "uninspected-high.json", uninspected)
    summary = dict(task=TASK, status="recommendation-prepared-not-admitted-not-frozen", r3c_root=str(root), r3d_root=str(out),
        integrity_before=before, observations=15, table_observations=5, readable_nonextracted_image_observations=4, cannot_read_observations=6,
        inherited_unresolved_regions=9, proposed_restricted_regions=10, human_responses_recorded=15, expert_certifications=0,
        fully_semantically_cleared_pages=0, inherited_severity_counts=dict(Critical=0, High=388, Medium=10, Low=20),
        uninspected_high=329, uninspected_medium=9, uninspected_low=20,
        freeze_ready=False, task_3c2b_authorized=False, automatic_admission=False,
        readiness="Ready for restricted-scope approval review; no full semantic certification. Subsequent labeling needs authorization and targeted evidence QA.",
        outstanding_requirements=[
            "Approve explicit unavailability/relation limits on ten regions, including the separate XL PDF 83 gate; no repeat of the 15 observations is needed.",
            "Approve retention of all open priorities as unjudged; preserve the exact 329 High page queue and all Medium/Low flags.",
            "Choose domain/bilingual/second reviewers and scope for later Task 3C.2B; verify all intended evidence spans and warning/condition dependencies before labels are accepted.",
            "Do not extend five table observations to other components. XL PDF 81 product table is not one of the five user-confirmed tables; its use requires targeted QA.",
            "For complete sensor/reset, graphical polarity, MMU symbols or PDU identification/operation: qualified targeted review or retain the approved unavailable status; do not reconstruct every graphic.",
            "Before freeze, recheck source/overlay hashes, revisions/licenses, mixed-language provenance, exclusions and reviewer roles; create a separate approved freeze manifest.",
            "Later verify all benchmark design quotas, review/label provenance and pilot/sealed separation before dataset seal/indexing; no question/gold artifacts exist in R3D.",
        ])
    after = integrity(root)
    if before != after:
        raise ValueError("R3C or historical inputs changed during packaging")
    summary["integrity_after"] = after
    write(out / "readiness.json", summary)
    (out / "README.md").write_text(
        "# R3D human-review observations and restricted admission proposal\n\n"
        "This is an external metadata overlay referencing unchanged R3C-v2, not a new normalized corpus, admission or freeze. "
        "The original PDFs/Markdown/maps remain in R3C; no visual transcription or interpretation was added.\n\n"
        "`human-review-decisions.json` records 15 direct human page/component observations and separate agent reconciliation. "
        "Physical PDF pages are 1-based; ranges use LF-normalized full-file Unicode characters [start,end), hashed as UTF-8. "
        "`page-reconciliation.csv` summarizes all 15 gates. `restricted-regions.json` retains nine limits plus XL PDF 83 identification. "
        "`inherited-*` files are byte-identical, including all 418 unchanged priorities. `uninspected-high.json` preserves all 329 pages.\n\n"
        "Five table observations report no visible errors; they are not expert or PDF-to-Markdown certification. Four readable images remain unavailable to text-only RAG. "
        "Six cannot-read observations leave visual/technical relations unresolved. All scope approvals remain pending.\n\n"
        "`admission-policy-proposal.json` and `readiness.json` define the restricted proposal and outstanding requirements. "
        "No full 329-page review is required for restricted scope, but any later evidence use requires targeted source/context QA; unknown is unjudged. "
        "Whole documents remain candidates for later equally scoped A/B/C retrieval. Sidecars and derived notes are not technical evidence.\n\n"
        "Reproduce with `python -B tools/corpus/review_prusa_r3d.py --r3c <pinned-R3C-v2> --output <NEW-external-path>`. "
        "Verify with the same command plus `--verify --expected-inventory-sha <report-anchor>`. "
        "Review observations are supplied input; replaying the tool does not independently reproduce human judgment. "
        "Corpus freezing, questions, labels, indexes, benchmarks and live inference need separate approval.\n",
        encoding="utf-8")
    shutil.copyfile(Path(__file__), out / "review_prusa_r3d.py")
    write(out / "r3d-integrity-inventory.json", dict(algorithm="SHA-256", files=[dict(path=p.relative_to(out).as_posix(), sha256=digest(p), bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file()]))
    return summary


def verify(root, out, expected=None):
    inventory = out / "r3d-integrity-inventory.json"
    if expected and digest(inventory) != expected:
        raise ValueError("R3D inventory trust anchor mismatch")
    files = load(inventory)["files"]
    if {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} != {f["path"] for f in files} | {inventory.name}:
        raise ValueError("Unexpected or missing R3D files")
    for f in files:
        p = local(out, f["path"])
        if not p.is_file() or digest(p) != f["sha256"] or p.stat().st_size != f["bytes"]:
            raise ValueError("R3D output integrity mismatch: " + f["path"])
    original = load(out / "readiness.json")
    if integrity(root) != original["integrity_before"] or original["integrity_before"] != original["integrity_after"]:
        raise ValueError("Input chain changed")
    if reconcile(root) != load(out / "human-review-decisions.json")["decisions"]:
        raise ValueError("Decision reconciliation changed")
    return dict(verified=True, r3d_files=len(files), inventory_sha256=digest(inventory), source_snapshot_unchanged=True,
        observations=15, inherited_risks=418, uninspected_high=329, admitted=False, frozen=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r3c", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-inventory-sha")
    args = parser.parse_args()
    result = verify(args.r3c, args.output, args.expected_inventory_sha) if args.verify else build(args.r3c, args.output)
    print(json.dumps(result, indent=2))
