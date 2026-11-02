---
type: roadmap
id: M17
title: Second Brain & Global Knowledge Integration
name: Second Brain & Global Knowledge Integration
description: Make the Obsidian vault a real, curated knowledge source (ADR-002) with structured organization, link-aware chunking, and proper scope separation between @project and @knowledge.
scope: project
tags:
  - knowledge
  - obsidian
  - second-brain
  - global-knowledge
status: completed
purpose: Make the Obsidian vault a real, curated knowledge source (ADR-002) with structured organization, link-aware chunking, and proper scope separation between @project and @knowledge.
read_when:
  - implementing Obsidian vault integration
  - Milestone 17 (Second Brain & Global Knowledge Integration)
implements:
  - ADR-002
---

### Milestone 17: Second Brain & Global Knowledge Integration
**Goal:** Make the Obsidian vault a real, curated knowledge source (ADR-002).
**Scope:** Stand up the `knowledge/` vault configured in the manifest; ingest and index the global vault into `@knowledge` RAG with structured organization (Knowledge, Decisions, Research, Templates) rather than a dumping ground; enforce project-specific docs stay in-repo, cross-project knowledge in the vault (ADR-011); link-aware chunking to preserve Obsidian backlinks.
**Dependencies:** None functional; Milestone 14 for retrieval latency.
**Tests:** Vault ingestion, scope separation (`@project` vs `@knowledge`), link preservation, source attribution in retrieved context.
**Definition of Done:** A populated Obsidian vault is indexed and retrievable as `@knowledge` context with correct scoping and sources.

### Vault reorganization — 2026-10-31

M17 remains **completed**. The same vault and `laew_global` collection now use
`topics/`, `research/`, `decisions/`, `profile/`, `inbox/`, `templates/` and a
Polish README. All eight existing notes and their frontmatter were preserved;
qualified wikilinks were updated. Inbox, templates and auxiliary/cache folders
are excluded by one shared ingestion/reconciliation policy. The README is
indexed as organization guidance, and research remains searchable.

After migration, ten physical Markdown files yield eight indexed documents
and 35 chunks. Old path records and the already-missing test-note record are
absent. Eight production questions, three live Chief answers and a fresh-process
global sync verified the current sources and unchanged embedding avoidance.
The dedicated validator did not synchronize projects; an unintended LAEW index
refresh during subsequent CLI regression is recorded in the report. See
[the reorganization verification](M17-Vault-Reorganization-2026-10-31.md) for
backup, link/plugin checks, regression results and the manual Obsidian checklist.
The dated completion snapshot below retains the original layout/count evidence.

### Completion — 2026-10-29

**M17 is completed.** The user explicitly approved the proposed knowledge and
profile contents, requiring authored global notes to be Polish while allowing
native-language source documents. Eight approved Polish notes were added to
`C:\ROOT\Knowledge`; the existing synthetic note was translated with its code
and original backup preserved. The four manifest categories are populated.
The actual `laew_global` collection contains nine documents and 31 chunks,
including six reusable materials and two approved profile notes. The synthetic
note is retained but is not counted as curated engineering knowledge.

Production validation verified file/chunk consistency, metadata, links, seven
topic queries, global/project/hybrid attribution, a real document update and
zero embeddings on an unchanged sync. Two live Chief Agent runs through a
separate Workbench HTTP listener used actual project/global sources and
answered the requested measurement and PDF/evaluation questions correctly.
Existing project collections and Obsidian configuration were unchanged by vault
deployment. The legacy `laew_project` collection remains absent.

See the [current verification and historical preparation record](M17-Knowledge-Preparation-2026-10-29.md)
for the complete acceptance matrix, earlier infrastructure evidence, regression
results and a documented broad-query relevance limitation. Local production
evidence is in `runtime/knowledge-deployment-2026-10-29/production-report.json`
and `final-consistency.json`. User Profile and Studia remain practical uses of
the existing scoped RAG, not new mandatory milestone criteria. The dated
in-progress sections below preserve earlier observations and are superseded
by this completion record.

### Implementation Status — 2026-10-26

- The Obsidian parser, link-aware chunk metadata, scoped stores, reranking, and budgeted source attribution are implemented in `laew/rag/`.
- The Chief Agent runtime now registers the read-only `RagTool`; project and global roots are resolved through the trusted workspace aliases, and project/global retrieval loads only the requested source (or both for hybrid scope).
- The manifest points the Second Brain path to `@knowledge`. Console vault inspection and RAG commands resolve that alias and reject paths outside the trusted vault.
- Automated verification covers fixture ingestion, source separation, alias/traversal validation, embedding failures, and retrieval through the actual `AgentExecutor` tool loop.
- `C:\\ROOT\\Projects\\LAEW\\Knowledge` is LAEW-local content indexed under `@project`; `C:\\ROOT\\Knowledge` is the global vault resolved by `@knowledge`.
- Embeddings use the OpenAI-compatible llama.cpp `/v1/embeddings` client on a separately configured server. Set `models.roles.embedding.model_name` to the ID exposed by that dedicated server; the repository does not select or assume an embedding model file.
- The global vault currently has no visible Markdown notes. The configured embedding endpoint/model could not be verified as available in this environment. Mocked retrieval tests pass, but live embedding and retrieval from populated global content remain unverified; M17 stays **in progress**.

### Project-scoped indexes and synchronization

### Knowledge organization preparation — 2026-10-29

See [the preparation verification](M17-Knowledge-Preparation-2026-10-29.md) for
the academic-project audit, minimal per-project RAG source configuration,
reviewable candidate contents and isolated real-model retrieval evidence.
M17 remains **in progress**: the actual global vault still contains one
synthetic note, and explicit approval of the proposed real contents is pending.
Staging retrieval does not satisfy the production-vault Definition of Done.

### Final validation in progress — 2026-10-28

See [the verification matrix](M17-Verification-2026-10-28.md) for current
evidence, criteria, limitations, and out-of-scope work.

The target `C:\ROOT\Knowledge` was inspected read-only on 2026-10-28: it
contains one Markdown file, `test-global-knowledge.md`, a synthetic integration
test note. It does not yet demonstrate the populated, curated cross-project
vault required by the scope and Definition of Done above. No minimum number of
notes, automatic curation process, or prescribed metadata schema is specified;
the named Knowledge, Decisions, Research and Templates organization is the
milestone's stated structure. A synthetic fixture is evidence of the integration,
not evidence of a populated real Second Brain. M17 remains in progress until the
real vault is populated and its actual content is indexed and retrieved with
scoped sources. Validation must not modify the user's vault without a separate
content migration or curation task.

The isolated live validation `runtime/m17-validation-e1e30ef7467f/report.json`
confirmed four real-model project/global/hybrid queries and incremental sync;
`tests/integration/test_rag_http_crash.py` checks recovery from a deterministic
partial upsert against a separate HTTP Chroma server. Further failure-scenario
results are recorded separately; previous browser results are not presented as
new runs. Full Workbench permission-mode and TerminalTool acceptance belong to
those components and do not define M17 completion.

An isolated Workbench and separate local Chroma server were tested with the
configured llama.cpp chat and embedding servers. Project A and an explicitly
registered external Project B returned their own codes and `@project` sources;
the shared test vault returned its global code and `@knowledge` source. A
hybrid Chief Agent query returned both. The browser displayed streamed answers
and project sources for both projects. In the isolated store, incremental
add/update/delete, unchanged embedding avoidance, simulated embedding failure,
and Chroma outage/recovery were verified. An offline process test interrupted
an actual partial upsert in a temporary persistent Chroma store and verified
that retrieval was blocked until repair.

At that point, Workbench failure/restart, real-model behavior during failed
synchronization, and the populated curated real vault had not been fully
verified. Full permission acceptance is tracked outside M17. Replacement
characters were reported during earlier observation; later byte and code-point
checks showed that some apparent examples were console display artifacts, but
do not establish the cause of every prior observation.
Run `python scripts/validate_m17.py --run --model` for an isolated validation;
the Git-ignored runtime workspace contains the report and test database.

On 2026-10-28 the legacy `laew_project` collection was exported and verified
under the Git-ignored `runtime/backups/` directory. After two project-only
synchronizations found 44 documents unchanged and generated no new embeddings,
the verified legacy collection was removed. The project-specific collection
contained 285 chunks and Global Knowledge contained one chunk. The legacy
backup remains available for recovery; multi-process synchronization and a
full Workbench acceptance run still require verification.

The existing destination collection can contain independently synchronized
records and metadata. Migration must stop if the destination differs from the
legacy collection; never delete or overwrite those records to force migration.

- Project collections are derived from the canonical absolute project path. The configured `project_collection` identifies the legacy collection for explicit migration; it is never deleted automatically. Global Knowledge continues to use `global_collection`.
- Before starting a workbench or console that would populate a new project collection, identify the owner of the legacy collection. Run `laew rag-migrate "<project path>" --confirm-owner "<same confirmed owner path>"` only after confirming the legacy collection belongs exclusively to that project. Migration refuses incompatible destination records or missing embedding identity and does not regenerate vectors. The legacy collection remains the rollback source. Stop other LAEW processes during migration.
- The Workbench and interactive console start project and global synchronization, and periodically synchronize global knowledge every 30 minutes while the process runs. Selecting a Workbench project requests synchronization for that captured project. Workbench Context shows status and offers manual synchronization; the console provides `rag embed [project|global] [force]` and `rag stats`.
- Freshness is established by a successful incremental synchronization in the current process; after restart it is unknown until synchronization succeeds. A host-local OS lock serializes access to each configured endpoint and collection; a durable generation marker invalidates another process's previous freshness after any synchronization. An interrupted synchronization leaves an incomplete marker and blocks retrieval until a successful retry. A sync is a point-in-time snapshot: source changes made afterward are reflected at the next synchronization. Chroma writes remain non-transactional. Processes must share the same OS temporary directory and canonical endpoint configuration for this coordination; clients on different hosts or non-LAEW clients do not participate.
- The Workbench can accept explicitly registered external project paths through its service constructor; it does not scan arbitrary filesystem locations or expose a registration UI.
