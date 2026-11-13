---
type: report
title: Full Prusa PDF candidate conversion - Task 3C.2A-R2
date: 2026-11-11
status: candidates-generated-further-remediation-required
scope: six complete candidates, 418-page structural audit, 28-page targeted visual review
---

# Result and decision

Six complete candidate Markdown files were generated in the separate versioned workspace `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1`. **Recommend further remediation, not corpus admission or freezing.** The reviewed warning dependencies survive both unchanged chunkers, but applicability coverage remains partial; graphics, merged/borderless tables and remaining conditions require adjudication. Automated checks do not certify the semantic correctness of all 418 pages.

Accepted corpus and R1 are unchanged: all **289 / 87** inventoried files and their original manifest/inventory anchors were verified. Original PDFs were read only. The accepted mixed PL/EN Pro Git sections and PostgreSQL WAL commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48` are preserved. No production, vault, Horizon, reranker, index or model configuration was changed; no model inference, questions, labels, embeddings, retrieval benchmark, admission or freeze occurred.

# Method and warning preservation

R2 wraps the unchanged R1 converter with evaluation-only repairs: recover small numbered source headings; reconstruct complete icon paragraphs from coordinates; carry explicit LCD menu ancestry across pages; retain every table cell with row/column context; and create bounded Markdown leaf packets. Extraction uses bundled **Python 3.12.14 / pdfplumber 0.11.9**, source glyphs, fonts and geometry. **Poppler 26.07.0** rendered all 418 original pages. Existing LAEW Python **3.14.7** runs the actual parser/chunker checks. No new dependencies, OCR or generated image descriptions were used.

Each packet retains primary source ranges and distinguishes `[Source]` from `[Derived repeats]`. Repetitions contain verbatim source warning/condition text, not new technical advice. Short aliases such as `p23n1` resolve to full source IDs, pages and source spans in `maps/`; menu ancestor labels and table labels are explicitly derived structural context. Unique H6 boundaries make the existing chunkers retain these packets within **1,000 characters**, with legacy overlap **200** unchanged. Original headings remain above the packets. The candidate is evaluation-specific Markdown; its many derived headings add overhead and are not an admission decision.

Reviewed applicability rules cover MK3S PL menu pages 35–36; XL DE sheet installation 23–24; MK4S EN selftest/calibration 18–19; MK4 DE 21–22; MINI PL sheet/calibration context 42–45; and MMU3 EN procedure 2.6 on page 22. Warranty, photo-local and unscoped notes remain primary text and are not broadcast indiscriminately. XL finger clearance is tied to its own alignment paragraph; source bold bed/cleanliness restrictions and MK4/MK4S 5 cm prerequisites also repeat where reviewed.

Of **318** extracted callout nodes, **13** have reviewed, materialized repetition rules; **305** remain primary-only with applicability review outstanding (including legitimate exclusions). Four additional literal source-condition records are used. There are **52** primary block relations with materialized reviewed dependencies and **1,132** block relations with unreviewed candidate associations. Those proposals are retained in metadata, flagged and **not** silently applied. These counts describe coverage, not a claim that every remaining note must repeat.

All materialized dependencies survive in the actual delivered legacy and structure-v2 chunks: **zero detected dependency failures**. Structure-v2 offsets partition each candidate exactly; the legacy parser retains its existing whitespace behavior. A capacity guard fails rather than truncating required source text. Reviewed sets fit the existing contract. Earlier broad chapter associations produced capacity alarms; recovering small subsection headings and excluding unrelated chapter/photo/warranty associations resolved those inference errors. Historical diagnostics remain labelled as superseded; `contract-status.json` is authoritative. No production contract change was made, and no reliability claim is made for unreviewed sets.

# Complete candidates and overhead

All paths below are relative to R2. Revision and product applicability are inherited unchanged from the accepted source manifest; originals, URLs, licenses and hashes are recorded in `candidate-manifest.json` and the repository metadata export.

| Candidate | Revision | PDF pages | Markdown characters | UTF-8 bytes | Legacy / structure-v2 chunks |
|---|---:|---:|---:|---:|---:|
| `candidates/prusa-mk4s-en.md` | 1.01 | 66 | 163,943 | 166,867 | 600 / 600 |
| `candidates/prusa-mmu3-en.md` | 1.03 | 56 | 126,839 | 129,353 | 539 / 539 |
| `candidates/prusa-mk4-de.md` | 1.03 | 69 | 186,250 | 191,024 | 609 / 609 |
| `candidates/prusa-xl-de.md` | 1.06 | 85 | 238,292 | 244,544 | 810 / 810 |
| `candidates/prusa-mini-pl.md` | 1.09 | 58 | 151,793 | 159,990 | 491 / 491 |
| `candidates/prusa-mk3s-pl.md` | 3.17 | 84 | 204,297 | 215,379 | 931 / 931 |
| **Total** | | **418** | **1,071,414** | **1,107,157** | **3,980 / 3,980** |

Candidate character accounting: **819,783** primary representation characters (including structural menu ancestry/figure references), **48,678** derived repetition-block characters including table context and aliases, and **202,953** remaining packet/boundary markup characters. The repetition blocks account for **4.54%** of the final candidate. These are representation counts, not raw publisher prose counts or token estimates.

Compared with the six accepted plain-extraction bodies (**749,370** characters; **1,183 / 1,141** chunks), candidates add **322,044 characters (+42.98%)**, **2,797 legacy chunks (+236.4%)** and **2,839 structure-v2 chunks (+248.8%)**. Counts are actual dry ingestion, not retrieval results. The eighteen unchanged other sources contributed **806** chunks in each strategy; hypothetical replacement would yield **4,786** total chunks, exceeding the specification's proposed **3,000-chunk cap**. No source was cropped to satisfy that cap. Resolving fragmentation/budget requires a separate decision before admission. No index was created.

For scale only, adding the unchanged eighteen source bodies (**465,842** characters) to the candidates gives **1,537,256** characters, within the proposed 0.8–1.6M range. This mixes body-only baseline counts with candidate structural markup and must not be treated as a comparable raw-prose size. R2 disk inventory is **1,297 files / 372,425,616 bytes**, including renders, geometry, diagnostics and reproducibility artifacts; originals remain in the accepted corpus.

# All-page audit and exact remaining work

| Manual | Critical | High | Medium | Low |
|---|---:|---:|---:|---:|
| MK4S EN | 0 | 61 | 0 | 5 |
| MMU3 EN | 0 | 52 | 1 | 3 |
| MK4 DE | 0 | 64 | 3 | 2 |
| XL DE | 0 | 77 | 2 | 6 |
| MINI PL | 0 | 55 | 1 | 2 |
| MK3S PL | 0 | 79 | 3 | 2 |
| **Total** | **0** | **388** | **10** | **20** |

Checks found no missing/duplicated primary source lines, missing non-whitespace glyph sequences, missing checked native table cells/numeric values, source-range discontinuities or coordinate-order inversions. Explicit square menu bullets become structural paths, and page-number footers are separately excluded. Retention checks against PDF text objects cannot detect text embedded only in images or prove correct semantic reading order. Native table checks do not validate merged-cell interpretation.

Risk flags overlap: **261** pages with inline-condition applicability review; **230** with substantial images; **191** with unmaterialized dependency candidates; **174** with uncertified callout applicability; **159** with colored-callout scope review; **81** alignment/borderless-table layouts; **32** merged/ambiguous-cell flags; **18** existing independent-extraction disagreements; and smaller rotated/vector/layout categories. A flag is not proof of a defect. No automatic promotion follows from an empty flag set.

The exact **388 unresolved High pages** are listed by source ID and PDF page in R2 `unresolved-critical-high-pages.csv`; `inspection-queue.csv` lists **all 418** pages, including ten Medium and twenty Low pages. Repository `prusa-pdf-r2-20261111-audit.json` also contains every page record and flag. Component reviews below do not clear whole-page priority entries. **No whole page is claimed semantically certified**, including unflagged pages.

Planning estimate, not a measured commitment: at 3–8 minutes for each High page, first-pass review is approximately **19–52 hours**, plus approximately **4–8 hours** for cross-page dependency adjudication, corrections and regression checks; complex visual/merged-table cases may require more. The Low and Medium pages still need proportionate sampling/review before any admission claim.

# Targeted visual review

Original PDF renders were compared with source blocks and exact generated candidate excerpts on **28 distinct pages**, with **40 component decisions**. R2 `review.html` presents original renders beside candidate Markdown; `visual-review-decisions.json` records each decision. Review was performed by this agent and is not independent human certification. The original eight R1 samples are included.

| Pages | Component outcome | Finding / remaining limitation |
|---|---|---|
| MK3S PL 12–13 | Corrected and verified | Small numbered subsection headings restored; flowchart arrow graph on 12 is **Not safely representable as text** from current source text. |
| MK3S PL 15 | Corrected and verified | Complete icon paragraphs recovered; warranty remains primary-only. |
| MK3S PL 16 | Requires manual review | Pros/cons columns and tick/warning polarity; first-layer photographs are **Not safely representable as text**. |
| MK3S PL 35–36 | Corrected and verified | 44 + 49 menu items, cross-page parent chain and original shared note survive chunks. Regression exposed and repaired page 36's lossless fallback lacking menu structure. |
| XL DE 7 | Verified correct | Original blank page confirmed; no invented source content. |
| XL DE 16–18 | Verified correct (prose/topic separation) | Distinct installation topics retained. Illustration-only part positions remain **Not safely representable as text**. |
| XL DE 23–24 | Corrected and verified (reviewed dependencies) | Three source warnings, bold bed/cleanliness restriction and local finger warning preserved. Spatial alignment on 23 remains **Not safely representable as text**. |
| XL DE 62 | Requires manual review | Material table polarity and borderless columns; original text/temperatures retained. |
| XL DE 70; MK4S EN 58; MK4 DE 60 | Verified correct (table cells/context) | Product and usage/risk labels retained in every cell fragment; no whole-page callout certification. |
| XL DE 81 | Requires manual review | PDU merged dimensions/safety legend; numerical tokens alone do not resolve relations. Graphic symbols remain **Not safely representable as text** without reviewed mapping. |
| MK4S EN 18–19; MK4 DE 21–22 | Corrected and verified (selected procedure dependencies) | Cross-page bed prerequisite, local stability/no-touch warnings and 5 cm prerequisite retained, without leaking into 4.5. |
| MINI PL 31 | Verified correct (published legend) | Twelve Polish entries retained; raster interface positions remain **Not safely representable as text**. |
| MINI PL 44 | Corrected and verified | Row/column context repeated; selected calibration/handling notes retained separately from warranty/property notes. |
| MMU3 EN 22 | Corrected and verified | Two 1–6 sequences and scope-specific note; no unrelated repetition into 2.5. |
| MMU3 EN 40 | Verified correct (matrix) | Six rows, column identities and units retained; photo relationships remain **Not safely representable as text**. |
| MK4S EN 42; MK4 DE 43; XL DE 46 | Verified correct (published legends) | Fourteen entries each retain order and wording. Raster callout endpoints remain **Not safely representable as text**. |

“Not safely representable as text” describes the current text-only conversion; a later reviewed human transcription may be possible. Linking original images preserves access and provenance but does not resolve text-only RAG semantics.

# Tests and reproducibility

**63 tests passed in 4.89s**, through `scripts/run_isolated.py`, covering the existing corpus/R1 tests, both chunker suites and new R2 regressions: all six candidates and 418 pages, actual delivered dependency text, cross-page menu/conditions, table identity, scope exclusions, capacity failure, R1 glyph equality, legends/blank page and resolvable figure links. First run found page 36's missing menu classification; it was repaired and the full selected suite rerun. No test used a store or embedding service.

```powershell
$env:LAEW_PUBLIC_CORPUS_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111'
$env:LAEW_PRUSA_R1_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r1'
$env:LAEW_PRUSA_R2_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1'
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

Offline byte-integrity check, without redownloading or rewriting files:

```powershell
python -B tools/corpus/finalize_prusa_r2.py --verify --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1' --expected-inventory-sha 3fc630e9ca60a06223da8ec8198b13f7b3d51c98193271bab61007e2198ce9fb
```

This checks every R2 file, rejects unexpected paths and verifies accepted/R1 inventories and anchored identities. R2 `README.md` gives regeneration instructions into a **new** workspace; `reproduction-tools/` contains tool/test snapshots. The manifest records source/candidate hashes and exact local production chunker/loader hashes. Rechecking hashes establishes byte identity, not semantic correctness.

| Candidate | Normalized SHA-256 |
|---|---|
| MK4S EN | `5b4ac5d74d146432ea91a821a860652a2f7c7181795e0176db7c53ce26e6135f` |
| MMU3 EN | `02960742d636c41af45cd2bf3dea2b150263f92604df1671f5b63c697cb550a5` |
| MK4 DE | `926372b4532988f85a1985e59ab72bc39ef536befec2fff85a00366ac5d9b594` |
| XL DE | `0b5303e81125c3bfdf383facba1ce58ba9efbc058b842989f22afef1399f0d0e` |
| MINI PL | `3db38dae0fb7f597b470b96828dc27c99120e7e8413a40628da7bc27f2b89f83` |
| MK3S PL | `9597e3302eff1ed0942d5532a75278a3ce7f18a3d5416e5ca79c3433c8223fb7` |

No Prusa handbook redistribution grant has been established. PDFs, candidate text, renders and source-bearing maps remain in local staging, outside Git. Repository exports contain code and QA metadata only. No source substitutions or changes to EN/PL acceptance were made.

# Changed files and next gate

R2 adds `tools/corpus/prusa_pdf_r2.py`, `tools/corpus/audit_prusa_r2.py`, `tools/corpus/finalize_prusa_r2.py`, `tests/evaluation/test_prusa_pdf_r2.py`, this report, `docs/reports/prusa-pdf-r2-20261111-audit.json` and `docs/reports/prusa-pdf-r2-20261111-git-status.txt`. R1/acquisition scripts were not changed. Full Git status is in the last file; pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`, with many unrelated untracked artifacts preserved. No Git add, commit, push, reset or clean occurred.

Stop here. Further work should first adjudicate the exact High queue, define approved representations for visual/merged-table cases, expand reviewed applicability rules and resolve the 3,000-chunk budget. **User approval is required before additional remediation or any later corpus admission/freezing. Task 3C.2B has not started.**
