---
type: report
title: Full source-once corpus regeneration - Task 3C.2A-R3C
date: 2026-11-11
status: candidates-complete-not-admitted-not-frozen
scope: 24 source units, six regenerated manuals, 418-page structural audit
---

# Result

Complete candidates are in **`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3c-v2`**. The six Prusa files are `normalized/prusa-mk4s-en.md`, `prusa-mmu3-en.md`, `prusa-mk4-de.md`, `prusa-xl-de.md`, `prusa-mini-pl.md` and `prusa-mk3s-pl.md`. All eighteen Git/PostgreSQL Markdown files are byte-identical copies of their accepted versions. Originals, public assets, licenses and pinned-source snapshots are retained locally.

The corpus contains **1,281,131 body characters**, **1,287,327 including YAML**, and **1,307,740 UTF-8 bytes** in the 24 Markdown files. The actual unchanged loader produces **2,171 legacy / 2,185 structure-v2 chunks**. All six manuals have different primary boundaries and payload sequences between strategies. The 3,000-chunk resource-review trigger is not exceeded. These are preparation/consistency results, **not semantic admission or retrieval results**.

**124 tests passed. All 418 pages pass the recorded structural checks.** Nine unresolved regions, fifteen mandatory human-review gates, and all inherited priorities remain open. Recommend a separate admission/scope review; do not start freezing, Task 3C.2B or indexing automatically.

# Representation, repairs and provenance

The R3A representation is used throughout: source headings, paragraphs, numbered steps, native tables and original-position callouts occur once. Native one-column lists were reflowed in **147 blocks** using explicit text markers or repeated small filled bullet objects immediately left of native text. Ambiguous columns were not reconstructed automatically. Original words, values and marker provenance are retained; this is source-layout presentation, independent of either chunker's size. No R2 H6 packets, per-packet labels or per-chunk warning duplication are present. Original authored repetitions remain.

Exactly **22 R3B operations on 20 pages** were applied from the verified overlays: six native-table relationship repairs, five column-order repairs, four callout-tail repairs, two heading repairs and five native rotated-text repairs. Each overlay requires matching original PDF and R2 structured-input SHA-256 values; its R3B Markdown/map identity is also checked. No publisher-authored section-number oddity, URL spelling, untranslated passage or technical value was silently corrected. The WAL commit remains `220b5263dbb71bbe2966c6d47c0c456c14ed4e48`.

The initial R3C-v1 draft is retained separately. Final v2 represents explicit native bullets as valid Markdown list markers rather than literal circle glyphs. Both draft and final have the same measured character/chunk totals; the change corrects Markdown presentation, not strategy performance. Only v2 is the final candidate workspace.

All **418 original page rasters** are copied unchanged and hash-checked. **725 native image-object records** retain original object/hash/bounding-box provenance, including small icons. Original embedded pixels remain in unchanged PDFs. Figure Markdown links the corresponding local original page raster and PDF page; it does not describe image content or make graphical meaning available to text-only RAG.

`maps/` records full-file Unicode offsets, primary block/page spans, line ownership, table-cell ranges, source-input hashes and separately identified derived subranges. Blank pages remain in page maps and raster assets. Excluded page-number footers remain in originals/native geometry and are recorded explicitly. `warning-applicability-reviewed.json` rebases six R3B source-scope decisions; historical proposals are separately marked unverified and mapped through repaired source blocks. **Sidecars are not automatically delivered to an LLM.** No production loader, context rule or renderer was changed.

# Full-corpus measurements

All paths follow `normalized/<source_id>.md`. Character counts below exclude YAML. Full-file characters, SHA-256, bytes, per-strategy min/p10/median/p90/p95/max sizes, overlap, context, token estimates and attribution are provided for **every unit** in [the CSV](prusa-pdf-r3c-20261111-metrics.csv) and [verification JSON](prusa-pdf-r3c-20261111-verification.json).

“Different ends” counts the symmetric difference of internal primary end offsets after edge-whitespace trimming. “Unmatched payloads” counts legacy/V2 payload occurrences without an identical counterpart after edge trimming; it is not a quality/recall score.

| Source ID | Body characters | Chunks L / V2 | Different ends | Unmatched payloads L / V2 |
|---|---:|---:|---:|---:|
| prusa-mk4s-en | 125,803 | 210 / 212 | 152 | 154 / 156 |
| prusa-mmu3-en | 96,081 | 162 / 160 | 111 | 119 / 117 |
| prusa-mk4-de | 143,394 | 233 / 243 | 188 | 180 / 190 |
| prusa-xl-de | 181,504 | 303 / 307 | 234 | 226 / 230 |
| prusa-mini-pl | 115,345 | 191 / 194 | 147 | 139 / 142 |
| prusa-mk3s-pl | 153,162 | 266 / 263 | 193 | 191 / 188 |
| progit-first-time-setup-en | 6,245 | 13 / 13 | 4 | 10 / 10 |
| progit-config-en | 21,003 | 42 / 39 | 30 | 27 / 24 |
| progit-remote-branches-en | 13,652 | 24 / 26 | 21 | 21 / 23 |
| progit-submodules-en | 41,439 | 74 / 76 | 63 | 69 / 71 |
| progit-first-time-setup-pl | 3,845 | 7 / 7 | 0 | 3 / 3 |
| progit-config-pl | 21,669 | 42 / 38 | 32 | 28 / 24 |
| progit-remote-branches-pl | 13,190 | 22 / 24 | 25 | 19 / 21 |
| progit-submodules-pl | 34,745 | 60 / 62 | 52 | 56 / 58 |
| progit-first-time-setup-de | 7,247 | 13 / 14 | 9 | 10 / 11 |
| progit-config-de | 23,959 | 45 / 41 | 31 | 31 / 27 |
| progit-remote-branches-de | 15,917 | 27 / 27 | 10 | 24 / 24 |
| progit-submodules-de | 45,574 | 81 / 83 | 72 | 76 / 78 |
| postgresql-17-continuous-archiving | 48,612 | 81 / 80 | 62 | 76 / 75 |
| postgresql-17-runtime-config-wal | 47,937 | 76 / 76 | 77 | 76 / 76 |
| postgresql-17-backup | 2,094 | 4 / 3 | 3 | 4 / 3 |
| postgresql-17-recovery-config | 1,486 | 2 / 3 | 3 | 2 / 3 |
| postgresql-11-continuous-archiving | 45,979 | 78 / 77 | 73 | 73 / 72 |
| postgresql-12-release-12 | 71,249 | 115 / 117 | 130 | 110 / 112 |
| **Total** | **1,281,131** | **2,171 / 2,185** | **1,722** | **1,724 / 1,738** |

The six manuals contribute **815,289 body characters / 1,365 legacy / 1,379 V2 chunks**; the unchanged eighteen units contribute **465,842 / 806 / 806**. Compared with R2's 3,980 Prusa chunks per strategy, fragmentation is substantially reduced without cropping authentic text. Even the Polish setup unit with zero different end positions has different primary starts/overlap and payloads. All **24 payload sequences differ** after whitespace trimming; equal counts on individual units are not forced equality.

| Corpus-level delivery measure | Legacy | Structure-v2 |
|---|---:|---:|
| Chunk min / median / max characters | 1 / 784 / 1,000 | 17 / 839 / 1,000 |
| p10 / p90 / p95 characters | 284 / 967 / 984 | 474 / 1,000 / 1,000 |
| Chunks below 200 characters | 170 | 35 |
| Delivered characters over all chunks | 1,520,769 | 1,713,970 |
| Added source overlap / synthetic context | 241,459 | 432,839 |
| Estimated delivered tokens, sum ceil(chars/4) | 381,013 | 429,229 |
| Limited-context flag | N/A | 2,002 chunks |

Legacy overlap is **18.8%** and V2 synthetic context **33.8%** of body size. Whitespace trimming explains why delivered-minus-body is not exactly legacy overlap. The token proxy is not a tokenizer measurement or a multilingual guarantee. These are whole-corpus payload totals, not per-query context usage. Longer context and different boundaries are not claims of retrieval or answer-quality improvement.

Legacy attribution comes from tracing the **actual unchanged engine's** append positions and checking exact payload/source equality, not replacing its algorithm or guessing repeated occurrences. V2 uses native primary offsets/context spans; primary spans partition each body exactly. All 24 units have complete non-whitespace primary coverage and no invalid source ranges or broken local references.

# All-page checks and representative inspection

`structural-audit-418.json` records **418/418 passing pages**, **zero failed checks**, source-line ownership/order, **10,250 non-table line checks**, **235 cell checks**, and **6,199 numeric/negation-token checks**. Table glyph multisets are compared with native source objects; reviewed columns are checked separately in their approved reading order. Every failed check would retain source ID, page and block/line/cell location. No original non-footer line is missing or multiply owned; no new block-order inversion or missing checked value was detected. No semantic page certification follows from this result.

Full-document representative inspection covered selftest warnings/lists (MK4S 19), purge matrix/units (MMU3 40), repaired product table (MK4 7), cross-page sheet installation (XL 23–24), long usage/risk cells (MINI 44), and repaired literal pros/cons (MK3S 69), plus all six reviewed applicability groups. `representative-review.html` shows the originals, actual Markdown and real overlapping chunk payloads. Original pixels are unchanged from the visually reviewed R3B sources. Review origin is agent, not independent human.

The whole-document scope diagnostics show **5/4 legacy/V2 chunks for the MK3S menu, 4/4 for XL sheet installation, 7/7 for MK4S, 8/8 for MK4, 6/7 for MINI sheets, and 4/4 for MMU procedures**. Each group's retained source note bodies appear intact somewhere in both strategies except MINI V2, where one of four bodies spans chunks. All remain present in the document. This is source-presence instrumentation, not a rule that every note applies to every chunk, gold labels or a retrieval score. Valid source text can still require unioning chunks; sidecar information does not count as delivered context.

# Open limitations and next admission decision

The full register retains **0 Critical / 388 High / 10 Medium / 20 Low**, including **329 uninspected High pages**. Structural consistency passes did not downgrade or close anything. All **nine** R3B region limits and **15** mandatory human-review gates are rebased to exact R3C source ranges:

- MK3S PL **16, 37** and MINI PL **45**: graphical column polarity or callout applicability remains unresolved.
- MMU3 EN **6** and XL DE **81**: safety/electrical symbol relationships need qualified disposition; literal descriptions/table text are retained.
- MK4 DE **33** and XL DE **35**: reset-procedure completeness depends on screenshot-only information.
- MK4S EN **19** and MK4 DE **22**: sensor-test startup substeps depend on screenshot-only information.
- The additional six human gates are corrected product tables MK4 DE **7–8**, MK4S EN **6**, MMU3 EN **7**, XL DE **9**, and PDU identification XL DE **83**.

Limitations target source regions and types of support; no entire manual or section was silently removed. Original captions/text and unreviewed material remain. Derived availability/layout annotations have separate provenance and contain no invented technical descriptions or benchmark answer hints. Future use must distinguish valid split text, explicitly unavailable visual meaning, actual extraction defects and unresolved technical relationships. The old R3B scope policy remains a proposal, not admission.

The corpus meets the proposed character range without cropping. Actual counts remain below the 3,000 review trigger; **no resource override is needed**. The 4,356 hypothetical chunk vectors would occupy about **17 MiB raw float32 storage at 1,024 dimensions**, excluding index/metadata overhead. Using the specification's illustrative 0.25–0.75 seconds/input plus 60 query inputs implies approximately **18–55 minutes**, not a measured embedding/build time. No vectors or queries were generated. R3C v2's local inventory is **750 files / 264,064,509 bytes**, excluding its inventory file; the earlier draft is additional retained staging.

Recommend a bounded **admission/scope decision** next: review the nine unavailable/uncertain regions and fifteen human gates, decide what explicit support restrictions are acceptable, and plan disposition of the untouched risk queue. Do not declare the entire corpus admitted from these checks. Any admission, freeze or subsequent labeling/indexing requires a separate authorization.

# Integrity, tests and changed files

**124 tests passed in 10.20s** through `scripts/run_isolated.py`, including new full-corpus checks and the R3B/R3A/R2/R1, acquisition and both chunker regressions. They cover all source IDs/hashes, 18 byte-identical units, all pages/line ownership, repair identity rejection, availability markers/gates, unchanged priorities, real differing boundaries/payloads, image references, list rendering and original untranslated prose. The exact command/log is in R3C `isolated-tests.txt`; set `LAEW_PRUSA_R3C_ROOT` to v2 alongside the earlier corpus environment variables and add `tests/evaluation/test_prusa_pdf_r3c.py` to the prior isolated suite.

Read-only offline verification:

```powershell
python -B tools/corpus/finalize_prusa_r3c.py --verify --accepted 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111' --r2 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1' --r3a 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3a-v1' --r3b 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3b-v1' --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3c-v2' --expected-inventory-sha c63e3eddfc17b9c04f420d1ec3cb2e1c7196b3ffaeae9346a58fcadf600a93aa
```

Before/after checks confirm the unchanged **289 accepted / 87 R1 / 1,297 R2 / 75 R3A / 203 R3B** inventory entries. The command also checks the 24 candidate original/normalized hashes, 18 unchanged Markdown identities and WAL pin without redownloading or writing. Hash integrity is not semantic certification. R3C `README.md`, manifest, maps, tool snapshots and inventories document regeneration and license restrictions; source files/payload material were not added to Git.

Added: `tools/corpus/regenerate_prusa_r3c.py`, `audit_prusa_r3c.py`, `finalize_prusa_r3c.py`, `tests/evaluation/test_prusa_pdf_r3c.py`, this report, `docs/reports/prusa-pdf-r3c-20261111-verification.json`, `prusa-pdf-r3c-20261111-metrics.csv` and `prusa-pdf-r3c-20261111-git-status.txt`. No existing production/acquisition/R1–R3B tools were changed. Pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`; unrelated uncommitted work is preserved. No commit, push, reset, clean, admission, freeze or Task 3C.2B occurred. **Stop pending approval for the next admission-review step.**
