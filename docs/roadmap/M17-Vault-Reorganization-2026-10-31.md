---
name: Global Knowledge Vault Reorganization Verification
description: Path migration, Obsidian compatibility checks and global-only RAG validation after M17 completion.
title: Global Knowledge Vault Reorganization — 2026-10-31
type: report
scope: project
status: active
read_when:
  - checking the current global vault layout or source selection policy
  - reviewing migration evidence and remaining Obsidian UI checks
---

# Global Knowledge vault reorganization — 2026-10-31

**M17 remains completed.** This is maintenance of the existing vault and RAG,
not a new memory system or a change to the milestone Definition of Done.

## Audit and backup

The actual vault contained eight Markdown notes, no visible attachments and no
README. Contrary to the supplied initial description, Decisions and Research
were populated. Their notes were preserved. The global index still had nine
source paths/31 chunks, including a test note already absent from disk.
That stale index record was reconciled; no source document was deleted.

Backup: `runtime/backups/vault-reorganization-2026-10-31-b774ebc3/`.
The archive contains all 63 original files (6,897,939 bytes before compression),
including note metadata, Obsidian/plugin configuration and the tiny existing
Smart Environment state. CRC and per-file SHA-256 read-back checks passed.
No large model/cache payload existed or was copied. The global collection's
records, vectors and metadata were also exported. Neither backup is in Git or
inside the production vault.

The exact old-to-new file mapping is in
`runtime/vault-reorganization-2026-10-31/migration-plan.json`; each folder move,
including the intermediate names for case-only Windows renames, is recorded in
`migration-journal.json`. On a conflict or unexpected file change the script
stops and preserves its journal/backup; it never performs blind rollback.

## Current layout and source policy

```text
C:\ROOT\Knowledge\
  .obsidian/                 existing configuration preserved
  .smart-env/                existing plugin state preserved
  profile/                   unchanged approved profile files
  topics/ai/                 moved from Knowledge/ai/
  topics/security/           moved from Knowledge/security/
  research/                  moved from Research/
  decisions/                 moved from Decisions/
  inbox/                     empty raw-note workspace
  templates/                 preserved template plus new Inbox template
  README.md                  new Polish organization guide
```

Assets were unnecessary because no attachment files/settings required a new
folder. All eight original frontmatter mappings are unchanged. Six notes moved;
the two profile notes are byte-identical to their originals. Only necessary
link targets changed in existing note bodies. Fifteen rendered wikilinks resolve
after migration, including the README link; all 14 original wikilink targets
were updated. Absolute local-source Markdown links remain valid and unchanged.

Initial ingestion and incremental sync share `_source_selected`, including
default case-insensitive exclusions for `inbox/**`, `templates/**`, `assets/**`,
`backups/**`, `temp/**`, temporary/backup Markdown suffixes and existing hidden
folder rules. `rag.global_sources.exclude_patterns` adds validated exclusions
without disabling defaults. Runtime, console RAG and vault inspection use the
same selection policy. Project source selection is independent.

The README is intentionally indexed so the Chief can retrieve organization
rules. Research is not excluded or automatically marked verified. Its status
metadata is retained; material limitations should also be in body text because
the existing RAG does not expose all frontmatter fields as context/filters.

## Obsidian compatibility: verified scope

| Area | Static/automated result | Actual application result |
|---|---|---|
| Existing vault | Same root, `.obsidian` and `.smart-env` retained | No Obsidian app/window returned by Computer Use inventory; manual open check remains |
| Wikilinks | Actual targets resolve; isolated tests preserve short links, aliases, headings, block IDs, embeddings and `.md` suffixes | Navigation not exercised in UI |
| Markdown links | Existing source paths preserved; isolated relative/encoded/attachment link cases pass | Attachment rendering not exercised; no actual attachments existed |
| Breadcrumbs | All configured relation fields preserved byte-for-byte; no existing note had relation values to rewrite | No populated relation graph available for UI acceptance |
| Dataview | Installed/enabled; no queries, DataviewJS or folder predicates existed in notes; no code executed | UI/query rendering not exercised |
| Core Templates | Already enabled but no folder configuration; added `.obsidian/templates.json` with `folder: templates` | Template insertion not exercised |
| Templater | Not installed | Not applicable |
| Smart Connections / Lookup | Installed but not enabled; no cached smart source/component/context files existed; all state/config bytes preserved | Not enabled or refreshed by this task |
| Note Refactor, Supercharged Links, Style Settings | No relevant hard-coded moved path found; configurations untouched | Runtime plugin behavior not exercised |

The workspace file contains historical already-invalid paths such as
`Knowledge/Local Models tests.md` and paths under `Projects/LAEW/`; none identifies
a moved current note. They were not guessed/replaced, and the saved workspace
was not reset. Smart Environment and ChromaDB are independent indexes.

## Verification and operational limits

Production evidence: `runtime/vault-reorganization-2026-10-31/production-report.json`.
The actual `laew_global` now has eight source paths/35 chunks. Every stored
chunk ID, text and supported note metadata matches the current selected files.
There are no obsolete uppercase/Knowledge source paths, duplicates, template or
Inbox records. The already-missing test note is absent. Research and both profile
notes remain available. The recorded explicit sync found all eight documents
unchanged; a repeated sync and fresh-process sync required zero document
embeddings. Do not infer zero migration cost: path changes may regenerate
vectors and the original-index export proves the before/after path change.

Eight concept questions returned expected sources; three actual Chief runs
through a separate Workbench HTTP listener correctly answered a topic question,
the approved profile language preference and the Inbox/template lifecycle.
All returned current `@knowledge/topics/...`, `@knowledge/profile/...` or
README sources. The global validator never synchronized a project collection.
Hashes of every preexisting non-global collection matched before/after the
dedicated global validation. The later regression incident below changes the
end-to-end project-isolation result; do not extend that earlier pass to the
entire task.
Project/global/hybrid separation is also covered by isolated component and
Chief integration regressions; no new production project sync is claimed.

The first broad run exposed unsafe existing test setup: console boot tests
started the real scheduler, and two persistence tests used temporary collections
on the configured production HTTP server. The scheduler could reconcile the
authorized global migration before the dedicated validator's first sync.
The initial global validation still found project records unchanged. However,
after documentation edits and the next broad run, final hashes detected LAEW's
project collection changing from 321 to 329 chunks. Additional CLI console/chat
entry-point tests had also started the real scheduler. This violated the task's
project-collection constraint. The files were not lost or moved, and the current
index has 45 expected project source paths, unique IDs and only project-scoped
records; Studia and every other non-global collection stayed unchanged.
No blind index rollback was attempted because only the old project digest/count,
not a complete old project-vector export, was captured before the migration.

Console boot, CLI and routing unit tests now mock background schedulers;
routing tests also stub irrelevant shared-tool construction. Persistence tests
use a disposable real PersistentClient. No runtime freshness or permission
guard was weakened. `final-collection-diff.json` and `project-index-incident.json`
preserve the incident evidence. A final regression and post-fix comparison must
be distinguished from the earlier failed end-to-end unchanged-collection check.

Evidence files include `audit.json`, `static-verification.json`,
`services-and-index-before.json`, `production-report.json`, regression logs and
the Polish report/manual checklist under the same Git-ignored runtime directory.
Documentation updates remain on disk; no deliberate project-index refresh is
performed by the migration/validator, and no further project writes are permitted
after fixing the test isolation incident. Restart existing
LAEW processes to pick up the scanner/configuration change before future syncs.

## Manual Obsidian checklist

Final regression after isolating all identified entry points: **937 passed,
2 skipped, 1 deselected** in 135.76 seconds (`pytest-post-isolation.log`).
The skips are Windows-inapplicable POSIX chmod
cases; the live Ollama case was deselected. **9 UI tests passed**;
`node --check laew/ui/app.js`, Python compilation and `git diff --check` passed.
The first focused run had one fixture model-identity mismatch across a subprocess;
the fixture now passes its explicit test identity and the restart test passes.
The application model-identity guard was not changed. Logs are in the runtime
evidence directory; the initial broad run's 936 passes precede the additional
layout-compatibility regression.

`final-audit.json` confirms no further project-index changes after the isolation
fix: LAEW remains at the incident's 329 chunks; all other non-global collections
still match the original audit. The end-to-end requirement that no project
collection change at all is **not met for LAEW**, and is not relabeled as a pass.

The detailed Polish checklist is in the final user report. Open the existing
vault, check README navigation and preserved Breadcrumbs fields, confirm the
Templates folder and insert the Inbox template into an Inbox note. No existing
Dataview query needs migration; an optional manual folder query should use the
new names. Smart plugins remain disabled; if the user later enables them, review
Smart Environment status and run queued re-import/refresh operations without
deleting `.smart-env`. Full GUI/plugin compatibility is not claimed by static
tests alone.
