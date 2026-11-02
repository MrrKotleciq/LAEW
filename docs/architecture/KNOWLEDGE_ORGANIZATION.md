---
name: Knowledge Organization
description: Ownership, promotion, user profiles and academic projects using the existing scoped RAG.
type: architecture
title: Knowledge Organization
scope: project
status: active
read_when:
  - organizing project or cross-project knowledge
  - creating an academic project or proposing a user profile
---

# Knowledge organization

This policy applies ADR-002, ADR-009, ADR-010 and ADR-011. It does not add a
memory service, agent role, or collection for each subject.

## Ownership

| Information | Owner and location |
|---|---|
| Project decisions, history, measurements and implementation details | That project's Project Memory, `@project` |
| Reusable, checked methods independent of a project | The shared Global Knowledge vault, `@knowledge` |
| Approved user facts and collaboration preferences | Logical User Profile category inside `@knowledge/profile/` |
| Academic lectures, lab notes and reports | Studia Project Memory |

A project is a context space. It need not be a software repository. A lab's
measured motor tuning belongs to its project; a sourced, generalized tuning
method can qualify for Global Knowledge. LAEW internals remain in LAEW memory.
Do not copy whole project ADRs to the vault as domain knowledge.

The canonical vault layout after the 2026-10-31 reorganization is `profile/`,
`topics/`, `research/`, `decisions/`, `inbox/`, `templates/` and a Polish `README.md`.
Technical notes live under existing domains such as `topics/ai/` and
`topics/security/`. `research/` contains analyses and explicitly qualified
investigations; `decisions/` contains cross-project rationale. Add domain
directories and optional `assets/` only when real content requires them.
`profile/` is a logical category, not a private collection or security boundary.
The original M17 category names are historical; the completed milestone and its
Definition of Done are unchanged by these path-only organizational changes.

## Inbox, templates and global source selection

`inbox/` is for raw notes awaiting review; `templates/` contains Obsidian authoring
aids. Neither is Global Knowledge RAG input. The same source-selection function
is used for initial ingestion and incremental reconciliation. It excludes
`inbox/**`, `templates/**`, `assets/**`, `backups/**`, `temp/**`, temporary/backup
Markdown suffixes and the existing hidden/cache directories. Reserved-folder
matching is case-insensitive, including legacy `Templates`. The optional
`rag.global_sources.exclude_patterns` list adds further relative POSIX glob
exclusions to these defaults; it cannot remove default exclusions. Invalid
absolute/traversal patterns fail validation. Runtime, console RAG and vault
inspection/index commands use the same policy. Project source selection remains
independent; a project may legitimately have its own `inbox/` documentation.

The vault README is intentionally indexed as organizational guidance. Exclusions
are based on location, not proof of correctness: `research/` remains searchable
and may contain drafts/hypotheses. Keep status metadata and state material
qualifications in the body because full frontmatter/status is not automatically
shown in retrieved context. Do not treat a folder name as verification.

On synchronization, moving an indexed note into Inbox removes its old records;
moving an authored note from Inbox into a selected folder indexes its new path.
Content files are not deleted by index reconciliation. Move notes rather than
creating duplicates, preserve provenance, and review content before promotion.
Restart running LAEW processes after scanner/configuration updates, then request
global synchronization. Existing collections are reconciled incrementally;
neither force-reembedding nor a new global collection is required.

The 2026-10-31 migration preserved all original note metadata and plugin/cache
files, corrected full-path wikilinks and added `.obsidian/templates.json` pointing
to `templates`. Core Templates was already enabled but had no folder setting.
Smart Connections/Lookup were installed but not enabled, and no cached source
records existed. Their `.smart-env/` data is independent of Chroma and was not
reset. See the migration evidence linked from M17 for the static checks and
manual Obsidian checklist; a file check is not a full GUI/plugin acceptance test.

## Language of global notes

The user approved the initial package on 2026-10-29 with this language rule:
write authored Global Knowledge notes, summaries, profiles and templates in
Polish. A source document originally authored in another language may retain
its native language; cite that original from any Polish synthesis. This is a
content convention, not a new runtime setting or an enforced ingestion filter.
Keep machine metadata keys, path identities, code and source identifiers intact.
LAEW repository code, tests, comments and technical documentation remain English.

## Knowledge promotion

1. Identify a project source and the claim worth reusing.
2. Draft a focused generalized note in an unindexed staging area. Preserve the
   original project document; do not automatically move or delete it.
3. Record its purpose, category, source paths or primary URLs, verification date,
   qualifications, related notes, and why it applies to other projects.
4. Verify each claim against its sources. Distinguish observations, proposed
   practices and hypotheses. Remove secrets and unnecessary personal details.
5. Check for an existing equivalent note; prefer an approved update to duplication.
6. Present the exact proposed contents and destinations to the user.
7. After explicit content approval, add or incrementally update the approved
   Markdown file via `FilesystemTool.write_knowledge_note` and a one-operation
   PermissionBroker decision. Existing notes require the SHA-256 returned by
   `view_file`; new notes use an empty hash. The operation preserves existing
   frontmatter and wikilinks, rejects hidden paths and symlinks/junctions, and
   does not allow ordinary project mutation approvals to authorize vault writes.
8. Synchronize global scope and check actual records, topic retrieval, links,
   `@knowledge` attribution, and a second unchanged sync without new embeddings.

Workbench requests global synchronization after a successful approved write and
reports whether it was requested; a request is asynchronous, not proof of
successful indexing. Check synchronization status and retrieve the changed
note. Files in Inbox and templates remain excluded. The console reports that
synchronization is required; run `rag embed global` before querying. Restricted
mode and noninteractive Workbench calls deny this approval-required operation.
The vault is not an OS sandbox: path revalidation reduces but does not eliminate
concurrent filesystem race risks. Never use this operation for secrets.

Approval of a project task is not blanket approval for profile retention or
bulk vault changes. A staging index does not satisfy M17's production-vault DoD.

## Project contract and content layout

WorkspaceService discovers direct child directories under the trusted Projects
root; Git and `.laew-project.json` are not required for discovery. Explicit
external registration is available through `registered_projects` on the service
constructor, not a registration UI. Project identity and the collection name
are derived from the canonical absolute root. Moving a project changes that
identity and requires a deliberate reindex/migration plan.

The contract consists of a selected root, derived identity, validated settings,
workspace permissions and scope synchronization. It does not require `src/`,
`tests/`, a manifest copy or an installed tool contract in every project.
GitTool is available but Git operations require a repository; academic work
does not require those operations. Some tool prompt hints still point to
project-local `tools/*/CONTRACT.md`; those files may be absent outside LAEW.
This is a prompt usability limitation, not a requirement to copy LAEW internals.

Example software layout: `README.md`, `docs/`, `src/`, `tests/`.
Example academic layout: `README.md`, `docs/index.md`, `templates/`; add real
semesters, subjects and `resources/` only when needed.

Per-project settings support:

```json
{
  "documentation_language": "pl",
  "rag_source_allowlist": ["README.md", "docs/*.md"]
}
```

`documentation_language` supports `en` and `pl`; it controls documentation,
not a mandatory conversation language. `rag_source_allowlist` is an optional,
nonempty list of project-relative POSIX Markdown glob patterns, validated on
load and save. Absolute paths, backslashes, colons and traversal are rejected.
It replaces the manifest's project source allowlist for that project only.
When absent, the previous manifest behavior remains unchanged. Python's
`fnmatchcase` lets `docs/*.md` match nested paths too, including `docs/index.md`.
This selects RAG input; it grants no extra filesystem permission. Restart the
Workbench/console after manually changing the allowlist, then synchronize
project scope; cached KnowledgeBase instances retain their original selection.
Excluded indexed notes are removed from that project's index on synchronization,
not from the filesystem. Global collection selection is unchanged.

LAEW itself keeps its narrow manifest list. Add new authoritative LAEW documents
there explicitly. Do not include `runtime/` staging or validation fixtures.

## Student notes, metadata and attachments

Start with the Studia index and four small templates (subject, note, laboratory,
report). Instantiate paths such as `docs/semestr-NN/subject/` only from confirmed
information. No enrollment history, completed subjects or lab results may be
inferred from example filenames. Repeat subject, semester and topic in the
body when they must be semantically searchable.

Use the existing documentation types: `docs` for a note/profile/template,
`index` for navigation. `profile` and `notes` are not documented schema type
values; no new type is necessary. Include `name`, `description`, `title`, `type`,
`scope`, `status`, `read_when` and tags. Optional `semester`, `subject`, `topic`
and `course_type` describe academic notes without constraining other projects.

| Layer | Current behavior |
|---|---|
| Markdown file | Holds the full YAML frontmatter and body |
| Parser | Lightweight scalar/simple-list parser; not a full YAML implementation |
| Indexed chunk | Body only, section header/index, chunk index, tags, backlinks; synchronization fingerprint/count and embedding identity are operational metadata |
| Filtering | RagTool accepts scope and max_results; no academic-field or profile-type filters |
| Source output | Logical root plus full relative file path, section, tags and raw wikilink targets in context |

Additional YAML fields do not become Chroma filters or embedding text. Prefer
simple unquoted scalars or simple lists for the parser's recognized fields.
`parse_note` recognizes `title` (not `name`) as the title; chunk section headers
come from body headings. Semantic retrieval uses chunk body text.

Use relative Markdown links for portable navigation and attachment provenance,
and full vault-relative wikilink targets to disambiguate repeated basenames.
`[[path/note#heading|label]]` is preserved as raw link metadata; it is not resolved,
validated or expanded into linked content by RAG. Markdown links remain in body
text but are not backlink metadata. This is link-preserving chunking, not graph
retrieval. Heading/alias resolution and automatic backlinks are Obsidian concerns.

Only lowercase `.md` files are indexed. PDF, presentations, images, MATLAB files
and other binaries are not parsed or OCR'd. Store them under `resources/` when
needed and link from notes, for example `[handout](../../../resources/pdf/handout.pdf)`
from `docs/semestr-NN/subject/note.md`. Write a verified Markdown summary
with page/slide references; do not claim the attachment's content is searchable.
Hidden directories, `node_modules`, `__pycache__`, `venv` and escaping links are
excluded. The Studia allowlist also excludes templates and attachments. Global
vault ingestion uses the global exclusions above: raw drafts belong in `inbox/`,
and `assets/` Markdown is not treated as domain knowledge. Vault structure counts
show physical notes, including excluded authoring aids; index counts show only
selected source documents.

## User Profile and future context management

Initially propose only `profile/preferences.md` and `profile/goals.md` using
facts explicitly stated by the user. Create `about.md`, `education.md` and
`skills.md` only after confirmed information warrants them. Separate proven
skills from learning goals. Do not infer a university, study year, proficiency,
employment or personal identity from repository examples.

Keep a review date and provenance. Reconfirm time-sensitive goals before
presenting them as current. Changes and corrections require approval of the
exact retained facts. Never store credentials, contact details, addresses,
birth dates, identifiers or health information as incidental profile content.
User preferences cannot override PermissionBroker, PathResolver or tool policy.

The existing global RAG can retrieve a profile on demand with `scope=global`.
It does not guarantee that the Chief will query it at a useful moment. No
automatic profile injection is implemented here. A future, separate context
management task may add a short, user-approved Core User Context (stable language
and documentation preferences) with an explicit budget, provenance and revision
policy; detailed skills and goals should remain on-demand RAG.

Global notes and profile text/vectors are shared across authorized projects and
local processes. FilesystemTool permits validated, explicitly approved note writes; the vault is not private from local processes.
RAG is not a per-user ACL, encryption layer or prompt-injection defense. A more
private memory tier would require a separate future design; do not claim one
exists. The broker approval controls edits, not access to indexed content.

The approved note operation accepts existing directories throughout the vault,
including drafts and templates, but excludes hidden paths, symlinks, junctions,
non-Markdown files, and paths outside the resolved vault. New notes need YAML
frontmatter with `type` and `scope: global`; updates preserve existing metadata
and wikilinks and require the SHA-256 returned by `view_file`. Files without
valid required frontmatter cannot currently be updated through this operation.
The validator checks UTF-8 and structural requirements, not whether Polish is
semantically correct. Notes should be in Polish unless retaining an original
document's language. A successful Workbench write requests asynchronous global
synchronization; the request is not proof of completion or retrieval. Existing
RAG exclusions still apply to inbox, templates, assets, and hidden content.
Path checks are repeated around the write, but do not form an OS sandbox against
a concurrent local process replacing directory entries between checks.
