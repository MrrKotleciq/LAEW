---
type: report
title: Real-world multilingual pilot dataset preparation - Task 3C.2B.1
date: 2026-11-12
status: agent-draft-content-frozen-human-review-pending
scope: four pilot families, twelve questions and draft source-span labels only
---

# Result

Prepared **four operational pilot families / twelve EN/PL/DE questions**, nine answerable variants and three insufficiently specified variants. Final workspace: **`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-pilot-20261112-v3`**, outside Git, Obsidian and the frozen corpus. All questions, facts, labels and QA judgments are **agent-origin drafts**. No human review, independent agreement, domain-expert authorship or evaluation readiness is asserted.

| Family | Category | Scope | Evidence |
|---|---|---|---|
| P01 | Single-document technical configuration | Repository-specific Git author identity | Three coherent alternatives: pinned EN, PL or DE first-time-setup section; each sufficient set uses one source unit. |
| P02 | Multi-section procedure with conditions | MINI+ smooth-sheet replacement/preparation | Sections 5.3 and 9.1, physical PDF pages 18 and 42–44. Textual preparation/condition checks only. |
| P03 | Complementary multi-document reasoning | PostgreSQL 17 incremental-backup retention planning | Backup section 25.3.3 plus WAL configuration 19.5.7; both source units contribute required facts. |
| P04 | Insufficiently specified / version ambiguity | Recovery-runbook applicability without the server major version | Supported conditional explanations from versioned PostgreSQL guidance; request clarification rather than assume the runtime version. |

Each family has exactly one question in each language with shared target/assumptions and draft fact requirements. The variants were agent-authored, not supplied by a domain reviewer or independently translated. Their naturalness and semantic equivalence still require bilingual human validation.

# Review package and labels

- [Main review package](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/review.html): all twelve questions, proposed answer facts, alternatives, conditions, uncertainties, exact source excerpts and links to frozen originals/page rasters.
- [Questions only](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/questions.json), [draft labels](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/draft-labels.json), and [evidence registry](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/evidence-spans.json).
- [Blind second-labeling package](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/blind-second-review.html): questions and all 24 source-unit links, without the proposed facts, labels or selected excerpts. A second reviewer must use this before exposure to the main package; merely opening it does not establish independence.
- [Reviewer requirements](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/review-requirements.json), [source QA](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/targeted-source-qa.json), [corpus-wide inspection](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/corpus-wide-inspection.json) and [split reservation](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/split-reservation.json).

The 12 label records contain required facts, alternative sufficient sets or clarification-support alternatives, product/version assumptions, warnings, exceptions, actual evidence languages and expected limitations. The shared registry resolves each reference to its exact source ID, revision/commit, original document/page/section/line or HTML location, source/map attribution, normalized full-file **Unicode [start,end)** range, excerpt and UTF-8 SHA-256. **No evidence uses chunk IDs.**

For P04, the full request remains insufficiently specified; positive-evidence recall/completeness is N/A. Its facts support clarification and version-conditional explanation, not an unqualified procedure for the unidentified server. No corpus-absence/world-absence or negative-relevance labels were fabricated.

# Integrity and targeted source QA

Before source use and after dataset construction, verified all **774 frozen copy entries and the exact 777-file set**, including approved manifest `5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19` and receipt `cc46d666407c74beec2bf0832bfcf4a9f62117db608f53c2ef339e5e28d7759c`. Evidence was read only from that frozen copy; no prior acquisition/staging corpus or live publisher source supplied evidence. The frozen corpus was never edited.

Targeted QA covers **25 spans from nine source units**:

- Six Pro Git spans: exact selected pinned AsciiDoc-line versus mapped Markdown comparisons, allowing only whitespace/code-fence presentation changes. Body-relative maps are explicitly rebased to full-file coordinates. No translation fallback was silently relabeled.
- Six Prusa spans: agent compared complete preserved page rasters 18, 42, 43 and 44 with selected blocks, the cross-page cleaning continuation, table headers/selected smooth-sheet row and the sheet-change callout. Images establish the QA comparison only; no graphical meaning or image text was added as evidence. Row/material scope, cool-surface/burn condition and conditional calibration applicability are retained. Page 18 was in the inherited uninspected High queue; this new component QA does **not** clear that page or rewrite the queue.
- Thirteen PostgreSQL spans: exact original frozen HTML block visible text versus normalized Markdown visible text; original anchors, actual heading paths and raw original locations are recorded. Scenario-derived comparisons and conditional conclusions remain agent drafts. WAL metadata retains approved commit `220b5263dbb71bbe2966c6d47c0c456c14ed4e48`.

Every selected span is checked against all ten approved restricted-region/component/context ranges: **zero overlaps**. Derived placeholders and availability text cannot be evidence. All nine inherited availability limits, fifteen human component observations, **329 inherited uninspected High findings and all other priorities remain unchanged**. Selected neighboring literal text is not whole-page certification.

A literal, unranked content scan covers all 24 frozen units for identity, sheet and PostgreSQL version/backup terms. It is an inspection/navigation aid, not RAG retrieval or a relevance judgment. P04 is grounded in an explicitly missing runtime version and conflicting version-conditional procedures, not a failed initial search. Full human corpus/version-sibling adjudication and further alternative-passage review remain pending; alternatives are not claimed exhaustive. Cross-language-required status is deliberately unadjudicated rather than inferred from the selected source language alone.

# Draft content freeze and isolation

[Pilot integrity manifest](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-pilot-20261112-v3/pilot-integrity-manifest.json) SHA-256: **`a9bd1d0828fd39725a1801916f2584b31810687af2d68fc4b8eb8c4f9ed780cc`**. It binds fourteen artifacts plus itself: questions, labels, source excerpts/QA, review packages, authoring data, provenance, split reservation and generator snapshot. This is a **content freeze of agent drafts**, not human-approved gold or scoring authorization. Any correction requires a new version with parent hash and review before later scoring.

Preserved predecessors: v1 (`1db556028b8d469296f3e1ff77e1f10a9085162f20c8eb99fb767cc3613df4eb`) was superseded to correct a release-note section/anchor; v2 (`22a32df42ddf0f07508a30d30c543d7001e4b5f90fa2d2643895de06088e3004`) was superseded to tighten two clarification-fact statements so each alternative independently supports the full claim. Final v3 uses actual frozen PostgreSQL 12 section E.23.2 / anchor `id-1.11.6.28.4`. Questions and source excerpts stayed unchanged across these corrections; no retrieval results existed or guided the changes. Earlier versions were not edited or deleted.

Only the 24 original frozen source documents may be used in a future authorized index. **Never ingest the pilot workspace, review excerpts, labels, provenance or answer facts.** `questions.json` is separated from curator/evaluator-only label and evidence artifacts. The existing substring-based baseline scorer cannot directly score these unioned, alternative source-span labels; a later authorized evaluation-only adapter is required. Existing evaluation modules were inspected as text, not imported/executed. A/B/C and production settings remain unchanged.

# Human review and the remaining sealed set

Required before accepting labels: domain review of all four families and every fact/condition/alternative; bilingual review of all twelve variants; version compatibility and numeric/retention reasoning review; sufficient-set/unknown-relevance adjudication. Reviewer identities, timestamps and independent agreement remain absent, not invented.

Independent second labeling is preselected for **P04** (all unsupported/conflict cases) and **P02** (one of three remaining answerable families, rounding 25% upward), before seeing first-review labels or retrieval output. Record distinct human identities, disagreements and adjudication. Main-package exposure must be disclosed; agent-only judgments cannot be reported as independent human validation.

Reserve **16 sealed families / 48 questions**, of which 13 families / 39 variants are answerable and three families / nine variants unsupported. Remaining category counts are **5 single-document, 5 multi-section, 3 multi-document, 3 unsupported**. **Zero sealed questions have been generated.**

Recommended next preparation, only after separate approval: appoint domain/bilingual/independent reviewers and a sealed-label custodian; review and version the pilot drafts; then choose sealed topics without overlap with connected pilot evidence, translations, repetitions or version siblings. Keep one answerable sealed family per Prusa manual, including a distinct non-overlapping MINI topic. Verify the global six-manual, cross-language-direction, long-distance and historical-conflict quotas before sealing. Do not recycle P04's migration topic to fill a sealed conflict quota. If exclusions make the approved design infeasible, return for a scope decision rather than relax isolation or invent evidence. Do not tune retrieval from these labels.

# Tests, reproduction and Git state

**Nine tests passed in 3.76s** via `scripts/run_isolated.py`. Tests cover 4/12 grouping, agent-only provenance, full-file/source-coordinate fidelity, alternative sufficient sets/document requirements, restricted/derived evidence rejection, table row/header scope, cross-page conditions, unsupported N/A status, all-24 inspection coverage, sealed reservation, blind-view separation, real HTML anchor validation and integrity/tampering rejection. **All 55 local review links resolve to frozen source files.** Final read-only source/dataset integrity verification passed.

```powershell
$env:LAEW_FROZEN_CORPUS_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-freeze-v1'
$env:LAEW_REAL_WORLD_PILOT_ROOT='C:\Users\korne\LAEW-corpus\stage-2b2-real-world-pilot-20261112-v3'
python -B scripts/run_isolated.py pytest tests/evaluation/test_real_world_pilot.py -q --tb=short
python -B tools/corpus/prepare_real_world_pilot.py --verify --corpus $env:LAEW_FROZEN_CORPUS_ROOT --output $env:LAEW_REAL_WORLD_PILOT_ROOT --expected-inventory-sha a9bd1d0828fd39725a1801916f2584b31810687af2d68fc4b8eb8c4f9ed780cc
```

To reproduce into a **new external path**, use `prepare_real_world_pilot.py --corpus <frozen-root> --authoring <v3>/authoring-plan.json --output <NEW-path>`. The generator contains no source-bearing Prusa selection data; those data and excerpts remain external. Replaying agent-authored selections does not independently reproduce human judgment. Source-only integrity verification never changes the corpus or contacts a model.

Repository additions: `tools/corpus/prepare_real_world_pilot.py`, `tests/evaluation/test_real_world_pilot.py`, this report, `real-world-pilot-20261112-summary.json`, `real-world-pilot-20261112-initial-state.json`, `real-world-pilot-20261112-final-state.json`, `real-world-pilot-20261112-git-status.txt`. Report JSON is metadata-only. All **206 pre-existing dirty/untracked file hashes** remain unchanged. Pre-existing tracked changes remain `docker-compose.yml` and `docs/README.md`; no existing production, retrieval or chunker file was edited. No Git add/commit/push/reset/clean occurred.

**Stop after pilot preparation.** No indexing, retrieval benchmark, embeddings, live answer testing, GPT-5.6 Luna call, model download, paid API or sealed-question generation occurred. Human review, sealed preparation and any evaluation require their own next authorization.
