"""Prepare agent-draft pilot artifacts from frozen sources and external authoring data.

Standard library only. No production imports, chunking, embeddings, retrieval,
index creation, inference or network access. Source-bearing authoring data and
outputs must remain outside the repository and the immutable source snapshot.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil

MANIFEST_SHA = "5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19"
RECEIPT_SHA = "cc46d666407c74beec2bf0832bfcf4a9f62117db608f53c2ef339e5e28d7759c"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), "Path escapes workspace")
    return path


def verify_corpus(root):
    require(digest(root / "freeze-manifest.json") == MANIFEST_SHA, "Source freeze manifest changed")
    require(digest(root / "freeze-receipt.json") == RECEIPT_SHA, "Source freeze receipt changed")
    plan, receipt = load(root / "freeze-manifest.json"), load(root / "freeze-receipt.json")
    require(receipt["status"] == "frozen-restricted-text-only" and receipt["plan_sha256"] == MANIFEST_SHA, "Invalid freeze receipt")
    require(digest(root / "freeze-approval.json") == receipt["approval_sha256"], "Freeze approval changed")
    require(len(plan["copy_entries"]) == receipt["copied_files"] == 774, "Wrong source freeze count")
    for entry in plan["copy_entries"]:
        path = local(root, entry["destination"])
        require(path.is_file() and path.stat().st_size == entry["bytes"] and digest(path) == entry["sha256"], "Frozen artifact changed: " + entry["destination"])
    expected = {e["destination"] for e in plan["copy_entries"]} | {"freeze-manifest.json", "freeze-approval.json", "freeze-receipt.json"}
    require({p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == expected, "Source freeze file set changed")
    return dict(verified=True, copy_files=774, total_files=777, manifest_sha256=MANIFEST_SHA, receipt_sha256=RECEIPT_SHA)


def plain_markdown(value):
    # Remove inline link destinations while retaining labels and nested/escaped
    # parentheses. This is used for fidelity comparison, never as retrieval text.
    result, i = [], 0
    while i < len(value):
        if value[i] == "[":
            j = value.find("](", i)
            if j >= 0:
                depth, k = 1, j + 2
                while k < len(value) and depth:
                    if value[k] == "\\":
                        k += 2
                        continue
                    depth += (value[k] == "(") - (value[k] == ")")
                    k += 1
                if depth == 0:
                    result.append(value[i + 1:j]); i = k
                    continue
        result.append(value[i]); i += 1
    text = "".join(result).replace("`", "").replace("**", "").replace("\\(", "(").replace("\\)", ")")
    return " ".join(html.unescape(text).split())


class OriginalHTML(HTMLParser):
    """Capture original block text and raw HTML ranges without external parsers."""
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.raw, self.stack, self.blocks = text, [], []
        self.starts = [0]
        self.starts += [m.end() for m in re.finditer("\n", text)]
        self.feed(text)

    def position(self):
        line, column = self.getpos()
        return self.starts[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "img", "meta", "link", "hr", "input", "wbr", "source", "area"}:
            self.handle_data(" ")
            return
        self.stack.append(dict(tag=tag, attrs=dict(attrs), start=self.position(), text=[]))

    def handle_data(self, data):
        for item in self.stack:
            item["text"].append(data)

    def handle_endtag(self, tag):
        match = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]["tag"] == tag), None)
        if match is None:
            return
        end = self.raw.find(">", self.position()) + 1
        for item in self.stack[match:]:
            if item["tag"] in {"p", "li", "dd"}:
                self.blocks.append(dict(tag=item["tag"], start=item["start"], end=end, text=" ".join("".join(item["text"]).split())))
        del self.stack[match:]


def paragraph_range(text, begins):
    matches = [m.start() for m in re.finditer(re.escape(begins), text)]
    require(len(matches) == 1, "Paragraph selector is not unique: " + begins)
    start = matches[0]
    end = text.find("\n\n", start)
    return start, len(text) if end < 0 else end


def make_span(root, spec, unit):
    corpus = root / "corpus"
    text = (corpus / unit["normalized_path"]).read_text(encoding="utf-8")
    mapping = load(corpus / unit["source_map"])
    original = corpus / unit["original_path"]
    qa = dict(origin="agent", status="agent_targeted_qa_passed", human_reviewed=False, reviewer_identity=None, review_time=None)
    location = dict(section=spec["section"], original_path=unit["original_path"], canonical_url=unit["canonical_url"])
    if "block_id" in spec:
        record = next(r for r in mapping["records"] if r["id"] == spec["block_id"])
        require(record.get("contains_publisher_text") and not record.get("derived_segments"), "Derived/visual material cannot be evidence")
        start, end = record["start"], record["end"]
        if spec.get("table_prefix_rows"):
            cell = next(c for c in record["cells"] if c["row"] == spec["table_prefix_rows"] + 1 and c["column"] == 0)
            end = text.rfind("\n", start, cell["start"]) + 1
        location.update(pdf_page=record["page"], block_id=record["id"], source_line_ids=record["source_lines"])
        page = next(p for p in mapping["pages"] if p["page"] == record["page"])
        location.update(render_path=page["render_path"], render_sha256=page["render_sha256"])
        require(spec.get("visual_qa_note"), "Prusa evidence needs explicit targeted visual QA provenance")
        qa.update(method="Agent visual comparison of full frozen original-page raster and selected normalized block/table/callout; not whole-page clearance", observation=spec["visual_qa_note"])
        risk = next(r for r in load(corpus / "unresolved-risk-register.json") if r["source_id"] == unit["id"] and r["page"] == record["page"])
        qa.update(inherited_page_severity=risk["original_severity"], inherited_r3b_inspected=risk["r3b_inspected"], original_priority_unchanged=True)
    elif "source_lines" in spec:
        a, z = spec["source_lines"]
        records = [r for r in mapping["records"] if a <= r["source_line"] <= z]
        require(records, "No original line ownership")
        start = unit["body_offset"] + min(r["start"] for r in records)
        end = unit["body_offset"] + max(r["end"] for r in records)
        lines = original.read_text(encoding="utf-8").splitlines()
        raw = "\n".join(lines[a - 1:z])
        # Allow only known code-fence presentation changes in these selections.
        normalize = lambda s: " ".join(line.strip() for line in s.splitlines() if line.strip() not in {"----", "[source,console]", "```console", "```"})
        require(normalize(text[start:end]) == normalize(raw), "Selected AsciiDoc/Markdown text differs")
        location.update(source_line_from=a, source_line_through=z, pinned_repository_path=unit["source_path"])
        qa.update(method="Exact selected AsciiDoc-line / mapped Markdown comparison, allowing only code-fence syntax and whitespace", original_excerpt=raw)
    else:
        start, end = paragraph_range(text, spec["paragraph_begins"])
        raw = original.read_text(encoding="utf-8")
        require(any(a["id"] == spec["anchor"] for a in mapping["records"]["anchors"]), "Original section anchor absent from frozen map")
        require(re.search(r'\bid=[\"\']' + re.escape(spec["anchor"]) + r'[\"\']', raw), "Original HTML anchor missing")
        visible = plain_markdown(text[start:end])
        candidates = [b for b in OriginalHTML(raw).blocks if b["text"] == visible]
        # Numbered/list markers are presentation, not part of the original <p>.
        if not candidates:
            visible = re.sub(r"^(?:\d+\.|\*)\s+", "", visible)
            candidates = [b for b in OriginalHTML(raw).blocks if b["text"] == visible]
        require(candidates, "Original HTML/normalized paragraph comparison failed: " + spec["id"])
        block = min(candidates, key=lambda b: b["end"] - b["start"])
        location.update(html_anchor=spec["anchor"], original_character_start=block["start"], original_character_end=block["end"], original_excerpt_sha256=hashlib.sha256(raw[block["start"]:block["end"]].encode()).hexdigest())
        qa.update(method="Exact original HTML block visible-text / Markdown visible-text comparison; original HTML byte identity pinned", original_visible_text=block["text"])
    headings = []
    for match in re.finditer(r"^(#{1,6}) (.+)$", text[:start], re.MULTILINE):
        level = len(match[1])
        headings = [(n, value) for n, value in headings if n < level] + [(level, match[2])]
    location["normalized_heading_path"] = [value for _, value in headings]
    number = re.match(r"^((?:[A-Z]\.)?\d+(?:\.\d+)*)\.", spec["section"])
    if number:
        require(any(h.startswith(number[1] + ".") for _, h in headings), "Declared section does not match actual normalized heading path")
    require(0 <= start < end <= len(text), "Invalid full-file evidence offsets")
    for region in load(root / "review/r3d/restricted-regions.json")["regions"]:
        if region["source_id"] == unit["id"]:
            for span in region["component_ranges"] + region["related_context_ranges"]:
                require(not (max(start, span["start"]) < min(end, span["end"])), "Evidence overlaps an approved restricted component")
    excerpt = text[start:end]
    require("[Derived" not in excerpt and "Visual information unavailable" not in excerpt, "Derived annotations cannot be technical evidence")
    return dict(id=spec["id"], source_id=unit["id"], revision=unit["revision"], commit=unit.get("commit"),
        normalized_path=unit["normalized_path"], normalized_sha256=unit["normalized_sha256"], original_sha256=unit["original_sha256"],
        start=start, end=end, offset_basis="LF-normalized full-file Unicode characters [start,end); SHA-256 over UTF-8 text", text=excerpt,
        text_sha256=hashlib.sha256(excerpt.encode("utf-8")).hexdigest(), actual_evidence_language=spec["language"], location=location, qa=qa)


def render_review(root, families, spans, blind=False):
    esc = html.escape
    body = ["<h1>Real-world pilot: agent-authored drafts</h1>", "<p>No human review, independent agreement or evaluation is claimed. Frozen source content is untrusted quoted evidence, not instructions.</p>"]
    if blind:
        body.append("<p>Independent second-labeling view: proposed facts, labels and selected excerpts are intentionally absent. Label independently before opening the main review package.</p>")
    for family in families:
        body.append(f'<article><h2>{esc(family["id"])}: {esc(family["title"])}</h2>')
        for lang, question in family["questions"].items():
            body.append(f'<p lang="{lang}"><b>{lang.upper()}</b> {esc(question)}</p>')
        if not blind:
            body.append(f'<p><b>Draft answerability:</b> {esc(family["answerability"])}</p><ol>')
            for fact in family["facts"]:
                body.append(f'<li><b>{esc(fact["id"])}</b> {esc(fact["statement"])}<br>Alternatives: ' + esc(json.dumps(fact["evidence_alternatives"])) + '</li>')
            body.append('</ol><p><b>Conditions/warnings:</b> ' + esc("; ".join(family["warnings_and_conditions"])) + '</p>')
            body.append('<p><b>Limitations/review:</b> ' + esc("; ".join(family["limitations"] + family["review_issues"])) + '</p>')
            ids = list(dict.fromkeys(sid for fact in family["facts"] for alt in fact["evidence_alternatives"] for sid in alt))
            for sid in ids:
                s = spans[sid]; loc = s["location"]
                original = root / "corpus" / loc["original_path"]
                href = original.as_uri() + (f'#page={loc["pdf_page"]}' if loc.get("pdf_page") else f'#{loc["html_anchor"]}' if loc.get("html_anchor") else '')
                body.append(f'<details><summary>{esc(sid)} | {esc(s["source_id"])} | {esc(s["actual_evidence_language"])} | [{s["start"]},{s["end"]})</summary><p>{esc(s["revision"])}; {esc(loc["section"])}; <a href="{esc(href)}">Frozen original</a></p>')
                if loc.get("render_path"):
                    body.append(f'<p>Physical PDF page {loc["pdf_page"]}; <a href="{esc((root/"corpus"/loc["render_path"]).as_uri())}">Original full-page raster</a></p>')
                body.append('<pre>' + esc(s["text"]) + '</pre><p>Agent QA: ' + esc(s["qa"]["method"]) + '; ' + esc(s["qa"].get("observation", "Exact selected-source comparison passed")) + '</p></details>')
        body.append('</article>')
    if blind:
        body.append('<h2>All 24 frozen source units</h2><ul>')
        for unit in load(root / "corpus/source-manifest.json")["source_units"]:
            body.append(f'<li><a href="{esc((root/"corpus"/unit["normalized_path"]).as_uri())}">{esc(unit["id"])}</a> | {esc(unit["revision"])}</li>')
        body.append('</ul>')
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pilot draft review</title><style>body{max-width:1000px;margin:32px auto;padding:0 20px;font:16px/1.55 system-ui;color:#182334}article{border-top:2px solid #ccd7e5;margin:30px 0}details{margin:12px 0;padding:12px;background:#f2f5f9}summary{cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 Consolas,monospace}a{color:#1859a8}</style>' + ''.join(body) + '</html>'


def build(root, authoring, out):
    root, authoring, out = [p.resolve() for p in (root, authoring, out)]
    repo = Path(__file__).resolve().parents[2]
    require(not out.exists() and not out.is_relative_to(root) and not out.is_relative_to(repo), "Use a NEW external pilot output")
    require(not authoring.is_relative_to(repo) and not authoring.is_relative_to(root), "Keep source-bearing authoring data outside Git and frozen corpus")
    integrity = verify_corpus(root)
    data = load(authoring); families = data["families"]
    require(len(families) == 4 and Counter(f["category"] for f in families) == Counter({"single_document":1,"multi_section":1,"multi_document":1,"insufficiently_specified":1}), "Pilot category/count mismatch")
    require(all(set(f["questions"]) == {"en", "pl", "de"} for f in families), "Each family needs equivalent EN/PL/DE variants")
    units = {u["id"]:u for u in load(root / "corpus/source-manifest.json")["source_units"]}
    spans = {s["id"]:make_span(root, s, units[s["source_id"]]) for s in data["spans"]}
    require(len(spans) == len(data["spans"]), "Duplicate evidence span ID")
    questions, labels = [], []
    for family in families:
        for fact in family["facts"]:
            require(fact["evidence_alternatives"] and all(alt and all(s in spans for s in alt) for alt in fact["evidence_alternatives"]), "Missing fact evidence alternative")
        if family["category"] != "insufficiently_specified":
            require(family["minimal_sufficient_evidence_sets"], "Answerable family lacks sufficient evidence sets")
            for evidence_set in family["minimal_sufficient_evidence_sets"]:
                require(all(any(set(alt) <= set(evidence_set) for alt in f["evidence_alternatives"]) for f in family["facts"]), "Sufficient set does not cover every required fact")
                docs = {spans[s]["source_id"] for s in evidence_set}
                require(len(docs) == 1 if family["category"] == "single_document" else len(docs) >= 2 if family["category"] == "multi_document" else True, "Evidence set violates document requirement")
        for lang, text in family["questions"].items():
            qid = family["id"] + "-" + lang
            questions.append(dict(id=qid, family_id=family["id"], language=lang, text=text, split="pilot", origin="agent", status="agent_draft", human_reviewed=False))
            labels.append(dict(question_id=qid, family_id=family["id"], origin="agent", status="agent_draft", author="Codex drafting agent", human_reviewers=[], review_time=None,
                target=family["target"], answerability=family["answerability"], positive_evidence_recall_applicable=family["category"] != "insufficiently_specified",
                required_answer_facts=family["facts"], minimal_sufficient_evidence_sets=family["minimal_sufficient_evidence_sets"],
                warnings_and_conditions=family["warnings_and_conditions"], expected_limitations=family["limitations"], unresolved_review_issues=family["review_issues"],
                evidence_languages=sorted({spans[s]["actual_evidence_language"] for fact in family["facts"] for alt in fact["evidence_alternatives"] for s in alt}),
                cross_language_required="not adjudicated; do not infer solely from document language", source_freeze_manifest_sha256=MANIFEST_SHA))
    scans = []
    for u in units.values():
        text = (root / "corpus" / u["normalized_path"]).read_text(encoding="utf-8")
        hits = []
        for term in data["corpus_scan_terms"]:
            hits += [dict(term=term, start=m.start(), end=m.end()) for m in re.finditer(re.escape(term), text, re.IGNORECASE)]
        scans.append(dict(source_id=u["id"], normalized_sha256=u["normalized_sha256"], inspected=True, literal_term_hits=hits, relevance_status="unjudged except explicit draft spans; not a negative relevance label"))
    out.mkdir(parents=True)
    shutil.copyfile(authoring, out / "authoring-plan.json")
    for name, value in (("families.json", families), ("questions.json", questions), ("draft-labels.json", labels), ("evidence-spans.json", list(spans.values()))):
        write(out / name, value)
    write(out / "targeted-source-qa.json", dict(origin="agent", human_reviewed=False, retrieval_outputs_seen=False, selected_spans=len(spans), records=[dict(span_id=s["id"], source_id=s["source_id"], qa=s["qa"]) for s in spans.values()], restricted_overlaps=0, priorities_cleared=0, remaining_uninspected_high=329))
    write(out / "corpus-wide-inspection.json", dict(method="Literal source inspection only; no ranked retrieval, embeddings or benchmark", records=scans, unsupported_disposition="Version ambiguity in the question, not asserted corpus absence", absence_assertion=False, human_whole_corpus_adjudication="pending", requirements=data["unsupported_review_requirements"], alternatives_exhaustive=False))
    write(out / "review-requirements.json", dict(status="human-review-pending", reviewers=[], independently_reviewed_labels=0, issues=data["review_requirements"], independently_second_label_families=["P02", "P04"], selection_basis="Preselected without retrieval outputs: all unsupported/conflict cases plus ceil(25% of three answerable pilot families)=one; P02 selected", bilingual_variants_to_review=12, main_package="review.html", blind_second_label_package="blind-second-review.html"))
    write(out / "split-reservation.json", dict(pilot_families=4, pilot_questions=12, pilot_answerable_questions=9, pilot_insufficiently_specified_questions=3, sealed_families_reserved=16, sealed_questions_reserved=48, sealed_questions_authored=0, sealed_answerable_families_reserved=13, sealed_unsupported_families_reserved=3, remaining_category_counts=dict(single_document=5,multi_section=5,multi_document=3,unsupported=3), topic_quarantine=data["pilot_topic_quarantine"], sealed_policy="Do not reuse connected evidence topics, translations, repeated passages or version siblings across pilot/sealed. Check six-manual answerable coverage and all global quotas before seal; no sealed questions generated here."))
    (out / "review.html").write_text(render_review(root, families, spans), encoding="utf-8")
    (out / "blind-second-review.html").write_text(render_review(root, families, spans, blind=True), encoding="utf-8")
    write(out / "provenance.json", dict(task="3C.2B.1", dataset_version=out.name, parent_dataset_manifest_sha256=data.get("parent_dataset_manifest_sha256"), version_change_reason=data.get("version_change_reason"), created_date="2026-11-12", origin="agent", status="agent-draft-content-frozen-human-review-pending", human_reviewers=[], independent_human_agreement=None, source_root=str(root), source_integrity=integrity, authoring_sha256=digest(authoring), generator_sha256=digest(Path(__file__)), question_origin="agent-authored; no human-supplied task provenance invented", targeted_qa_origin="agent", retrieval_indexing_embeddings_inference=False, scoring_authorized=False, redistribution="Local review only; source and license restrictions remain applicable"))
    shutil.copyfile(Path(__file__), out / "prepare_real_world_pilot.py")
    (out / "README.md").write_text("# Pilot dataset: agent drafts, content frozen for review\n\nOpen review.html for questions, facts and exact frozen excerpts. Use blind-second-review.html before exposing independent second reviewers to proposed labels. No human-reviewed labels or evaluation readiness is claimed.\n\nquestions.json is the question-only artifact; draft-labels.json and evidence-spans.json are curator/evaluator-only. Never ingest this workspace, excerpts, review pages, provenance or labels as retrieval documents. Only the 24 original frozen corpus documents may enter a later authorized index.\n\nAll normalized offsets are full-file Unicode [start,end), including YAML; software source maps use body offsets internally and are explicitly rebased. Text hashes use UTF-8. Prusa source inspection is component-scoped agent QA and never clears an inherited page flag.\n\nThe integrity manifest freezes this draft version, not human-approved gold. Any question, translation, label, alternative or QA correction requires a new dataset version with parent hash and renewed review before scoring. No sealed questions exist. No retrieval tuning or execution is authorized.\n", encoding="utf-8")
    require(verify_corpus(root) == integrity, "Frozen source corpus changed during authoring")
    write(out / "pilot-integrity-manifest.json", dict(schema_version=1, status="agent-draft-content-frozen-human-review-pending", source_manifest_sha256=MANIFEST_SHA, scoring_authorized=False, families=4, questions=12, labels=12, files=[dict(path=p.name, bytes=p.stat().st_size, sha256=digest(p)) for p in sorted(out.iterdir()) if p.is_file()], self_excluded=True))
    return dict(output=str(out), families=4, questions=12, spans=len(spans), integrity_manifest_sha256=digest(out / "pilot-integrity-manifest.json"), human_reviewed=False, scoring_authorized=False)


def verify(root, out, expected):
    require(expected and digest(out / "pilot-integrity-manifest.json") == expected, "Pilot trust anchor mismatch")
    verify_corpus(root)
    inventory = load(out / "pilot-integrity-manifest.json")
    require({p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} == {f["path"] for f in inventory["files"]} | {"pilot-integrity-manifest.json"}, "Pilot file set changed")
    for f in inventory["files"]:
        p = local(out, f["path"])
        require(p.stat().st_size == f["bytes"] and digest(p) == f["sha256"], "Pilot artifact changed: " + f["path"])
    for s in load(out / "evidence-spans.json"):
        p = root / "corpus" / s["normalized_path"]
        text = p.read_text(encoding="utf-8")[s["start"]:s["end"]]
        require(text == s["text"] and hashlib.sha256(text.encode()).hexdigest() == s["text_sha256"], "Evidence source span changed")
    return dict(verified=True, families=4, questions=12, source_unchanged=True, human_reviewed=False, scoring_authorized=False, integrity_manifest_sha256=expected)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authoring", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--expected-inventory-sha")
    args = parser.parse_args()
    if args.verify:
        result = verify(args.corpus, args.output, args.expected_inventory_sha)
    else:
        if not args.authoring:
            parser.error("--authoring external plan is required")
        result = build(args.corpus, args.authoring, args.output)
    print(json.dumps(result, indent=2))
