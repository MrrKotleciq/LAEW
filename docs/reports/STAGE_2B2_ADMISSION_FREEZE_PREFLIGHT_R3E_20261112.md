---
type: report
title: Restricted admission approval and source freeze preflight - Task 3C.2A-R3E
date: 2026-11-12
status: restricted-scope-approved-freeze-prepared-not-executed
scope: approval provenance, readiness clarification, 24-source verification, unexecuted source-only freeze plan
---

# Decision and readiness

**The user approved the R3D restricted text-only admission policy. That approval is recorded; the corpus is not frozen.** Offline preflight passes for all 24 source identities, hashes, revisions, license metadata and availability restrictions. No technical blocker to a **source-only restricted-scope freeze** was found. Separate explicit approval of the exact freeze plan/destination is still required before execution.

This accepts a bounded source/evidence scope, not comprehensive semantic correctness. All ten relationship/availability restrictions, all 329 uninspected High findings and all other open priorities remain. No further reconstruction of every graphic is required. Source-only freeze and later question/gold/dataset sealing are distinct operations.

New external workspace: **`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-r3e-v1`**. Its [current readiness](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/readiness.json) is authoritative for this preflight. Historical R3C/R3D candidate/pending labels remain unchanged; the R3E overlay records the subsequent scope approval.

# Approval and the reported missing readiness file

[admission-approval.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/admission-approval.json) records human-origin approval from the current user instruction, including its supplied approval sentence, exact R3D policy/restriction hashes, packaging date and explicit limits. The precise approval time and credentials were not supplied; timestamps remain null. Freeze execution, question generation, benchmarks and inference are not approved by this record.

**The reported external file absence was not reproduced.** Both historical files exist and match their original, report-anchored inventories:

| File | Bytes | SHA-256 |
|---|---:|---|
| R3D external `readiness.json` | 4,233 | `be673e4813cca57e898e2932de9afabe28998417a9d5c8342ffd51bcb35afe00` |
| R3C-v2 external `readiness.json` | 596 | `33f1129208d5f6a4b6c65cd4755f5dd9303b33a2fbee34afe76dfbb66541395a` |

The R3D report used an unlinked bare filename under its external-workspace section. There is no intended `docs/reports/readiness.json`. That reference was ambiguous, so an additive R3E clarification now links the [historical R3D file](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3d-v1/readiness.json), this report and current R3E readiness. Neither historical file was recreated, regenerated or edited. The exact location/history behind the user's lookup is unknown; no deletion, UI failure or prior absence is asserted. [readiness-discrepancy.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/readiness-discrepancy.json) contains the checked paths, lengths, hashes and explanation.

Historical R3D `freeze_ready=false` describes its pre-approval state. Current R3E separates **technical preflight passed**, **restricted policy approved**, **freeze not authorized/executed**, and **Task 3C.2B not authorized**. Approval does not retroactively turn the 15 component observations into expert or whole-page certification.

# Source identity, pin and restriction verification

[source-identity-verification.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/source-identity-verification.json) lists **each of the 24 units**, original/normalized hashes, revision/commit, product/version applicability, language provenance, original/source/map paths, license notice and hashes of the retained artifacts. Identity fields were compared with the original accepted manifest; all 18 Git/PostgreSQL Markdown identities remain byte-identical. Whole inventories verify the retained assets and upstream evidence too. This is an offline check of the approved snapshots, not live publisher freshness or new semantic certification.

| Group | Verified revision pins |
|---|---|
| Prusa, six complete manuals | MK4S EN 1.01 / 2024-09-26; MMU3 EN 1.03 / 2025-05-15; MK4 DE 1.03 / 2023-09-04; XL DE 1.06 / 2026-01-22; MINI PL 1.09 / 2022-04-05; MK3S PL 3.17 / 2021-04-21. Hardware/date applicability remains intact; no current-firmware claim. |
| Pro Git EN, four sections | `a013e3230a1207cfa5ae94d28ba7d2021063c337` |
| Pro Git PL, four sections | `3a939c84461d254478a87749d43bed97ada37602`; authentic mixed PL/EN configuration/submodule content remains approved mixed content. |
| Pro Git DE, four sections | `9a8204ef167584e5b703eccbce5d4e81a7cdc86b` |
| PostgreSQL 17 archiving, backup, recovery configuration | `REL_17_10`, `25c49f3a4a742ba283f5cc43cc7f1d361552e917` |
| PostgreSQL 17 WAL configuration | `REL_17_STABLE`, **`220b5263dbb71bbe2966c6d47c0c456c14ed4e48`**; do not relabel the pinned rendered WAL snapshot as REL_17_10. |
| PostgreSQL 11 archiving | `REL_11_22`, `fd851f9e4a13d81cccc4ac5d6059d732c7518111` |
| PostgreSQL 12 release notes | `REL_12_22`, `498f30a8b7025a2a7bd3715acc1d1692122ba542` |

All six Prusa manuals keep their original local-research licensing limits. Pro Git and PostgreSQL notices stay intact. Freeze is a local byte-preserving copy, not redistribution authorization. Publisher-rendered pages and pinned repository sources retain their documented correspondence limitations.

[availability-restrictions-approved.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/availability-restrictions-approved.json) binds approval to the unchanged R3D region register: nine R3C limits plus XL DE PDF 83. Exact source regions remain:

- MK3S PL PDF 16 and MINI PL PDF 45: graphical column polarity unavailable.
- MK3S PL PDF 37: callout association/instruction scope unresolved.
- MMU3 EN PDF 6: safety-symbol associations unavailable.
- XL DE PDF 81: electrical-symbol meaning/association unresolved; its separate product table has no positive human table check from R3D.
- XL DE PDF 83: PDU identification/numbered-label geometry, protective-earth terminal identification and connections unverified.
- MK4 DE PDF 33 / XL DE PDF 35: complete image-dependent reset/confirmation procedures unavailable.
- MK4S EN PDF 19 / MK4 DE PDF 22: complete image-dependent sensor/selftest startup unavailable.

The five positive table observations remain component-scoped and the four readable images remain non-extracted. No OCR, translation, graphical transcription or new technical interpretation was added. R3D reconciliation re-verifies the 15 exact page/component mappings, including neighboring-section boundaries and required XL table footnote/PDU label context.

[risk-preservation.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/risk-preservation.json) confirms **418 unchanged records: 0 Critical / 388 High / 10 Medium / 20 Low**, including the exact **329 uninspected High** queue, nine uninspected Medium and twenty uninspected Low. It records original-register and exact-queue hashes. **Zero priorities were cleared.** Approved unavailability is a coverage decision, not confirmation of missing technical relationships. Unknown material stays unjudged; actual future evidence use requires targeted source/context QA.

# Prepared freeze manifest and reproducible procedure

The reviewable [draft freeze manifest](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/freeze-manifest.draft.json) has status **`prepared-not-executed`** and freeze ID **`stage-2b2-real-world-20261112-freeze-v1`**. It pins all identities, source/metadata hashes, tool/helper hashes in this dirty checkout, the scope approval and complete risk/availability basis. No HEAD-only reproducibility claim is made.

Planned destination, **not created**:

`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-freeze-v1`

The plan contains **774 exact copy entries / 265,280,870 bytes**: 751 R3C files including its inventory, 13 R3D files including its inventory, and ten current R3E approval/preflight/procedure artifacts. Full R3C directory structure is preserved under `corpus/`, preserving relative document/image links; R3D goes under `review/r3d/` and current metadata under `review/r3e/`. This does not re-normalize sources or change source-once representation. The draft plan and its later R3E inventory are explicitly excluded from recursive self-hashing; execution would separately retain the exact plan, later freeze approval and completion receipt at the target root.

Manifest SHA-256: **`5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19`**.

[FREEZE_PROCEDURE.md](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/FREEZE_PROCEDURE.md) gives commands and an independent, read-only destination-verification snippet. The prepared [PowerShell procedure](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-r3e-v1/freeze-procedure.ps1) is **not executed**. Its intended sequence is:

1. Obtain separate human approval for the exact manifest hash, freeze ID and destination; record the later user instruction as a separate `corpus-freeze-only` approval. R3E scope approval cannot satisfy this requirement.
2. Re-run read-only R3E preflight against the report anchor. Any changed source, metadata or consumed code requires a new preflight version and renewed approval of that plan.
3. Only after approval, invoke the prepared procedure. It checks its own hash, plan hash, exact approval binding, all sources and a new destination before copying. It checks copied bytes and rechecks sources before writing a completion receipt. No source mutation/deletion or automatic partial-target cleanup is included.
4. Independently verify every destination hash/length, the exact destination file set, manifest/approval hashes and receipt. Absence of a valid receipt or any failed check means an incomplete snapshot. A failed partial target must not be reused silently.
5. Record completion separately; stop before Task 3C.2B. Hash-based logical freezing does not enforce operating-system immutability; verify before later use. Archived historical status fields/absolute staging references are not rewritten; the reviewed plan and receipt define any completed source freeze.

No completion receipt or executed-freeze approval exists. The procedure's PowerShell syntax was parsed with **zero errors without executing it**. Its actual copying phase has not been tested end to end or run against this corpus, because execution is not authorized. Post-copy verification remains mandatory.

# Remaining blockers by stage

| Stage | Remaining requirement |
|---|---|
| Restricted admission policy | Approved by the current user instruction, recorded against exact R3D hashes. No repeat scope approval is required. |
| Source-only freeze | **Separate user authorization of this exact plan/destination**, followed by a fresh preflight and verified copy. No current technical blocker was detected. |
| Task 3C.2B | Completed/verified source freeze, separate authorization, and recorded domain/bilingual/independent second-review roles. Reviewer availability is unknown; identities/assignments were not supplied. |
| Evidence labeling / dataset seal | Targeted source-span and condition/warning QA; provenance and independent-review requirements; six-manual answerability, language/distance quotas and 12-pilot/48-sealed separation. These later requirements do not require reviewing all 329 High pages before a source-only freeze. |
| Expanded graphical/safety scope | Qualified targeted interpretation or continued unavailability. No complete PDU/electrical/symbol-driven/image-dependent procedure certification follows from admission. |
| Indexing, retrieval/answer benchmark, live pilot | Separate authorization; not started or covered by source freeze approval. |

R3D mentioned reviewer roles around freeze preparation; the approved policy itself requires them before question generation. R3E makes the boundary explicit: source-only freeze can preserve unresolved/unjudged material and restrictions; domain/bilingual/second review remains a blocker to Task 3C.2B and accepted labels, not a reason for exhaustive manual reconstruction.

# Verification and repository changes

**145 tests passed in 36.65s**, using `scripts/run_isolated.py`: eleven R3E cases plus the previous 134 corpus/chunker tests. They cover exact policy binding without freeze authorization, historical readiness presence/missing-copy refusal, edition/WAL/language/license/source substitution rejection, all source files and priorities in the plan, output tampering and target/snapshot reuse. The test suite prepares metadata in isolated temporary storage; it never runs the generated freeze procedure.

With the prior corpus environment variables and `LAEW_PRUSA_R3D_ROOT` set:

```powershell
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r3e.py tests/evaluation/test_prusa_pdf_r3d.py tests/evaluation/test_prusa_pdf_r3c.py tests/evaluation/test_prusa_pdf_r3b.py tests/evaluation/test_prusa_pdf_r3a.py tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

The new external R3E package contains **eleven inventoried files plus its inventory**. R3E inventory SHA-256: **`5ece0758981377b165a632d10f1f3752e9f2a92c7505c22a8a1d8db45427ae08`**. Read-only verification passed:

```powershell
python -B tools/corpus/preflight_prusa_r3e.py --verify --r3c 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261111-r3c-v2' --r3d 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-r3d-v1' --output 'C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-r3e-v1' --expected-inventory-sha 5ece0758981377b165a632d10f1f3752e9f2a92c7505c22a8a1d8db45427ae08
```

Pinned R3C/R3D inventory anchors remain `c63e3eddfc17b9c04f420d1ec3cb2e1c7196b3ffaeae9346a58fcadf600a93aa` / `07cb927d96d0153681f0034aed8502e46ca0334fcb4e1305b1b0e3a4b90f7d0f`. Before/after checks confirm unchanged **750 R3C / 12 R3D inventoried files**, plus their inventories, and the prior **203 R3B / 75 R3A / 1,297 R2 / 87 R1 / 289 acquisition files**. Source identity, restriction and code checks pass. The planned freeze directory remains absent.

Added: `tools/corpus/preflight_prusa_r3e.py`, `tests/evaluation/test_prusa_pdf_r3e.py`, this report, `prusa-pdf-r3e-20261112-preflight.json`, `prusa-pdf-r3e-20261112-initial-state.json`, `prusa-pdf-r3e-20261112-final-state.json`, `prusa-pdf-r3e-20261112-git-status.txt`. Modified only the existing R3D report, by adding the documented readiness-location/current-state clarification. The initial snapshot records hashes of all **193 pre-existing dirty/untracked files**; final comparison permits only that intended additive report edit. All other pre-existing work is preserved. Tracked changes remain the pre-existing `docker-compose.yml` and `docs/README.md` changes. No Git add/commit/push/reset/clean occurred.

Production, source documents, PDFs, previous corpus/metadata snapshots, chunkers and RAG settings are unchanged. No questions, gold labels, embeddings, indexes or inference were created. **Stop before freeze execution and request separate approval of the prepared plan.**
