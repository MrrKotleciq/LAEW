---
type: report
title: Stage 2B.2 public corpus acquisition and verification - Task 3C.2A
date: 2026-11-11
status: acquired-not-ready-for-freeze
scope: source acquisition, normalization and offline verification only
---

# Task 3C.2A - Acquisition result

**All 24 proposed units were acquired and normalized. Do not freeze this corpus or start Task 3C.2B yet:** six Prusa PDF normalizations fail admission because important visual structure is absent or insufficiently verified. Eighteen Git/PostgreSQL units pass the implemented text/source checks with the limitations below. No unavailable unit was silently replaced.

Persistent staging: `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111`. The dedicated directory is outside `C:\ROOT` and Obsidian vaults. Unchanged originals, local derived copies, images, HTTP provenance, licenses, page/section maps, extraction records, scripts and integrity inventory are retained there. Only tooling, tests and metadata/report files were added to Git's working directory; no source documents were added or staged.

## Acquired revisions and provenance

Selection follows [Task 3C.1](STAGE_2B2_REAL_WORLD_RAG_BENCHMARK_SPEC_20261111.md), including the exact six PostgreSQL pages and all four Git topics. Full URLs, source paths, commits, retrieval timestamps, licenses and both SHA-256 values for every unit are in the [metadata-only manifest](real-world-corpus-20261111-manifest.json). The authoritative staging manifest is `source-manifest.json`; paths inside it are relative to staging.

Prusa originals are linked by the manufacturer's [handbook catalogue](https://help.prusa3d.com/pl/article/podreczniki-druku_125045) through official localized product pages. Printed editions were checked on PDF page 2, independently of filenames and PDF creation dates:

| Unit | Printed edition/date | Pages | Actual applicability |
|---|---|---:|---|
| MK4S EN | 1.01 / 2024-09-26 | 66 | MK4S and MK3.9S |
| MMU3 EN | 1.03 / 2025-05-15 | 56 | MMU3 with MK3S+, MK3.5/S, MK3.9/S, MK4/S and CORE One |
| MK4 DE | 1.03 / 2023-09-04 | 69 | MK4 and MK3.9 |
| XL DE | 1.06 / 2026-01-22 | 85 | Assembled/semi-assembled, single-tool and multi-tool XL |
| MINI/MINI+ PL | 1.09 / 2022-04-05 | 58 | MINI/MINI+; cover explicitly names MINI+ |
| MK3S/MK3S+ PL | 3.17 / 2021-04-21 | 84 | Both products; cover names MK3S+ |

These are dated handbooks, not guarantees of compatibility with today's firmware. They generally instruct updating firmware rather than pinning one firmware build. The MK3S PDF's 2022 metadata does not replace its printed 2021 edition date.

Pro Git second edition repositories and full pinned commits:

| Language | Official translation repository | Commit |
|---|---|---|
| EN | [progit/progit2](https://github.com/progit/progit2) | `a013e3230a1207cfa5ae94d28ba7d2021063c337` |
| PL | [progit2-pl/progit2-pl](https://github.com/progit2-pl/progit2-pl) | `3a939c84461d254478a87749d43bed97ada37602` |
| DE | [progit/progit2-de](https://github.com/progit/progit2-de) | `9a8204ef167584e5b703eccbce5d4e81a7cdc86b` |

Each repository supplies all four complete files: `book/01-introduction/sections/first-time-setup.asc`, `book/08-customizing-git/sections/config.asc`, `book/03-git-branching/sections/remote-branches.asc`, and `book/07-git-tools/sections/submodules.asc`. Git blob identities were independently recomputed against pinned tree metadata. Official rendered HTML snapshots and referenced figures are also retained. Normalization uses the pinned AsciiDoc files; the live site's rendering is not falsely identified as the same commit.

PostgreSQL pins:

| Units | Source revision |
|---|---|
| v17 continuous archiving, backup overview, recovery configuration migration | `REL_17_10`, commit `25c49f3a4a742ba283f5cc43cc7f1d361552e917` |
| v17 WAL parameters | `REL_17_STABLE`, commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48` |
| v11 continuous archiving | `REL_11_22`, commit `fd851f9e4a13d81cccc4ac5d6059d732c7518111` |
| v12 release notes | `REL_12_22`, commit `498f30a8b7025a2a7bd3715acc1d1692122ba542`; document describes release 12.0 |

**WAL revision caveat:** the official `/docs/17/` page includes a documentation correction about `on` being a historical spelling of `pglz`, absent from `REL_17_10`. The original page was kept unchanged and matched to the full stable-branch commit above; the tag remains recorded as the released baseline. This is a PostgreSQL 17 documentation snapshot, not a claim that it is exactly the released 17.10 manual. If a released-tag-only corpus is required, approve acquisition of a corresponding released rendering before freezing. No such replacement was made.

The backup unit is the complete `backup.html` overview, including its published table of contents. Linked SQL-dump and file-system-backup chapters were not silently added as extra units.

## Language and extraction verification

Nominal publication languages remain **12 EN / 6 DE / 6 PL**. Actual classification is **12 primarily EN, 6 primarily DE, 4 primarily PL, and 2 substantially mixed PL/EN**. Technical identifiers, command output and code are kept in their original language. Localized Prusa screenshots also contain English UI labels; the MK4 DE handbook has an English applicability heading on page 2.

The user explicitly approved retaining complete mixed Polish Git sections on 2026-11-11. `config.asc` changes to English at `core.whitespace` (source line 411); `submodules.asc` changes at “Working on a Project with Submodules” (line 199). Body-offset language maps distinguish prose, code/markup and whitespace. Screening identifies approximately 3,890 EN prose characters in Polish configuration and 14,191 in Polish submodules, excluding code/markup. These are agent-reviewed passage classifications, not independent bilingual human certification. The Polish first-time setup is also older/shorter than EN/DE and lacks their default-branch-name subsection; all original content was retained without backfilling.

Normalization and checks:

- **Git:** conservative syntax conversion preserves all source headings and every literal listing byte-for-byte as text. Figures are downloaded from the same commits. Source-line maps retain traceability; published cross-references are resolved from snapshots where available, with unresolved reference text left visible. Non-published index/style markup is removed. No prose was translated, paraphrased or shortened.
- **PostgreSQL:** the complete publisher section DOM, including nested subsections, is converted to Markdown. Navigation outside it is removed; links become absolute; all tables are represented explicitly. All 607 source paragraphs match the rendered prose under word/whitespace normalization, allowing generated references/entities; all 69 headings and all 24 preformatted blocks pass preservation checks. Source paragraph comparison is not a byte identity claim for generated HTML. One original-versus-normalized duplicate-body check found no exact duplicate units.
- **Prusa:** all **418 original PDF pages** were extracted with pypdf and independently compared with pdfplumber. Plain text, layout extraction, font/geometry records and image coordinates are retained per page. Original page maps are complete; PDF heading recovery is partial. Low-agreement pages are recorded. XL page 7 was visually confirmed blank, rather than treated as missing content.

**PDF admission failure:** eight rendered page samples confirm missing screenshot callout relationships, flattened nested LCD menus, and missing warning/information-box boundaries or image-dependent alignment cues. For example, MK3S PL page 35 retains temperature values but loses the certified menu hierarchy; XL DE page 23 depends on colored image marks. These defects were not hidden by cropping or invented descriptions. All six Markdown copies are marked `acquired-normalized-unsuitable-for-freeze`. The samples do not certify unsampled pages. See staging `verification/pdf-visual-review.json` and `extraction/*.json`.

Tool versions: Python **3.14.7**, html2text **2025.4.15**; bundled PDF Python **3.12.14**, pypdf **6.21.4**, pdfplumber **0.11.9**, Poppler **26.07.0**. Output is UTF-8/LF. No packages, infrastructure or AI models were installed. Transformation/tool records and exact script hashes accompany the manifest.

## Actual size and parser sizing

| Unit ID | Body characters | Legacy / structure-v2 chunks |
|---|---:|---:|
| prusa-mk4s-en | 116322 | 184 / 177 |
| prusa-mmu3-en | 86016 | 135 / 130 |
| prusa-mk4-de | 132704 | 207 / 197 |
| prusa-xl-de | 167984 | 258 / 250 |
| prusa-mini-pl | 106262 | 169 / 160 |
| prusa-mk3s-pl | 140082 | 230 / 227 |
| progit-first-time-setup-en | 6245 | 13 / 13 |
| progit-config-en | 21003 | 42 / 39 |
| progit-remote-branches-en | 13652 | 24 / 26 |
| progit-submodules-en | 41439 | 74 / 76 |
| progit-first-time-setup-pl | 3845 | 7 / 7 |
| progit-config-pl | 21669 | 42 / 38 |
| progit-remote-branches-pl | 13190 | 22 / 24 |
| progit-submodules-pl | 34745 | 60 / 62 |
| progit-first-time-setup-de | 7247 | 13 / 14 |
| progit-config-de | 23959 | 45 / 41 |
| progit-remote-branches-de | 15917 | 27 / 27 |
| progit-submodules-de | 45574 | 81 / 83 |
| postgresql-17-continuous-archiving | 48612 | 81 / 80 |
| postgresql-17-runtime-config-wal | 47937 | 76 / 76 |
| postgresql-17-backup | 2094 | 4 / 3 |
| postgresql-17-recovery-config | 1486 | 2 / 3 |
| postgresql-11-continuous-archiving | 45979 | 78 / 77 |
| postgresql-12-release-12 | 71249 | 115 / 117 |
| **Total** | **1215212** | **1989 / 1947** |

Including YAML metadata: **1,221,450 characters / 1,242,273 UTF-8 bytes**. Original unit files total **89,422,084 bytes**; complete staging, including provenance, extraction and QA, occupies **118,036,410 bytes** at inventory creation. **13 complete units exceed 30,000 body characters.** The proposed 0.8-1.6 million-character range is met without cropping. Counts are actual dry parser outputs at size 1,000 / legacy overlap 200, useful as future indexing estimates; no embeddings or indexes were created. Both remain below the 3,000-chunk review threshold. PDF remediation can change these counts.

The 18 text units alone contain **465,842 body characters**. Dropping the manuals would therefore change the approved scope and miss the size range; it is not an approved shortcut. The full selection provides real long-document and multilingual material, complementary configuration/procedure documents and historical PostgreSQL version conflicts. Six intent families with evidence ten chunks apart cannot be certified at acquisition without the later question/evidence work; no such labels or performance claims were created here.

## Compatibility, licenses and acquisition failures

Reviewed `knowledge_base.py`, Markdown/contextual chunkers, note/frontmatter parsing, `rag_baseline.py`, the isolated runner and relevant unit tests. Existing ingestion accepts the files and preserves recognized title/type/status metadata. It does **not** automatically carry arbitrary `source_id`, language or revision fields into chunk metadata: Task 3C.2B needs an evaluation-only join from stable filename/source ID to the external manifest. Page/section offsets are mapped before indexing. No production loader, routing or model configuration was modified.

- **Prusa:** no handbook-specific redistribution grant was identified. Hardware/firmware GPL notices do not establish a handbook license. Originals and normalized copies remain local research artifacts, excluded from Git and distribution.
- **Pro Git:** [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/), with language-specific notices archived. Preserve attribution, noncommercial and ShareAlike requirements; do not assume commercial reuse is authorized.
- **PostgreSQL:** [PostgreSQL License](https://www.postgresql.org/about/licence/), with the exact pinned COPYRIGHT files retained. Preserve required notices.

Initial guesses for the Polish Git repository and two German slugs returned 404; official book links supplied the correct destinations. Historical PostgreSQL uses `configure.in` rather than `configure.ac`. These were corrected provenance lookups, not source substitutions. A sandboxed network attempt was restricted; authorized downloads succeeded after escalation. All 24 final acquisitions succeeded. Failed attempts and resolutions are recorded in staging `verification/acquisition-failures.json`.

## Reproducibility and validation

Offline integrity check from this checkout:

```powershell
python -B tools/corpus/verify_corpus.py --root C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111
```

The check verifies all **289 inventoried files**, both hashes for all 24 units, and missing/changed/unrecorded files, without downloading. Inventory trust anchors:

- `source-manifest.json`: `3b25c6c001479e8c8f05847058f884f0c38093d6db0f37fa628e8ef6359e65a3`
- `integrity-inventory.json`: `7ce040ed0bf8cda84d6a86a0bbb4c06497e72899258ea40135dd8dce30cd874b`

`download-plan.json` records exact URLs and expected original bytes. `acquire_real_world.py --replay-plan ... --root NEW_EXTERNAL_ROOT` re-fetches only those URLs and rejects changed bytes. Immutable Git URLs are commit-pinned; mutable publisher pages/PDFs may eventually fail this strict replay, so retained originals are essential. Staging README documents regeneration; archived extraction/normalization scripts and the reviewed LAEW parsers/specification have recorded SHA-256 values. Reacquisition restores downloaded bytes, not the original HTTP retrieval times or derived metadata.

```powershell
$env:LAEW_PUBLIC_CORPUS_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111'
python -B scripts/run_isolated.py pytest tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q
```

**17 passed in 3.26 s.** The initial AppContainer run failed before test bodies because its temporary directory denied child creation; the same isolated runner succeeded after escalation. Tests use offline boundaries; corpus ingestion is dry (`embed=False`), with no ChromaDB construction. Existing parser unit tests use their existing local stub fixtures. No public-corpus retrieval benchmark, questions, evidence labels, generated answers, private Memory/vault access or generative-model calls occurred.

## Readiness and changed files

**Decision required before freezing:** remediate and verify the six existing PDF normalizations, or explicitly revise the source selection/admission requirements. Retaining and repairing these exact originals is the recommended next step. The mixed-PL decision is already approved and recorded; do not ask for it again. Review the WAL stable-commit caveat if released-tag-only documentation is required. No replacement source is proposed as already accepted, and no unavailable unit needs substitution.

This task added this report, `real-world-corpus-20261111-manifest.json`, `real-world-corpus-20261111-git-status.txt`, `tests/evaluation/test_real_world_corpus.py`, and seven files in `tools/corpus/`: acquisition, PDF extraction, normalization, content audit, language screening, finalization and integrity verification. No existing tracked file was edited by this task. Pre-existing `M docker-compose.yml`, `M docs/README.md` and other untracked work remain. The [full final Git status](real-world-corpus-20261111-git-status.txt) records the exact paths. No Git add, commit, push, reset or clean was performed.
