---
type: report
title: Prusa PDF extraction remediation - Task 3C.2A-R1
date: 2026-11-11
status: sample-method-verified-full-conversion-not-authorized
scope: eight sample pages, two supplementary table probes, and structural screening of 418 pages
---

# R1 result and recommendation

The geometry-based method repairs the tested menu hierarchy, section/callout associations, source legends, numbered procedures and two representative tables without OCR or generated image descriptions. **It is not yet safe as an unattended, admission-ready conversion for all six manuals.** Shared notes/warnings can still disappear from later chunks; raster-only spatial meaning and complex tables require review. R2 may use it as a candidate generator with explicit review gates, after user approval. No corpus freeze or Task 3C.2B work occurred.

Accepted corpus: `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111`.

Separate R1 workspace: `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r1`.

The original PDFs, 24 accepted Markdown files, mixed PL/EN decision and PostgreSQL WAL commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48` remain unchanged. All 289 accepted inventory entries were checked before/after. Copies of the accepted manifest and inventory are preserved in R1 `baseline-snapshot/`; neither original was overwritten. No new files were added inside the accepted corpus.

## Method and alternatives examined

The existing [acquisition report](STAGE_2B2_REAL_WORLD_CORPUS_ACQUISITION_20261111.md), extraction and normalization scripts, geometry cache, and both LAEW chunkers were reviewed. The old main Markdown path used pypdf plain text and recovered only some numbered headings. Its useful pdfplumber geometry was stored separately rather than used for structure.

The R1 implementation uses the already installed **pdfplumber 0.11.9 / pdfminer character, font, rectangle and image objects**, running under bundled Python **3.12.14**. Existing pypdf/pdfplumber extraction differences are reused as audit signals. Poppler **26.07.0** renders supply the visual reference; new renders were needed only for the two table probes. No packages or models were installed.

| Method | Assessment |
|---|---|
| Existing pypdf plain/layout extraction | Useful unchanged baseline and independent text comparison; plain text alone loses hierarchy, table relationships and callout boundaries. |
| pdfplumber geometry and ruled-table extraction | Selected: available locally, exposes the required glyph coordinates, fonts, colors, images and cell geometry. Explicitly rejects ambiguous/merged cells. |
| PyMuPDF blocks/words and reading-order facilities | Documentation reviewed; not installed or experimentally benchmarked. No unsupported claim that it would automatically solve the remaining visual semantics. |
| OCR | Not used. The tested structure already exists as PDF text/vector objects; raster-only controls remain unresolved. |

These capabilities and limitations are consistent with the primary documentation for [pdfplumber](https://github.com/jsvine/pdfplumber), [PyMuPDF text extraction](https://pymupdf.readthedocs.io/en/latest/recipes-text.html), and [pypdf extraction/layout](https://pypdf.readthedocs.io/en/stable/user/extract-text.html). Documentation review did not change installed tool versions.

Conversion rules:

1. Read lines in page coordinates and preserve glyphs. Recover headings from actual numbering, relative font size and font family; recover emphasis from the observed font runs. Reflow physical line wraps without paraphrasing or translating prose.
2. Turn explicit square-bullet indentation into complete menu paths. Ancestor labels and their conditions repeat verbatim, making each item self-contained. This is a structural representation of the original tree, not additional technical advice.
3. Group text geometrically contained in callout rectangles. Associate each with the preceding numbered source section; retain original position relative to instructions. Literal `!`/`i` markers are recognized only through exact image-stream hashes of visually reviewed icons. **Color alone does not determine warning versus information.** Unknown icons remain unclassified.
4. Preserve short ruled tables as Markdown matrices. Serialize long cells under explicit original row/product and column labels so a risk is not detached from its product. Preserve the original cell matrix in the sidecar. Merged/ambiguous cells are flagged rather than guessed.
5. Recover preceding-page section context from existing source heading records when a sample begins mid-section. Mark continued context explicitly; retain the originating page in object metadata. This does not certify cross-page callouts/tables generally.
6. Keep original figure pixels, existing captions, source page links/coordinates and local crops. Mark both figures and explicit image-dependent prose as **visual verification required**. No raster UI labels, arrow endpoints or alignment instructions were invented.

Every source text line is assigned once to a structural block, apart from separately recorded page-number footers. Source maps include PDF bounding boxes, section scope and Markdown offsets. Glyph checks ignore whitespace/Markdown emphasis; table checks preserve each source cell's content. Structural annotations and repeated ancestors are distinguished from publisher text.

## Original eight pages: before versus after

The comparison viewer is R1 `review.html`: original rendered PDF, exact accepted Markdown and exact R1 Markdown. `diffs/`, `objects/` and `maps/` contain the corresponding differences and provenance. All eight originals were visually inspected; the converted text was compared against those renders. A visual sample review is not a certification of unsampled pages.

| Source / page | Before | R1 repair | Remaining limitation |
|---|---|---|---|
| MK3S PL / 35 | Flattened LCD menu; conditions and values lack explicit ancestry. | **44 menu items**, three indentation levels; **34 previously absent explicit parent paths** recovered. Conditions remain on their branches, and temperatures are unchanged. All 44 paths survive whole in at least one chunk in both strategies. | General page note is absent in three later menu chunks per strategy. No unit or interpretation was added to source values such as `215/60`. |
| XL DE / 23 | Two warnings are plain paragraphs; unnumbered installation heading and graphic dependency are not represented reliably. | Two separate `!` red warning blocks scoped to **4.3**, before the installation subheading. Bold source restrictions retained. Alignment photo preserved; following image-dependent instruction explicitly flagged. | Orange alignment marks and spatial placement still require the original image. Two procedural chunks per strategy lack the complete preceding warning set. |
| MK4S EN / 42 | List text retained, screenshot absent from normalized text; weak heading structure. | Correct section heading, all **14 numbered legend entries** in order, original figure and unresolved-visual marker. | UI positions/pixels are not transcribed. Existing explanations are preserved, not extended. |
| MK4 DE / 43 | Same screenshot/legend limitation. | Correct heading and all **14 original German legend entries**; figure preserved. | Raster UI labels and locations remain visual-review-only. |
| MINI PL / 31 | Screenshot/caption linkage and continued section context are weak. | **12 numbered legend entries**, caption, continued **7.4** context from page 30, and separate **7.5** heading. | English raster UI content is not translated or invented. |
| MMU3 EN / 22 | Procedure boundaries and final orange note are flattened. | Distinct **2.5 / 2.6** headings, two separate **1-6** step sequences; final `i` note is associated with **2.6**, after its six steps. | This verifies this page's scope, not arbitrary cross-page note propagation. |
| XL DE / 7 | Empty page represented by provenance comment. | Confirmed zero text/image/drawing objects, matching the blank render; no missing-text alarm or invented content. | The review sample has metadata comments only; it is not an independent corpus document. |
| XL DE / 46 | Screenshot absent; heading/legend structure weak. | Correct heading and all **14 numbered legend entries**, original figure and explicit visual limitation. | Spatial callout relationships remain dependent on the raster source. |

Two additional source pages were selected **after** the 418-page audit because the eight original samples do not include a representative ruled parameter table:

- **MMU3 EN page 40:** source `Color / Unloaded / Loaded` matrix preserved, including all six data rows and surrounding `mm3` unit statements. No table values were inferred from the photograph.
- **MINI PL page 44:** three product rows and their two original usage/risk columns serialized into six labelled cells. `90%+`, `98A`, restrictions and source bullet content are retained. Four orange boxes are correctly distinguished as **two `!` warnings and two `i` notes**, scoped to continued section **9.1** from page 42. This exposed and corrected the unsafe initial assumption that every orange box was informational.

Only these **10 pages** have R1 Markdown; no complete handbook was regenerated.

## Chunking and regressions

The actual existing `KnowledgeBase._load_file(..., embed=False)` was used without constructing a store or embedding service. Size **1,000**, legacy overlap **200**, and existing structure-v2 context rules were unchanged. Every R1 source span partitions the sample exactly under structure-v2. All menu paths and individual callout bodies survive intact in a chunk. All checked non-table source lines and all table cells are retained.

| Page | Legacy chunks before -> after | Structure-v2 before -> after |
|---|---:|---:|
| MK3S PL 35 | 2 -> 5 | 2 -> 5 |
| XL DE 23 | 2 -> 4 | 2 -> 4 |
| MK4S EN 42 | 1 -> 2 | 1 -> 2 |
| MK4 DE 43 | 1 -> 2 | 1 -> 2 |
| MINI PL 31 | 3 -> 4 | 3 -> 4 |
| MMU3 EN 22 | 5 -> 5 | 4 -> 5 |
| XL DE 7 | 1 -> 1 | 1 -> 1 |
| XL DE 46 | 1 -> 2 | 1 -> 2 |
| MMU3 EN 40, table probe | 2 -> 3 | 2 -> 3 |
| MINI PL 44, table probe | 4 -> 10 | 4 -> 10 |

These are page-sample parser counts, including provenance/visual annotations, not an estimate of final full-corpus chunk counts. The blank-page sample's chunk contains comments only. No retrieval or performance benchmark was run.

**Unresolved semantic boundary:** syntactic preservation does not ensure shared restrictions accompany every later fragment. MK3S has three menu fragments without the complete general note in each strategy; XL has two procedural fragments without both prior warnings in each strategy. These findings are recorded rather than hidden by changing chunk size, overlap or production code. The method is therefore not yet a safe final text-RAG representation for all procedures.

Regression command:

```powershell
$env:LAEW_PUBLIC_CORPUS_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111'
$env:LAEW_PRUSA_R1_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r1'
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q
```

**37 passed in 3.19 s.** Tests cover menu ancestry/conditions, warning scope/order, procedure numbering reset, source legends, table identity/units, literal icon distinctions, deterministic replay, exact source spans, audit coverage and unchanged trust anchors/WAL pin. One initial test assertion was corrected from `>` to `>=` for adjacent half-open character ranges; it was not an extraction defect.

## Structural screening of all 418 pages

The scanner reads existing PDF objects and the accepted independent-extractor cache. It does **not** convert the six complete manuals to Markdown. Results are recorded for every page in R1 `structural-audit-418.json` and `inspection-queue-418.csv`; the [repository audit export](prusa-pdf-r1-20261111-audit.json) contains the same page-level metadata and sample checks without manual body text.

| Manual | Pages scanned | Pages flagged |
|---|---:|---:|
| MINI PL | 58 | 49 |
| MK3S PL | 84 | 68 |
| MK4 DE | 69 | 58 |
| MK4S EN | 66 | 55 |
| MMU3 EN | 56 | 50 |
| XL DE | 85 | 71 |
| **Total** | **418** | **351** |

Overlapping risk flags:

| Reason | Pages |
|---|---:|
| Substantial image needing visual review | 230 |
| Colored callout scope | 159 |
| Alignment / possible borderless table | 81 |
| Independent text disagreement | 18 |
| Merged or ambiguous table cells | 16 |
| Simple ruled table cells | 6 |
| Rotated text | 5 |
| Menu indentation | 2 |
| Complex vector grid | 2 |

The remaining **67** consist of one blank page and **66 pages with no rule triggered**. These 66 are not certified or declared error-free. Flags are inspection candidates, not proof of extraction failure; categories overlap. Alignment detection is deliberately conservative and may include ordinary layout. The scanner does not exhaustively establish all semantic or reading-order dependencies.

## Remaining limits and proposed R2 boundary

- Raster-only UI locations, colored marks and image relationships remain unresolved for text-only RAG. Embedding an image is not counted as recovering its meaning.
- Shared warnings and page-level notes need a source-grounded representation that remains available across chunk boundaries. Do not claim the current tests solve that problem.
- Merged/borderless tables, complex graphics, rotated text, unusual columns and cross-page structures require targeted review. The two table probes do not certify every table.
- The icon dictionary recognizes only exact reviewed image streams. New/unclassified symbols must not receive a guessed severity or description. Repeated source assets may be matched by hash; new assets require review.
- Font and incoming-section rules are heuristics with coordinate provenance, not a general PDF semantic parser. Eight original samples plus two probes are not sufficient for blanket approval of all 418 pages.
- Full-manual character/chunk counts remain unknown under R1. R2 must recalculate them and apply the existing resource review boundary without cropping sources.

**Recommended R2, subject to approval:** address note/warning propagation first; then generate separate, versioned candidate copies of all six unchanged manuals, process the inspection queue and explicitly adjudicate unresolved visual/table cases. Keep the accepted corpus unchanged until a separate admission decision. Do not freeze, label questions, index, or begin Task 3C.2B as part of this approval.

## Artifacts and integrity

R1 `review.html` provides the comparison; `before/`, `samples/`, `renders/`, `figures/`, `objects/`, `maps/`, `diffs/`, `table-candidates/` and the inspection queue preserve the details. Original handbook pixels/text remain local research material; no handbook redistribution grant was established. No source material was added to Git.

Offline verification, without downloads or writes:

```powershell
python -B tools/corpus/check_prusa_remediation.py --corpus C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111 --output C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r1 --verify-r1
```

Verified: **87 R1 inventoried files** and all **289 accepted corpus files**, with no mismatch. Review-bundle trust anchors:

- `review-snapshot-manifest.json`: `e7a80f29d76382e3cbbdba09c75ebe84d79db695734f4bc3fc2f793b7505483b`
- `r1-integrity-inventory.json`: `0e02f604e3113a839fb1d7efc2b3e20f39b4c003b62326da6db0b944cddf35cf`

The accepted manifest/inventory remain `3b25c6c001479e8c8f05847058f884f0c38093d6db0f37fa628e8ef6359e65a3` / `7ce040ed0bf8cda84d6a86a0bbb4c06497e72899258ea40135dd8dce30cd874b`. Exact R1 tool/test hashes are archived with reproduction instructions. This is a review snapshot, not a corpus freeze.

This task added two tools (`prusa_pdf_remediation.py`, `check_prusa_remediation.py`), `tests/evaluation/test_prusa_pdf_remediation.py`, this report, the audit JSON and a [Git status snapshot](prusa-pdf-r1-20261111-git-status.txt). Existing production files, previous corpus tools/artifacts, vaults and indexes were not edited. Pre-existing tracked modifications remain `docker-compose.yml` and `docs/README.md`. No commit, push, reset or clean was performed. No questions, evidence labels, embeddings, ChromaDB or generative-model calls were created/run.
