---
type: report
title: Restricted text-only corpus freeze completion - Task 3C.2A-R3F
date: 2026-11-12
status: frozen-restricted-text-only-independently-verified
scope: approved source-only freeze; no Task 3C.2B or benchmark authorization
---

# Result

**The approved source-only freeze completed and passed independent verification.** Freeze ID: `stage-2b2-real-world-20261112-freeze-v1`.

Destination: **`C:\Users\korne\LAEW-corpus\stage-2b2-real-world-20261112-freeze-v1`**. Future source access should use its `corpus/normalized/` directory with the preserved source manifest/maps and approved availability restrictions.

The original, unmodified R3E `freeze-procedure.ps1` exited successfully. Receipt completion time is `2026-11-12T13:47:29.6606563Z`. The freeze preserves **774 planned files / 265,280,870 bytes**, plus three root records: `freeze-manifest.json`, `freeze-approval.json`, `freeze-receipt.json`. The exact destination set is **777 files**, with no missing or extra files.

# Authorization, preflight and hashes

Read the R3E report and its prepared procedure before execution. Direct human authorization from the current R3F instruction was recorded in the external `stage-2b2-real-world-20261112-r3f-v1/freeze-approval.json`, binding the exact ID, destination and approved manifest hash. Approval time/credentials were not supplied and were not fabricated. A byte-identical copy is retained in the frozen root.

Fresh R3E preflight passed **before** execution: original R3C/R3D and historical input-chain integrity, R3E inventory, all source identities, revision pins, restrictions, planned source bytes and consumed tool/helper hashes. The destination was absent. Neither the approved plan nor procedure was edited. The existing procedure was then executed with the exact approved parameters and external authorization record.

| Frozen record | SHA-256 |
|---|---|
| [freeze-manifest.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-freeze-v1/freeze-manifest.json) | `5164763f273cf02379358b403cd48727e416e0898fd089b559277365a4099c19` |
| [freeze-approval.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-freeze-v1/freeze-approval.json) | `2c1fa29a284a6576146d2ce94360426d8f62f7fee20455f1eca464d2329956d4` |
| [freeze-receipt.json](C:/Users/korne/LAEW-corpus/stage-2b2-real-world-20261112-freeze-v1/freeze-receipt.json) | `cc46d666407c74beec2bf0832bfcf4a9f62117db608f53c2ef339e5e28d7759c` |

The executed procedure itself matched approved SHA-256 `69905949993469d363e2c7955cd7dff2fc4d2f64d9df9ebacfe035aec3399ebe`.

# Independent verification and preserved scope

A separate Python standard-library check, without importing freeze/preflight helpers, verified **every one of the 774 destinations** against its expected byte length and SHA-256, and checked each corresponding original source file remained unchanged. It also verified:

- Approved manifest identity and byte equality with the original R3E plan; unique destinations confined to the approved root.
- Exact 777-file set; approval origin, purpose, ID, destination, plan hash and prohibited follow-on authorization flags.
- Receipt status `frozen-restricted-text-only`, ID, copied-file count, manifest/approval hashes, timezone-aware completion time, and false semantic-certification/question/index/inference flags.
- All **24 original/normalized source identities**, versions, language provenance, license/map/provenance artifact hashes; six Prusa, twelve Pro Git, six PostgreSQL units. WAL commit remains `220b5263dbb71bbe2966c6d47c0c456c14ed4e48`.
- **418 unchanged risk records: 0 Critical / 388 High / 10 Medium / 20 Low**, including the exact **329 uninspected High** queue. No priority was cleared or semantically certified.
- **Ten approved restricted components**: MK3S PL PDF 16/37, MINI PL 45, MMU3 EN 6, XL DE 81/83, MK4 DE 22/33, XL DE 35, MK4S EN 19. Nine inherited availability regions and all fifteen human observations remain intact. Readable images remain non-extracted; electrical/PDU, symbol, polarity and image-dependent procedure limits remain unresolved/unavailable as approved.

[Verification JSON](prusa-pdf-r3f-20261112-verification.json) records all 774 per-file results and receipt metadata; its SHA-256 is `7456a2aaa670de28e3f9a33e0be3733614daa599441e6bb1792e72fcfa716dc7`. [Input integrity JSON](prusa-pdf-r3f-20261112-input-integrity.json) records the post-test verification of unchanged original R3C/R3D, historical input chain and all eleven inventoried R3E artifacts plus their inventory.

The frozen source manifest and archived R3C/R3D/R3E metadata retain their historical candidate/pending/not-executed fields and original staging references. They were not rewritten. The approved manifest plus completed receipt and this report establish the completed freeze. This is a logical hash freeze, not filesystem-enforced immutability or full semantic certification; verify hashes before later use. It is not a question/gold/dataset seal.

# Tests and Git state

**145 tests passed in 37.08s**, using `scripts/run_isolated.py`, with the existing corpus environment variables and `LAEW_PRUSA_R3D_ROOT` set:

```powershell
python -B scripts/run_isolated.py pytest tests/evaluation/test_prusa_pdf_r3e.py tests/evaluation/test_prusa_pdf_r3d.py tests/evaluation/test_prusa_pdf_r3c.py tests/evaluation/test_prusa_pdf_r3b.py tests/evaluation/test_prusa_pdf_r3a.py tests/evaluation/test_prusa_pdf_r2.py tests/evaluation/test_prusa_pdf_remediation.py tests/evaluation/test_real_world_corpus.py tests/unit/test_markdown_chunker.py tests/unit/test_contextual_chunker.py -q --tb=short
```

No new test or implementation code was needed. The original input chain and R3E metadata were rechecked after tests. The pending-freeze R3E verifier is not rerun against an existing completed target; independent post-freeze checks validate the completed snapshot instead.

Added in the repository: this report, `prusa-pdf-r3f-20261112-initial-state.json`, `prusa-pdf-r3f-20261112-verification.json`, `prusa-pdf-r3f-20261112-input-integrity.json`, `prusa-pdf-r3f-20261112-final-state.json` and `prusa-pdf-r3f-20261112-git-status.txt`. These contain metadata only; source-bearing material remains external. All **200 pre-existing dirty/untracked file hashes** remain unchanged. Tracked changes are still only the pre-existing `docker-compose.yml` and `docs/README.md`; no production or earlier report/tool/test edit was made. Final snapshot/status files record the exact repository state. No Git add/commit/push/reset/clean occurred.

**Stop after successful freeze.** Task 3C.2B, questions/gold evidence, indexing, benchmark execution and AI inference remain unauthorized and were not started. No original source snapshot, PDF, document representation, chunker or production RAG setting was changed.
