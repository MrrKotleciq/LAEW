---
name: M17 Knowledge Organization Verification
description: Production acceptance after approved Polish knowledge deployment, with the historical preparation record.
title: M17 Knowledge Organization Verification — 2026-10-29
type: report
scope: project
status: active
read_when:
  - reviewing the prepared knowledge package before production approval
  - checking the remaining M17 completion requirement
---

# M17 knowledge organization verification — 2026-10-29

**M17: COMPLETE.** The user explicitly approved the full package on 2026-10-29
with a Polish-language requirement for authored global notes and an exception
for original source documents natively written in another language.

This is the dated completion record. The same vault was reorganized on
2026-10-31; its current paths/counts and Inbox exclusions are documented in
[the reorganization verification](M17-Vault-Reorganization-2026-10-31.md).

## Final production acceptance

Eight approved Polish documents were added to the actual vault; the existing
synthetic note was translated with its verification code and original backup
preserved. All nine visible Markdown documents are now Polish. Native-language
source documents in LAEW remain unchanged and are linked from Polish notes.
Directory names, metadata keys, wikilink identities and code identifiers remain
stable. The approved profile records the new language preference.

The four manifest categories (`Knowledge`, `Decisions`, `Research`, `Templates`)
contain six useful materials; `profile/` contains two approved minimal notes.
This real content, not the retained synthetic note, satisfies the population
requirement. The actual `laew_global` index contains **31 chunks from 9 files**.

| Criterion | Evidence | Result |
|---|---|---|
| Explicit content approval | User approved the whole package with the Polish language condition; retained facts remain minimal and approved | PASS |
| Global Knowledge populated | Six reusable materials plus two approved profile notes in `C:\ROOT\Knowledge`; retained synthetic note identified separately | PASS |
| Global Knowledge organized | All four manifest categories populated; profile remains a logical category in the same global collection | PASS |
| Metadata consistency | All nine files have supported `docs` type, global scope, active status and required descriptive metadata | PASS |
| Vault ingestion and link preservation | Actual 31 records exactly match the file-derived chunk IDs, text and note metadata; all source links and wikilinks checked | PASS |
| Correct `@knowledge` attribution | Seven production topic queries returned expected aliased sources; Chief cited actual global paths | PASS |
| Global Knowledge retrieval | Actual indexing, context, security, evaluation, ownership and two profile topics found; broad-query limitation below | PASS for stated topic cases |
| Project isolation | Production global operations left LAEW and Studia records/vectors unchanged; project-only query returned only Studia paths; earlier independent-project isolation tests retained | PASS |
| Hybrid retrieval | Actual Studia README plus actual global evaluation note returned to the Chief with both source types | PASS |
| Incremental synchronization | Eight added files, approved test-note translation updated one file; later section-only changes reconciled; repeated final sync found 9 unchanged files/31 chunks with zero new embeddings | PASS |
| Chief Agent integration | Two live configured-model runs through Workbench HTTP, RagTool and production Chroma; both returned expected sources and correct substantive answers | PASS for stated cases |
| Workbench integration | Real Studia selection and Polish setting verified; actual-source NDJSON answers captured through a separate loopback listener | PASS (API/service; no new DOM/browser run) |
| Existing M17 infrastructure requirements | Earlier process, failure/recovery, restart and browser evidence in [the prior matrix](M17-Verification-2026-10-28.md); prior final broad regression 924 passed, 2 skipped, 1 deselected | PASS for documented tested paths |
| Definition of Done | The populated actual Obsidian vault is indexed and retrievable as global context with correct scoping and provenance | PASS |

Evidence under Git-ignored `runtime/knowledge-deployment-2026-10-29/`:

- `deployment.json`: user authorization, added paths, source hashes and confirmation
  that existing files were preserved during addition.
- `production-report-initial.json`: first production sync (eight added notes,
  26 new chunks), real test-note translation update (one document/one chunk),
  and the first relevance failure; preserved without relabeling it as a pass.
- `production-report-profile-miss.json`, `retrieval-diagnostics.json` and
  `profile-retrieval-diagnostics.json`: further observed retrieval limitations.
- `section-organization.json`: two approved notes reorganized into meaningful
  Markdown sections to separate facts, limitations and provenance, without
  adding personal facts; original versions preserved.
- `production-report.json`: successful final seven-topic retrieval, actual
  source metadata, unchanged sync and both live Chief cases.
- `final-consistency.json`: all 31 indexed texts/note metadata match current
  files; Obsidian configuration unchanged; final source hashes and diagnostics.
- `project-memory-refresh.json`: LAEW's final status/roadmap/policy changes
  synchronized incrementally (four documents updated); the completion query
  returned the milestone and PROJECT_STATUS sources. An unchanged repeat
  found 45 documents/321 chunks with zero embeddings; global and Studia
  records/vectors remained unchanged during this project-only refresh.
- `backups/`: original synthetic note and pre-organization versions of the
  two newly approved notes. This is a local task backup, not M18 automation.

The live global answer correctly specified measuring actual embedding-generation
calls during an unchanged second sync and expecting zero calls. The hybrid
answer correctly stated that Studia does not parse PDF contents and named the
four separate evaluation outcomes (indexing, selection, provenance, interpretation)
with the exact project/global citations. Minor Markdown spacing remains a
presentation-quality caveat; the substantive questions were answered.

### Retrieval limits and changes made during validation

One broad ownership question ("Gdzie powinny trafić wyniki konkretnego
eksperymentu, ogólna metoda oraz zatwierdzone preferencje użytkownika?") missed
the main ownership note at both three and the configured default five results,
including after section organization. More focused questions about ownership
and knowledge promotion retrieved it correctly. This observed false negative
is retained as a semantic-ranking backlog item, not described as fixed.
The milestone defines a useful populated/retrievable vault, not perfect recall
for every paraphrase; the completion decision uses multiple actual topic
queries and grounded answers and does not claim 100% retrieval accuracy.

The initially monolithic goals note also missed natural questions. Separating
its approved goals from uncertainty/provenance made both the original academic
goals question and the concise goals question retrieve `profile/goals.md`.
No threshold, model, RAG implementation or mandatory acceptance criterion was
changed to obtain the final result. The preparation regression remains the
software baseline; post-documentation checks are recorded in the final user
report. PDF/OCR, richer filters, graph retrieval, context injection and more
private profile storage remain optional future work.

Post-deployment focused regression: **58 passed** in 6.34 seconds, covering
documentation validation, console RAG configuration, project language,
Obsidian ingestion and the academic project integration regression.
`node --check laew/ui/app.js` and `git diff --check` passed. Application code was
unchanged in this deployment phase; the previous broad **924 passed, 2 skipped,
1 deselected** and **9 UI tests passed** remain the software baseline. No new
full infrastructure or browser suite is claimed.

## Historical preparation snapshot — before approval

**Historical M17 status: IN PROGRESS.** At this stage the production vault contained one synthetic note.
Content approval and actual curated-vault deployment/retrieval remain mandatory.
The milestone's scope and Definition of Done have not changed. User Profile and
Studia are applications of the existing architecture, not new M17 completion gates.

## Audit and minimal change

ADR-002, ADR-009, ADR-010 and ADR-011 already establish one shared vault and
separate Project Memory. WorkspaceService discovers ordinary directories;
neither Git nor software-specific content is required. Collection identities
already derive from the canonical full project path. No agent or memory service
was added. PathResolver and PermissionBroker were left unchanged.

The real obstacle was the manifest's LAEW-specific RAG document allowlist.
The optional validated `.laew-project.json` field `rag_source_allowlist` now
overrides that list for one project in runtime and console RAG composition.
Existing projects retain the manifest selection. Studia uses `README.md` and
`docs/*.md` (including nested paths). The source allowlist is not permission
to read outside a root. Templates and attachments are excluded from Studia RAG.

The [knowledge organization policy](../architecture/KNOWLEDGE_ORGANIZATION.md)
documents ownership, controlled promotion, profile visibility, flexible project
layouts, metadata, attachments and future Core User Context. `type: docs` is
used for notes/profiles instead of inventing `profile` or `notes` schema types.
The lightweight parser preserves tags and raw wikilinks; arbitrary academic
fields are neither embedded nor exposed as RagTool filters. PDF/OCR support,
academic filters, context integration and portable tool-contract hints are
recorded as optional backlog items, not implemented here.

## Reviewable artifacts

Git-ignored preparation package:
`runtime/knowledge-preparation-2026-10-29/`.

- `Global-Knowledge/`: five generalized technical/method notes, one reusable
  authoring template, and two explicit profile proposals. The layout preserves
  `Knowledge/`, `Decisions/`, `Research/`, `Templates/`, adding logical `profile/`.
- `Studia/`: the source package for the real `C:\ROOT\Projects\Studia` project:
  configuration, README, index and four small templates. No fictional subjects
  or personal education history was created in that project.
- `inventory.json`: candidate paths, SHA-256 digests, YAML metadata and source
  document hashes. All 14 candidate/project Markdown files passed metadata and
  Markdown-link checks; candidate wikilink destinations exist.
- `production-readonly-audit.json`: direct project discovery and read-only
  production index inspection. At audit time `laew_global` had one record and
  LAEW's project collection had 312 chunks; the legacy collection was absent.
- `RAPORT.md`: Polish user report and the exact scope awaiting approval.

Profile proposals retain only the requested collaboration languages, minimal
architecture/security preferences and the user's stated knowledge-management
goals. No university, major, semester, proficiency or career goal is inferred.
The goals are dated and must be reconfirmed when time-sensitive. Contact,
health, identifiers and credentials are not included. Approval remains pending.

The draft status is intentional. Approval must also cover the mechanical
deployment changes documented in the review package: activating accepted notes,
removing the two profile proposal notices and recording the real approval date.
No profile or proposed technical note has been written to the production vault.

## Current verification matrix

| Criterion | Evidence | Result |
|---|---|---|
| Global Knowledge populated with real curated content | Production inspection: only `test-global-knowledge.md`; eight candidate documents are staging only | FAIL — approval and deployment pending |
| Global Knowledge organized as stated in M17 | Candidate uses the four manifest categories plus profile; production has no curated category contents | FAIL for production |
| Metadata consistency | YAML, links and source-hash inventory validated for all candidates; no new type enum required | PASS for candidates; production check pending |
| Vault ingestion and link preservation | Current isolated HTTP Chroma run: eight candidate documents, 26 chunks; raw wikilinks preserved | PASS for candidates; actual-vault validation pending |
| Correct `@knowledge` attribution | Six real-embedding queries returned expected candidate sources | PASS for candidates; actual-vault validation pending |
| Global Knowledge retrieval relevance | Six topic questions across indexing, context, tool security, evaluation, ownership and Polish preferences retrieved the expected note first | PASS for candidates; actual-vault validation pending |
| Project isolation and nested sources | New deterministic academic regression; three isolated HTTP collections with distinct roots, including real Studia | PASS for tested paths |
| Hybrid retrieval | Isolated academic fixture plus candidate global notes; expected project/global sources also reached the live Chief | PASS for tested paths |
| Incremental synchronization | Isolated candidate update/restore; unchanged sync embedded zero chunks; offline academic add/update/delete checks | PASS for tested paths |
| Chief Agent integration | Two live configured-model runs through Workbench HTTP and RagTool; expected sources returned, nonempty answers | PASS for tested paths; language quality caveat below |
| Workbench selection and project language | Real Studia discovered under actual Projects root; selected via isolated HTTP Workbench; documentation language `pl` | PASS (API/service, no new browser run) |
| Existing M17 failure/restart/process requirements | Earlier evidence remains in [the prior verification matrix](M17-Verification-2026-10-28.md); current offline regression results recorded below | Prior evidence retained; no wholesale live infrastructure rerun |
| Production source separation and retrieval | Actual curated-vault deployment has not occurred | FAIL — pending approved production validation |

Live evidence: `runtime/knowledge-validation-02b08fc149f2/report.json`.
This run used existing local chat/embedding services with a dedicated loopback
Chroma HTTP process, dedicated Workbench HTTP process and a copied candidate
vault. It never opened the production database or vault. The real Studia root
and candidate source files were unchanged by that validation.

The first live answer correctly described Studia's indexed Markdown, unsupported
PDF content and Polish documentation, citing `@project/README.md` and its index.
The hybrid answer used the fictional PID label only from the isolated fixture
and explained fingerprints, chunk counts and reuse from the correct global
note. Its Polish wording was awkward (including an inappropriate translation
of "unchanged sync"); it explained reuse conditions but did not explicitly
give the requested embedding-call-count measurement. Retrieval/provenance pass;
model interpretation is useful but incomplete. Do not equate correct tool
sources with perfect answer quality. Both stored answers contained zero U+FFFD.

## Regression execution

Focused preparation/runtime/language tests: **42 passed**. UI tests: **9 passed**;
`node --check laew/ui/app.js` passed. Metadata and link validation passed.

The first broad run reported 922 passed, 2 failed, 2 skipped, 1 deselected.
One failure was the existing exact allowlist-count assertion (44 versus 45 after
the new policy document); it was updated to 45 with an explicit assertion for
that document. The concurrent persistent-Chroma process test returned early
without its expected marker. Its immediate isolated rerun passed; the initial
failure's cause is not established and is not described as fixed.

Final broad rerun: **924 passed, 2 skipped, 1 deselected** in 148.15 seconds:
`pytest tests/unit tests/integration tests/evaluation tests/workflow tests/multiagent
-m "not ollama" --basetemp=runtime/knowledge-preparation-2026-10-29/pytest-final
--tb=short -q`. The two skipped cases require POSIX chmod semantics; the live
Ollama test was deselected. The 38 warnings concern a ChromaDB dependency's
deprecated asyncio API. The final run includes the previously failing process
test. Logs: `runtime/knowledge-preparation-2026-10-29/pytest-final.log`.

The real Studia project was also synchronized to its production collection
`laew_project_38fa5f6b8863b4367be259e379861ab3`: two documents and five chunks.
An unchanged second synchronization performed zero embeddings. A real embedding
query returned `@project/README.md` and the project index. SHA-256 comparisons
of existing LAEW/global record metadata and vectors before/after confirmed
that both existing collections were unchanged. Global scope was not synchronized.
Evidence: `runtime/knowledge-preparation-2026-10-29/production-studia.json`.
The production collection contains only real project guidance, not academic
fixtures or proposed profile contents.

Initial sandbox attempts also encountered
restricted default temp-directory and loopback-socket access; test runs used
workspace-local temporary directories and authorized local-service access.

## Remaining required work

1. Obtain explicit approval of the exact profile and knowledge candidates.
2. Recheck current production files; add only approved notes without overwriting
   user changes or removing the existing test note.
3. Synchronize actual global scope; inspect real records, provenance, links,
   several concept queries and hybrid answers. Test an approved safe update and
   unchanged embedding avoidance against actual content.
4. Re-evaluate all mandatory M17 criteria. Only then set milestone status to
   completed and update PROJECT_STATUS with actual production evidence.

Monitoring, backup/retention and live health indicators remain M18 work. Full
permission/TerminalTool acceptance remains with those components. Neither is
silently implemented or made a new M17 completion gate by this task.
