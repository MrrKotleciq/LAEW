---
type: report
title: Human observations and restricted corpus admission recommendation - Task 3C.2A-R3D
date: 2026-11-12
status: recommendation-prepared-not-admitted-not-frozen
scope: 15 supplied human page/component observations; no new graphical reconstruction
---

# Recommendation

**Approve a restricted text-only scope in a separate decision. Further reconstruction of every Prusa graphic is unnecessary for that scope. Do not yet admit or freeze the corpus.** Keep all 24 complete R3C-v2 source-once candidates unchanged. Treat absent graphics and unresolved technical relationships as unavailable support, and unreviewed material as unjudged. These restrictions concern evidence validity, not document cropping or a new retrieval algorithm.

Read the R3A, R3B and R3C reports in order, the benchmark specification, R3C source manifest, availability/gate/risk registers, exact page/block maps and reviewed applicability sidecars. Offline verification confirms the pinned R3C inventory and historical input chain. Structural consistency is not semantic certification. The user's current statement that live provider inference was previously confirmed supersedes the specification's historical access uncertainty; no provider check or inference was needed here.

New external metadata workspace: **`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-r3d-v1`**, outside Git and Obsidian. It references `stage-2b2-real-world-20261111-r3c-v2`; it contains no regenerated PDFs, Markdown, questions, gold labels, vectors or indexes.

**R3E documentation clarification, 2026-11-12:** references below to `readiness.json` mean the external [historical R3D readiness file](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3d-v1/readiness.json), not `docs/reports/readiness.json`. The file exists and matches its original inventory hash; no missing external file was reproduced or recreated. Bare filenames made the location ambiguous. The user subsequently approved the restricted policy in Task R3E; R3D's pending-approval statements remain its historical assessment. See the [R3E preflight report](STAGE_2B2_ADMISSION_FREEZE_PREFLIGHT_R3E_20261112.md) and [current R3E readiness](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/readiness.json). Freeze execution remains separately approval-gated.

# Records and provenance

- `human-review-decisions.json`: 15 human-origin observations, with separately marked agent reconciliation, physical PDF page, revision, original/normalized/map/raster hashes, exact block IDs and hashed Unicode ranges.
- `page-reconciliation.csv`: all 15 reviewed gates; `restricted-regions.json`: the nine inherited limitations plus the separate XL DE page 83 identification gate, **ten restricted components, not ten newly discovered defects**.
- `inherited-availability-register.json`, `inherited-mandatory-human-review-gates.json`, `inherited-unresolved-risk-register.json`, `inherited-warning-applicability-reviewed.json`: byte-identical historical registers. The overlay records responses without rewriting their historical pending statuses.
- `uninspected-high.json`: all 329 unchanged uninspected High records; `admission-policy-proposal.json` and `readiness.json`: proposed rules and outstanding requirements.
- `review_prusa_r3d.py`, `README.md`, `r3d-integrity-inventory.json`: reproduction snapshot, instructions and integrity inventory.

The requesting user's observations are direct human input from section 4 of the current instruction. Identity, credentials and time of actual review were not supplied; review timestamps are **null**. The packaging date is 2026-11-12, not an invented review date. No signature or independent expert certification is asserted. The user inspected PDF components; a new human PDF-to-Markdown comparison is **not** claimed. Existing R3B repairs/R3C checks remain agent-origin.

# Reconciliation of the 15 physical PDF pages

All references match the correct source ID, original PDF hash, retained page raster and R3C normalized region. Page numbers are **1-based physical PDF pages**, not printed labels. Machine-readable ranges use LF-normalized full-file Unicode offsets **[start,end)**, hashed as UTF-8. The JSON retains each disjoint range rather than treating gaps as inspected.

| Source / PDF page | User observation | Recorded scope and consequence |
|---|---|---|
| MK4 DE 7 | Table: no visible errors | Repaired product table only, 19607–20375; neighboring prose is not certified. |
| MK4 DE 8 | Table: no visible errors | Repaired product table only, 21437–22207. |
| MK4S EN 6 | Table: no visible errors | Repaired shared-product table only, 18461–19551; retain both product identities/common values. |
| MMU3 EN 7 | Table: no visible errors | Repaired product table only, 15699–16262. |
| XL DE 9 | Table: no visible errors | Repaired product table only, 23109–24041; starred applicability footnote remains required context, 24041–24106. |
| XL DE 35 | Readable image text, different language | Screenshot remains non-extracted/unavailable. Exact reset blocks b7–b9; complete reset/confirmation support remains unavailable. Section 4.13 example models is outside this restriction. |
| MK4 DE 22 | Readable image text, different language | Retain selftest/sensor-startup limitation and original image markers; no inferred startup state. |
| MK4 DE 33 | Readable image text, different language | Reset blocks b8–b9, 71762–72391. Screenshot-only qualifier remains unavailable; neighboring example-model text is not quarantined. |
| MK4S EN 19 | Readable image text, same language | Same-language readability still supplies no extracted image text. Complete sensor-test startup remains unavailable. |
| MK3S PL 16 | “nie da się odczytać” | Column block 28753–29475: graphical polarity remains unresolved; no invented advantages/disadvantages. |
| MK3S PL 37 | “nie da się odczytać” | Blocks b7–b8, 70983–71323: icon/callout association and instruction scope remain unresolved. Do not turn isolated feed-rate values into complete operating guidance. |
| MINI PL 45 | “nie da się odczytać” | Column block 89514–90320: section 9.2 graphical polarity remains unresolved. This does not dispose of section 9.1. |
| MMU3 EN 6 | “nie da się odczytać” | Blocks b2–b7, 14882–15674: literal descriptions survive; symbol-to-description/action mapping is unavailable. |
| XL DE 81 | “nie da się odczytać” | Symbol table b4, 174340–174597: electrical symbol meaning/association remains unresolved. Separate product table 174624–175276 was **not** one of the five confirmed table checks. |
| XL DE 83 | “nie da się odczytać” | Three inherited figure ranges plus five literal numbered-label ranges in the overlay: names survive, but label-to-part/terminal geometry, protective-earth identification and connections are not verified. |

**15/15 human responses recorded: five scoped table observations, four human-readable but non-extracted images, six unavailable/unresolved observations.** Five table-check requests have received a limited positive observation; the other ten have received a disposition supporting proposed unavailability/restriction. No repeat of these observations is needed. **Zero pages are completely semantically certified, zero original priorities are cleared, and no scope restriction is approved automatically.** All nine inherited availability markers remain unchanged. XL 83 receives a sidecar restriction, without adding a new marker to R3C Markdown.

“Different language” is recorded without guessing which language. No image transcription, OCR, translation or graphical description was added. “Cannot be read” is not verification of the missing technical relation, nor a claim that all native prose on that page is unreadable.

# Proposed admission rules and actual blockers

1. **Potential textual support:** literal source prose, native table relationships and reviewed conditions can support a bounded claim only with correct product/version, source attribution and exact source spans. Five table observations supplement prior agent checks, with original units, labels, shared values and footnotes retained. Independently meaningful neighboring prose remains a candidate; no whole-page approval follows.
2. **Unavailable support:** image pixels/links, screenshot-only words, graphical polarity, symbol associations, terminal geometry and complete image-dependent reset/selftest procedures cannot count as textual evidence. Derived limitation/layout notes and applicability sidecars document QA; they are not publisher technical facts or delivered LLM evidence. Do not infer a visual fact from a caption alone.
3. **Procedure completeness:** valid text may require multiple chunks/pages. Preserve actual warning/condition scope, source order and prerequisites. A warning present once in the source is not automatically present in a retrieved payload. Missing delivered context is a retrieval/delivery limitation only when adequate valid textual support exists in the corpus; an unavailable visual requirement is a source-coverage limitation.
4. **Real blockers:** incorrect values/units, lost negation, interleaved steps, false table relationships, unresolved prerequisite scope or ambiguous attribution block the affected use. Repair and verify in a new version, or approve a precise support restriction. Unavailability of graphics alone does not require reconstructing them. Complete electrical/PDU or symbol-dependent operational claims stay blocked unless qualified targeted review expands that scope.
5. **Open priorities:** retain **0 Critical / 388 High / 10 Medium / 20 Low**. All **329 uninspected High**, **9 uninspected Medium** and **20 uninspected Low** pages remain unjudged; the other component reviews also do not clear whole-page flags. Before using an open/unjudged span as evidence, perform targeted source/normalized-text/context QA without retrieval output. Otherwise avoid that topic or leave relevance unjudged. A full 329-page clearance is not a prerequisite for approving restricted coverage.
6. **Equal corpus and honest scoring:** after separate authorization, preserve the same complete 24-unit universe across A/B/C; no question-dependent suppression of documents/chunks. Unavailable/unjudged passages may still be retrieved: disclose their exposure separately, without treating them as established support or automatically irrelevant. Incomplete review is not proof that an answer is absent. Later unsupported labels require whole-corpus/version/translation review. Unexpected valid evidence requires a versioned, arm-blind correction across all arms.
7. **Provenance and coverage:** preserve revisions/licenses, authentic mixed PL/EN Git passages and WAL commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48`. Record actual evidence language; do not translate sources to satisfy quotas. The primary representation stays source-once. Quotas and answerable coverage across six manuals must be verified during separately authorized dataset preparation; infeasibility requires a design/scope decision, not invented facts.

Thus the ten known relations can remain explicitly unavailable. The untouched risk queue prevents claiming comprehensive semantic admission; it does not force comprehensive graphic reconstruction. Any unresolved relation actually required by a future selected task remains a blocker for that task's answerability. This is corpus QA and a scope recommendation, not question-specific gold evidence or an admission whitelist.

# Outstanding requirements and readiness

**Ready now:** admission/scope approval review. No further request to repeat the 15 decisions. Corpus preparation can end with approved unavailability rather than renewed manual reconstruction.

**Before a restricted corpus freeze:** approve the proposed coverage/unjudged-material policy; approve the ten mapped relationship limits; retain all open priorities; recheck exact source/overlay integrity and preserved revision/license/language metadata; authorize a separate versioned freeze manifest. No corpus has yet been admitted or frozen. All 24 candidates and existing source-once metrics remain intact: 1,281,131 body characters, 2,171 legacy / 2,185 structure-v2 chunks; no resource-trigger override is required.

**Before Task 3C.2B:** separately authorize question/evidence preparation and assign the domain, bilingual and independent second-review roles required by the specification. Targeted QA is needed for every intended evidence span and its warning/condition dependencies, especially open priorities; XL 81's product table has no positive human table observation here. Complete procedures involving the ten restrictions require qualified interpretation **or remain out of supported scope**. This does not demand broad technical certification of all retained passages.

**Before dataset seal or evaluation:** establish the 60-question/20-family design, six-manual answerability, language/cross-language and distance quotas, evidence alternatives, reviewer provenance and 12-pilot/48-sealed isolation under the approved restricted scope. These are future checks, not work started here. Indexing, retrieval/answer benchmarks and the maximum-36-call live pilot each remain outside this authorization.

# Validation, integrity and repository state

**134 tests passed in 21.41s** via `scripts/run_isolated.py`: ten new R3D cases plus the 124 existing R3C/R3B/R3A/R2/R1/acquisition/chunker cases. New tests reject wrong/missing page gates, changed component offsets, invalid attribution, wrong trust anchors, overwritten outputs and tampered records; verify page/component scope, XL table footnote and PDU label context; and prevent human readability/no-error observations from becoming page/expert certification. No embedding, store or inference is invoked.

With the existing corpus environment variables set (`LAEW_PUBLIC_CORPUS_ROOT`, `LAEW_PRUSA_R1_ROOT`, `LAEW_PRUSA_R2_ROOT`, `LAEW_PRUSA_R3A_ROOT`, `LAEW_PRUSA_R3B_ROOT`, `LAEW_PRUSA_R3C_ROOT`):

```powershell
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r3d.py tests/evaluation/test_prusa_pdf_r3c.py tests/evaluation/test_prusa_pdf_r3b.py tests/evaluation/test_prusa_pdf_r3a.py tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

R3D has **12 inventoried files plus its inventory**; SHA-256 anchor **`07cb927d96d0153681f0034aed8502e46ca0334fcb4e1305b1b0e3a4b90f7d0f`**. Read-only verification passed:

```powershell
python -B tools/corpus/review_prusa_r3d.py --r3c 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3c-v2' --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-r3d-v1' --verify --expected-inventory-sha 07cb927d96d0153681f0034aed8502e46ca0334fcb4e1305b1b0e3a4b90f7d0f
```

The verifier also confirms unchanged **750 R3C / 203 R3B / 75 R3A / 1,297 R2 / 87 R1 / 289 original acquisition files**, all 24 source identities and 18 byte-identical Git/PostgreSQL files, using the report-pinned historical inventory chain. An initial verification command supplied an incorrect abbreviated anchor and was rejected before verification; the full anchor above then passed. Hash verification does not certify semantics.

Added in the repository: `tools/corpus/review_prusa_r3d.py`, `tests/evaluation/test_prusa_pdf_r3d.py`, this report, `prusa-pdf-r3d-20261112-review.json`, `prusa-pdf-r3d-20261112-initial-state.json`, `prusa-pdf-r3d-20261112-final-state.json` and `prusa-pdf-r3d-20261112-git-status.txt`. Report JSON contains metadata only; source-bearing material stays external. Initial/final snapshots compare every pre-existing dirty/untracked file hash. Pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`; unrelated uncommitted work is preserved.

No production code, chunker, RAG setting, prior snapshot or source was changed. No Git add/commit/push/reset/clean, question/gold generation, indexing, embedding or live inference occurred. Production remains legacy/cosine/K2/top2/500; proposed experimental arms remain A/B/C as specified. **Stop at this recommendation; obtain approval before admission/freezing, Task 3C.2B or any benchmark.**
