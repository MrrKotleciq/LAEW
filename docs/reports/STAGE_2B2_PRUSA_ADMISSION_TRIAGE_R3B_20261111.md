---
type: report
title: Risk-based PDF admission triage - Task 3C.2A-R3B
date: 2026-11-11
status: bounded-agent-triage-complete-no-admission
scope: 60 inspected pages, 20 experimental page repairs, six applicability groups
---

# Result and recommendation

**Source-once candidate regeneration is feasible, with explicit restrictions; corpus admission is not established.** Recommend separately approving R3C to apply the demonstrated repairs, generate reviewable source-once candidates and carry unresolved availability/priorities forward. Do not reconstruct every figure or reinstate R2's forced H6 packets. Nine inspected regions still need manual disposition or approved restrictions on complete procedural/graphical support; five additional corrected product tables and the PDU identification page require human checks before admission.

Separate workspace: `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3b-v1`. Its `review.html` shows original renders beside actual initial and corrected Markdown. `inspection-decisions.json` / CSV record source/page, original category/flags, evidence hashes, method, reason, correction need, blocking status, reviewer origin and uncertainty for every inspected page. `availability-register.json` identifies exact affected source block/line IDs. Source-bearing material remains local; no Prusa redistribution grant is asserted.

No full manual was regenerated, admitted or frozen. All 24 sources, original PDFs, mixed-language acceptance decisions and PostgreSQL WAL commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48` remain unchanged. No questions, evidence labels, OCR, generated visual descriptions, inference, embeddings, ChromaDB or retrieval run occurred.

# Review performed and exact counts

Read R3A/R2 reports, queues, prior visual decisions and all seven source-once examples. Compared original R2 Poppler renders with actual excerpt text and native PDF objects; corrections were then checked against those originals and their glyph/cell coordinates. All reviews are **agent-origin**, with **zero independent human certifications**. Decisions concern the stated components, not automatic whole-page closure.

| Phase | Bounded inspection | Verified correct | Corrected and verified against source | Visual information unavailable in text | Unresolved - manual review required |
|---|---:|---:|---:|---:|---:|
| A: text/layout | 36 pages: all 16 merged-cell pages, all 18 extraction disagreements, two additional polarity pages | 3 | 16 | 13 | 4 |
| B: visual-only | 12 of 43 candidates; two individually inspected pages per manual | 0 | 0 | 10 | 2 |
| C: applicability | 6 groups / 13 pages, including one A overlap | 9 | 1 | 0 | 3 |
| **Distinct-page dispositions** | **60** | **11** | **17** | **23** | **9** |

The fifth outcome, **Extraction defect - blocks admission**, has zero final page dispositions: confirmed repairable defects were corrected in experimental excerpts, while remaining ambiguous cases explicitly use the unresolved outcome. This does not mean the existing accepted/R2 Markdown has been repaired. Repairs touch **20 experimental page copies / 22 repair operations**; three corrected pages still have unresolved graphical/safety meaning and therefore are not counted in the 17 corrected final dispositions.

Of the inspected pages, **59 were originally High and one Medium** (MK3S PL 35). Original priorities remain **388 High / 10 Medium / 20 Low / 0 Critical**. Fully uninspected: **329 High / 9 Medium / 20 Low**. The 60 inspected pages have component decisions, not corpus admission. The other **31 image-only candidates** remain untouched. `uninspected-high.csv` lists exact remaining High pages; `outstanding-risk-register.json` preserves all 418 original priorities and inspection status. Nothing was closed by analogy.

# Confirmed defects and screening false positives

| Demonstrated repair | Operations | Inspected locations |
|---|---:|---|
| Restore label/value relationships from native merged cells | 6 | MK4 DE 7–8; MK4S EN 6; MMU3 EN 7; XL DE 9, 81 |
| Separate interleaved text columns | 5 | MK3S PL 16, 69; XL DE 62; MINI PL 42, 45 |
| Restore complete icon-adjacent paragraphs | 4 | MK3S PL 16, 19, 47, 59 |
| Restore chapter/multiline source headings | 2 | MK3S PL 11, 16 |
| Correct reversed rotated native text | 5 | Cover page 1 of MINI PL, MK4 DE, MK4S EN, MMU3 EN and XL DE |

These errors show why preserved glyph counts alone do not establish meaning. Table labels previously interrupted manufacturer addresses, operating-temperature values and dimensions. Pros/cons text interleaved across columns, and some source negations/conditions were detached from their callout. Native cells now retain all values/qualifiers, including PDU dimensions and ingress-protection wording; no number was inferred from a picture. Merged continuations remain under their source label, with native cell geometry preserved. The two-product MK4S table retains both names and their common values once. A neutral empty Markdown table header is explicitly derived, not publisher text.

Literal advantages/disadvantages headings were recovered on MK3S 69, XL 62 and MINI 42. MK3S 16 and MINI 45 have no literal polarity headings: text-column order is repaired, but graphical polarity remains unavailable/pending. No invented advantages/warnings were substituted. Rotated cover text was recovered from existing PDF text objects without OCR; raster/artwork-only cover information remains unavailable.

The merged-cell screen also flagged **ten non-grid MK3S pages** (8, 11, 19, 26, 36, 37, 39, 47, 59, 69). There is no missing native merged table on those pages; some nevertheless contain genuine heading/callout/column defects. This is a false-positive **table interpretation**, not grounds to clear the page. Among the 18 independent extraction disagreements, five covers have actual native reading-order defects; the other thirteen inspected cases do not show missing native prose in the checked components, but retain graphical/association limits. Preserve source-authored oddities: MK3S 47's repeated section number, source URL spellings, and the authentic English note in the Polish MK3S manual on page 26 were not silently corrected or translated.

# Outstanding blocking regions and human gates

All original text remains. Availability examples add a clearly derived limitation next to the affected region, with no new technical advice or visual transcription. These records propose restrictions on **complete procedural/graphical support**, not removal of entire sections or rejection of independently valid neighboring text.

| Source / PDF page | Remaining issue and required action |
|---|---|
| MK3S PL 16 | Source columns repaired; check/exclamation polarity lacks literal headings. Human interpretation or explicit graphical-relationship unavailability. |
| MK3S PL 37 | Feed-rate values survive, but icon paragraph scope is uncertain. Resolve exact association or quarantine that relationship. |
| MINI PL 45 | Incidental 9.2 interleaving repaired; no literal polarity headings. Manual disposition of column meaning; 9.1 text remains separate. |
| MMU3 EN 6 | Safety descriptions survive, but small symbol-to-description associations lack explicit representation. Qualified review or unavailable-symbol mapping. |
| XL DE 81 | Product table corrected; electrical symbol associations and interpretation require a qualified human. Do not claim complete electrical instructions. |
| MK4 DE 33; XL DE 35 | Reset screenshot contains a safety-relevant confirmation qualifier absent from prose. Complete reset-procedure support remains unavailable pending review. Neighboring example-model sections are not quarantined. |
| MK4S EN 19; MK4 DE 22 | Sensor-test startup state depends on screenshot-only information. Minimum filament-length and other literal prose remain valid; complete screen-driven procedure is unverified. |

There are **15 mandatory human-review page gates**: the nine above, plus corrected product tables MK4 DE 7–8, MK4S EN 6, MMU3 EN 7, XL DE 9, and PDU identification XL DE 83. The last page's component names survive, but connection geometry is unavailable. This list does not waive review of the untouched risk queue. The cover artwork's edition labels and other raster-only facts are not supplied as extracted evidence.

# Procedure/applicability decisions

Six source-once procedure excerpts and provenance sidecars were prepared; no warning is duplicated into every chunk. All relationships below are agent-verified source-scope decisions, not independent human certification or assertions of operational completeness.

| Group | Verified source relationship |
|---|---|
| MK3S PL 7.2.9, 35–36 | Shared note concerns unlisted settings; print-only restrictions remain on their branches; the menu continues across the page boundary. |
| XL DE 4.3, 23–24 | Sheet clearance/no-sliding, cleanliness/no-direct-bed and continued alignment restriction retain their scopes. Finger clearance stays local; spatial targets remain unavailable. |
| MK4S EN 4.3–4.4, 18–19 | Installed sheet precedes calibration; no-touch/stability applies during selftest; filament-length condition stays with selftest/sensor calibration. Optional internet setup and purpose note are not compulsory steps. |
| MK4 DE 4.3–4.4, 21–22 | Sheet preparation restrictions stay with 4.3; installed-sheet prerequisite carries to calibration; local selftest restrictions stay in 4.4, not later chapters. |
| MINI PL 9.1, 42–45 | Cool-surface cleaning restriction continues across pages. Recalibration/Live Z is conditional on changing plates, **not every cleaning**. Warranty/double-sided property are not procedural prerequisites. |
| MMU3 EN 2.5–2.6, 22 | Two separate six-step sequences. Straight filament-end note belongs to ejection 2.6; nozzle-loaded unloading condition and product-specific menu routes retain their branches. |

This refines the overly broad R2 association proposals, especially the MINI calibration note. Original authored repetitions remain; only derived per-chunk repetition is excluded. The production loader does not deliver arbitrary sidecars, so metadata alone never establishes that a retrieved payload contains a warning. All six tested source-once groups retain real legacy/V2 payload differences.

# Proposed text-only admission requirements

1. **Valid text split across chunks:** potentially compatible. Preserve original source ranges and conditions; missing context in a retrieved chunk is a system limitation, not automatically source corruption.
2. **Valid text with unavailable graphics:** potentially compatible after explicit availability/scope approval. Keep original captions/prose and page references. Do not claim complete visual identification, appearance criteria or screen-driven procedures from absent graphics.
3. **Incorrect/incomplete native extraction:** affected support is blocked until corrected and verified, quarantined by precise source region, or covered by a separately approved scope decision. Retain original text and complete manuals.
4. **Unresolved safety/table/applicability meaning:** qualified human disposition or an approved source-region restriction is required. Similar-page inspection and agent review do not provide independent human certification.

R3B applies none of these as an actual admission decision. The proposed policy is also stored in `admission-policy-proposal.json`. Source availability metadata is corpus QA, not question-specific evidence labeling.

# Feasibility and resources

The 60 paired page samples contain **87,371 source-once characters** versus **95,982 R2 primary-representation characters**. Per-manual ratios applied to existing R2 primary-size totals estimate approximately **746,559 Prusa characters**. Adding the unchanged eighteen source bodies gives approximately **1,212,401 characters**. This uses primary representation, not R2's repeated warning/packet text.

An explicit **±15% planning sensitivity on the Prusa estimate**, not a statistical confidence interval, gives approximately **1,100,417–1,324,385 characters for all 24 sources**. Applying the measured complete-section chunk-density ranges from the seven R3A samples gives scenarios of **1,746–2,439 legacy chunks** and **1,767–2,502 V2 chunks**, including the unchanged 806 text-source chunks per strategy. This is not full dry ingestion: the purposive samples, unresolved formatting and new annotations can shift actual counts beyond these ranges. No complete manual was assembled to obtain this estimate.

At the specification's illustrative 1,024 float32 dimensions, these scenarios imply about **14–19 MiB raw chunk vectors**, excluding index/metadata overhead. Its assumed 0.25–0.75 seconds/input suggests roughly **15–63 minutes** including 60 query inputs, before cache/build overhead. Neither indexing nor timing was run. Keep **3,000 chunks as a resource-review trigger**, not a validity limit; never crop authentic source text or tune production size/overlap/context to meet it.

# Validation, reproducibility and next gate

**102 tests passed in 4.39s** via `scripts/run_isolated.py`: 27 R3B checks plus the existing R3A, R2, R1, corpus and chunker suites. Tests verify native cell/glyph retention, column separation without invented polarity, complete callout tails, line ownership, exact excerpt hashes, unchanged priorities, untouched cases, source-preserving availability markers, neighboring-section isolation, and both real chunkers without embeddings.

Run the suites with the existing four corpus/R1/R2/R3A environment variables and `LAEW_PRUSA_R3B_ROOT` set to the R3B directory:

```powershell
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r3b.py tests/evaluation/test_prusa_pdf_r3a.py tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

Offline integrity check:

```powershell
python -B tools/corpus/triage_prusa_r3b.py --r2 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1' --r3a 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3a-v1' --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3b-v1' --verify --expected-inventory-sha e19abd2bf1407fff11f87e2ffe4fee9a1632905ad11852a9c1b21e6a6e714bdd
```

Before/after verification confirms **289 accepted, 87 R1, 1,297 R2 and 75 R3A files unchanged**. R3B has **203 inventoried files**. Its manifest records source/helper hashes and installed runtimes; snapshots and README give regeneration steps into a new experimental path. Replaying code does not independently reproduce a visual judgment.

New repository files: `tools/corpus/triage_prusa_r3b.py`, `prusa_native_repair_objects.py`, `prusa_r3b_review_notes.py`, `tests/evaluation/test_prusa_pdf_r3b.py`, this report, `docs/reports/prusa-pdf-r3b-20261111-triage.json` (metadata only), and `prusa-pdf-r3b-20261111-git-status.txt`. Prior tools and production code were not edited. Pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`; unrelated uncommitted work is preserved. No Git add/commit/push/reset/clean occurred.

**Stop here. Proposed R3C authorization is candidate regeneration only:** apply the 22 demonstrated repair operations under exact source hashes, carry all nine unresolved-region limitations and the complete open queue, retain all authentic text/source selections, measure actual resources, and leave admission/freezing/Task 3C.2B for separate decisions. This does not authorize complete graphical reconstruction or automatic clearance of the 329 uninspected High pages.
