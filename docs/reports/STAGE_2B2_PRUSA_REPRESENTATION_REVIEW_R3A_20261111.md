---
type: report
title: Prusa corpus representation review - Task 3C.2A-R3A
date: 2026-11-11
status: review-complete-source-once-alternative-proposed-no-admission
scope: full R2 boundary diagnosis, seven excerpt comparisons, existing High-flag policy review
---

# Decision

**R2 materially confounds a fair legacy versus structure-v2 chunking comparison.** Keep it as a preparation/regression artifact, not the proposed primary benchmark representation. A less fragmented, source-faithful **source-once Markdown** representation is feasible on the tested sections. It preserves source material and applicability maps without making every chunk self-contained. Its remaining context losses are visible chunking challenges, not a reason to manufacture identical boundaries.

No full corpus was regenerated. Seven corresponding section/group excerpt pairs from all six manuals are in `C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3a-v1` (`r2/`, `natural/`, `maps/`, `chunk-diagnostics/`). This is a representation review, not corpus admission/freezing, a retrieval experiment or a new comparison arm. No questions or evidence labels were created.

# Why exactly 3,980 chunks

Dry runs of the unchanged `KnowledgeBase._load_file(..., embed=False)` establish:

- R2 has **3,318 unique H6 packets**, each bounded to 1,000 characters, plus **662 original heading records** with derived boundary comments: **3,318 + 662 = 3,980** chunks under **each** strategy.
- All six manuals have the **same ordered chunk text after trimming edge whitespace**, not merely equal totals. All R2 structure-v2 synthetic-context counts are **zero**.
- Legacy splits at each H6 heading. Structure-v2 sees a distinct leaf path for each packet and cannot group adjacent packets. Boundary comments also prevent its heading-only-parent grouping from absorbing original headings. It therefore rarely encounters its intended long sections, tables or contextual continuations.
- R2 supplies reviewed dependencies and table identities as repeated source text before either strategy operates. That largely replaces the behavior the benchmark should observe. Full menu paths also pre-expand ancestor context; cell packets bypass native table handling.

This does not prove identical embeddings or retrieval: raw whitespace, IDs and metadata differ, and neither was evaluated. It does establish a substantial representation confound. R2's boundary/markup characters are **202,953** of **1,071,414** characters; a further **48,678** characters are derived repetition blocks. These are not all publisher prose.

# One alternative, chosen before measuring

The proposed source-once representation uses only the source-recovered section/subsection headings, paragraphs and numbered steps, in source order. Original callouts occur **once**, as blockquotes in their published positions. LCD items use their source labels and actual nested indentation rather than repeating the entire ancestor path per item. Tables retain the native row/column matrix; a Markdown header separator is used only where the source header was verified. No H6 packet IDs, per-packet `[Source]` labels, per-cell headings or chunk-size-dependent repetition is introduced.

Source block IDs, page numbers, line ownership, cell ranges/hashes, inherited reviewed applicability edges and literal condition spans remain in **sidecars**, outside retrieval text. Figure placeholders explicitly state that visual information is unavailable in text; sidecars retain original figure/source-page attribution. Published captions and surrounding prose remain. This does not invent graphical descriptions or resolve instructions requiring those graphics.

The production loader **does not consume these sidecars** or automatically deliver their safety dependencies. Applicability is preserved at document/provenance level; full safety context is not promised in each resulting chunk. Source warnings must not be deleted, moved to another procedure or mistaken for executable advice. A correct source can legitimately require unioning several chunks. Future evaluation must distinguish that retrieval/context challenge from a corrupt or incomplete source, under the already approved source-span evaluation protocol.

# Measured comparison

Samples were selected for known layout types before measurement, not randomly and not from retrieval outcomes. They include complete source-numbered sections/groups; page numbers identify where those sections occur, not arbitrary page crops. Source order and the same selected primary blocks are used in both representations.

| Source sections / PDF pages | R2 characters | R2 chunks L / V2 | Natural characters | Natural chunks L / V2 |
|---|---:|---:|---:|---:|
| MK3S PL 7.2.9 / 35–36 | 6,762 | 9 / 9 | 2,628 | 5 / 4 |
| XL DE 4.3 / 23–24 | 17,304 | 21 / 21 | 2,025 | 3 / 4 |
| MK4S EN 4.3–4.4 / 18–19 | 11,425 | 18 / 18 | 3,423 | 6 / 6 |
| MK4 DE 4.3–4.4 / 21–22 | 16,674 | 24 / 24 | 4,276 | 7 / 7 |
| MINI PL 9.1 / 42–45 | 15,873 | 23 / 23 | 3,790 | 6 / 6 |
| MMU3 EN 2.5–2.6 / 22 | 4,716 | 20 / 20 | 2,642 | 4 / 4 |
| MMU3 EN 6.2.2 / 39–40 | 4,964 | 31 / 31 | 1,818 | 3 / 3 |
| **Total** | **77,718** | **146 / 146** | **20,602** | **34 / 34** |

Natural Markdown reduces sample characters by **73.5%** and chunks by **76.7%**. The two natural totals happen to cancel: MK3S favors fewer V2 chunks while XL favors fewer legacy chunks. **All seven natural examples have different primary source boundaries after whitespace trimming, and different delivered payload sequences.** Equal aggregate counts are therefore not evidence of forced equality.

| Representation / strategy | Chunk min / median / max characters | Delivered characters | Strategy-added context or overlap | Approx. delivered tokens* |
|---|---:|---:|---:|---:|
| R2 / legacy | 55 / 600 / 997 | 77,404 | 0 overlap | 19,404 |
| R2 / V2 | 57 / 602 / 1,000 | 77,718 | 0 synthetic context | 19,487 |
| Natural / legacy | 103 / 799.5 / 984 | 25,034 | 4,454 overlapping source characters | 6,271 |
| Natural / V2 | 399 / 876.5 / 1,000 | 28,878 | 8,276 synthetic-context characters | 7,229 |

*Sizing proxy: sum of `ceil(chunk_characters/4)`, not tokenizer measurements or a multilingual token guarantee. Legacy edge-whitespace trimming explains why delivered-character differences are not exactly the overlap count. V2 prefixes are **40.2%** of the natural representation's size; **33/34** V2 chunks report limited context. R2 sample derived repetition blocks alone occupy **45,920 characters (59.1%)**. These deliberately warning-rich samples cover most existing R2 repetition and must **not** be extrapolated to full-corpus reduction ratios or used to choose a representation by apparent algorithm advantage.

## Safety and attribution trade-off

Using only the **inherited reviewed R2 relationships**, checked against actual payloads:

| Diagnostic | R2 legacy | R2 V2 | Natural legacy | Natural V2 |
|---|---:|---:|---:|---:|
| Complete dependency occurrences / required chunk-dependency checks | 176/176 | 176/176 | 17/61 | 19/62 |
| Procedural chunks carrying every inherited applicable dependency | 72/72 | 72/72 | 3/27 | 5/26 |
| All dependency source pieces available across the document | Yes | Yes | Yes | Yes |

These are **query-independent extraction/context diagnostics**, not gold evidence labels or retrieval/safety scores. Denominators change with boundaries, and R2's applicability coverage was already partial. The MMU purge table has no inherited procedural safety-dependency checks; that denominator is N/A, not a perfect safety score.

The natural MK3S menu illustrates a meaningful difference: its full shared note is visible in **1/5 legacy** versus **4/4 V2** menu-bearing chunks. XL 4.3 illustrates the limit: **neither** strategy carries the entire inherited warning set in every procedural chunk; V2's bounded introduction is insufficient. Both documents retain the warnings themselves. Repeating them per engineered packet conceals these differences while consuming context and adding retrieval candidates. Neither outcome authorizes safety-critical use of isolated chunks.

**94 source-block fidelity checks pass**, covering headings/prose, every selected menu label, native table cells and visual-unavailable markers. All source non-whitespace characters in each representation are covered by delivered primary spans; legacy alignments are exact and unambiguous in these excerpts. V2 source/context spans retain their own provenance. These checks are relative to retained R2 source blocks/PDF-object mappings, **not a new independent human certification of the originals**. No original-source language, technical value or version was intentionally changed. Original PDF hashes identify each sample's source.

# Review of the 388 High findings: proposed admission policy

**No finding was downgraded, cleared or admitted.** The R3A CSV lists every High page with unchanged priority and a proposed gate; JSON retains all 418 page records. Deduplicating flags per page matters: R2 has **32 merged-cell flag entries on 16 distinct pages**, and four complex-grid entries on two pages. Counting entries as defective pages would overstate the work. Lexical words such as “only” and covers containing rotated text are screening signals, not proof of corruption.

| Proposed first gate, mutually exclusive | Pages | Required decision |
|---|---:|---|
| Text/layout/extraction adjudication | 96 | Human checks source ordering, native/merged cells, units, qualifiers or extraction disagreement; includes possible detector false positives. |
| Applicability adjudication | 249 | Human checks procedure boundaries and genuine safety/condition scope; lexical presence alone is insufficient. Reuse a reviewed procedure-level decision only where its exact scope is documented. |
| Image-only flag, possible visual unavailability | 43 | Human verifies that a text-only availability declaration is truthful and that surrounding prose does not become misleading without the image. These are **candidates**, not approved downgrades. |
| **Existing High total** | **388** | **All pending.** |

The remaining ten Medium and twenty Low pages also remain uncertified. No automated retention-defect arrays were nonempty in the inherited audit; that does not exclude semantic defects or image-only text.

Proposed rules for a **text-only** benchmark, requiring approval before any admission:

1. **Block on actual text/meaning corruption:** missing/reordered technical steps, incorrect values/units, mismatched table headers/rows, lost negation or scope, fabricated graphical interpretation, wrong edition, or broken source attribution. Fix and verify, or explicitly quarantine the unresolved passage from usable textual support. Never silently accept a flattened pros/cons table as correct prose.
2. **Visual information need not be reconstructed:** a screenshot, flowchart, alignment target or first-layer photograph can remain unavailable with an explicit marker and original page attribution. A qualified human must decide whether nearby text is independently meaningful. Retaining an image link is not textual availability. Pure visual facts cannot later be presented as supported text-only evidence. This proposed coverage limitation must be declared before any questions/labels/results.
3. **Mandatory human review:** electrical/PDU instructions and symbols (XL 81), merged/borderless technical tables, safety-icon associations, unresolved prerequisite scope, pros/cons polarity (MK3S 16, XL 62), and extraction disagreements affecting procedural material. MK3S 35–36 and XL 23–24 retain their prior limited component reviews; they are not whole-page certifications. Covers or false menu/table detections may be disposed of quickly, with recorded reasons.
4. **Separate source validity from chunk completeness:** a warning present once in the correct source/procedure can be valid corpus material even when a particular chunk omits it. Missing it from a retrieved payload is then a system limitation. A sidecar dependency never counts as delivered evidence unless actually present in the permitted payload. No production renderer or warning-expansion change is proposed here.
5. Keep complete documents and authentic text. If an unresolved passage must be marked unusable, preserve it with an explicit availability status and obtain approval for the resulting benchmark coverage; do not crop it, replace it with an invented description or silently certify it. No statement that the entire manual is semantically reconstructed is required or supported.

# Resource threshold and bounded next work

The specification says to **stop and review before exceeding 3,000 chunks per chunker**. This is a resource gate, not a content-quality acceptance rule; the previous R2 report's “cap” wording was too strong. Do not truncate documents, change chunk size/overlap, or select a representation simply to get below 3,000. Choose a neutral representation before question creation, then approve measured time/storage limits separately.

For scale, retaining R2 for all 24 units would mean **4,786 chunks per strategy**, **9,572 chunk vectors** plus approximately 60 query inputs. At the specification's illustrative 1,024 float32 dimensions, raw chunk vectors are approximately **37.4 MiB**, excluding index/metadata overhead. Its assumed 0.25–0.75 seconds per input gives approximately **40–120 minutes** for 9,632 inputs, before cache savings or build overhead. These are planning calculations, not an embedding run or current performance promise. The seven excerpts cannot reliably predict natural full-corpus counts. Human QA should be budgeted by procedures/risk decisions, not by engineered chunk count.

Propose a **separately authorized, maximum eight-person-hour disposition cycle**, not a 418-page reconstruction:

- Up to **2 hours** to review the 43 image-only candidates and record unavailable/independently-usable/pending decisions. Stop on difficult cases rather than transcribe every figure.
- Up to **4 hours** to prioritize the 16 distinct merged-cell pages and 18 independent-extraction disagreements, including XL 81 and the known pros/cons layouts. Many detections may be nontechnical or already explained; unresolved technical relationships remain blocked. This is a triage budget, not a promise to repair every case.
- Up to **2 hours** to review a bounded set of at most twelve procedure/applicability groups across EN/PL/DE, focusing on safety and cross-page restrictions. The 249-page applicability queue is not implicitly cleared by reviewing twelve groups.

At that checkpoint, report actual disposition counts, unresolved source IDs/pages and spent time. Decide whether the proposed text-only coverage is adequate, further targeted work is justified, or the scope needs an approved revision. Only then consider a separately authorized full source-once candidate regeneration and measured build budget. Do not expand this into comprehensive manual reconstruction. Neither a full regeneration nor admission/freezing is authorized by this report; Task 3C.2B remains untouched.

# Reproducibility, tests and changed files

**75 tests passed in 5.58s**, via `scripts/run_isolated.py`: R3A regressions plus the existing R2, R1, corpus and both chunker suites. Tests cover equality diagnosis, source retention/cell ranges, differing natural boundaries/payloads, real dependency visibility, exact input integrity, and unchanged High priorities. No store, embedding service or generative inference was invoked.

Set `LAEW_PUBLIC_CORPUS_ROOT`, `LAEW_PRUSA_R1_ROOT`, `LAEW_PRUSA_R2_ROOT` as in R2, plus `LAEW_PRUSA_R3A_ROOT` to the new R3A path, then run:

```powershell
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r3a.py tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

Read-only offline integrity check (75 R3A files, 1,297 R2 files, 289 accepted files and 87 R1 files):

```powershell
python -B tools/corpus/review_prusa_r3a.py --r2 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r2-v1' --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3a-v1' --verify --expected-inventory-sha dd7d52fef9b733912c990aac6215c226841bc65bcf0277dd3677f1d3f6c05dfa
```

R3A `README.md`, `review-manifest.json`, source maps, chunk traces and code snapshots document regeneration into a new external path. R2's original inventory anchor remains `3fc630e9ca60a06223da8ec8198b13f7b3d51c98193271bab61007e2198ce9fb`. The accepted mixed PL/EN sources, pinned PostgreSQL WAL revision and original PDFs are untouched. Handbook excerpts, maps and payload text remain local; no redistribution authorization is asserted.

Added: `tools/corpus/review_prusa_r3a.py`, `tests/evaluation/test_prusa_pdf_r3a.py`, this report, `docs/reports/prusa-pdf-r3a-20261111-review.json` (metadata only), and `docs/reports/prusa-pdf-r3a-20261111-git-status.txt`. No existing R1/R2 or production source file was edited. The pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`; unrelated untracked work remains. No add/commit/push/reset/clean occurred. Stop before full regeneration or further remediation/admission decisions.
