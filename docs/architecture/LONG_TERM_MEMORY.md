---
type: docs
title: Long-Term Memory
scope: memory storage, recall, extraction, settings, recovery
status: active
read_when:
  - changing memory extraction or retrieval
  - configuring memory or recovering its index
---
# Long-Term Memory

## Ownership and composition

`laew.memory.store.MemoryStore` owns SQLite records and transactions.
`MemoryService` implements recall, proposals, approval, extraction, synchronization
and recovery. `integration.py` composes the existing provider/embedding registry,
ChromaVectorStore and one lifecycle-managed worker per application process.
`MemoryTool` prepares immediate review proposals for explicit remember requests;
it cannot approve them or access an arbitrary project.

The canonical taxonomy is defined in `laew/memory/categories.py`: `preference`,
`education`, `interest`, `skill`, `goal`, `decision`, `constraint`, `fact`.
Categories describe information types; travel intentions use `goal`, travel style
uses `preference`, and past experience/achievements can use `fact`. No topic tags
or category migration are required. Category descriptions generate MemoryTool
metadata, native function enums, extraction instructions/schema, and the Settings
selector through `/api/memory/state`. Local providers retain the fenced-text
tool protocol and receive the same guidance in the tool description.

All application writes (including API, CLI, proposals, review approval and Auto)
validate the shared contract before committing. Outer whitespace/case and an
explicit list of English plural aliases are normalized to canonical singulars;
unknown values are rejected, never guessed from topics. MemoryTool errors carry
`ERR_INVALID_INPUT`, `field`, `accepted_categories`, `retryable`, and correction
instructions through the tool runtime, permission broker and Chief observations.
Corrected calls use the existing iteration, time and duplicate-call limits;
native retries must use a new call ID. A successful explicit call creates a
review proposal, never an active-memory approval.

SessionStore remains the JSON conversation source of truth. No full transcript is
stored in SQLite. Global Knowledge remains the Obsidian vault. No memory worker
writes Markdown or modifies `laew_global` or a project RAG collection.

## Storage and schema

The default database is `memory/memory.db` alongside the configured SessionStore
directory (normally `runtime/memory/memory.db`). `LAEW_MEMORY_STORAGE` overrides
its path for isolated runs; the composition then derives a separate index name
from that path. Changing a SQLite path is not a substitute for isolating all test
services, histories and schedulers.

SQLite schema version 2 includes:

- `memories`: stable ID, scope, nullable project ID, category, content, normalized
  fingerprint, status, timestamps and version. A partial unique index prevents
  exact active duplicates within the same scope.
- `memory_sources`: conversation/event references, origin and timestamp.
- `memory_revisions`: a unique revision per memory/version, content, status and reason.
- `memory_proposals`: Create/Update proposals, expected target version, decision
  status, idempotency key and timestamps.
- `extraction_checkpoints` and `extraction_jobs`: per-conversation position, durable
  bounded work fragments, selected model, retry time and expiring ownership token.
- `memory_index_outbox`: durable memory/version operations, completion and errors.
- `memory_settings`, `memory_project_settings`: global defaults and partial local
  overrides. Schema v1 databases gain the project override table on initialization.
- `memory_fts`: FTS5 lexical fallback, updated with the canonical record transaction.

Connections enable foreign keys, WAL and a ten-second busy timeout. Mutations use
`BEGIN IMMEDIATE`; writes, revisions, FTS and outbox entries commit together.
Unknown future schema versions are rejected. Memory content is limited to 2000
characters. Recognizable credentials are rejected; arbitrary secret detection is
not guaranteed, so credentials should never be put in conversations or memories.

Deletion marks a record deleted, creates a revision, removes FTS content and queues
index deletion. It immediately excludes the record from recall. Revisions and
sources remain in SQLite for audit; deletion is not secure erasure.

## Recall and isolation

General Chat can use User Memory only. Project Chat can use User Memory and its
own stable project ID. SQLite validates scope even after Chroma metadata filtering.
No request automatically searches every project.

Recall performs no LLM request. It uses the existing embedding service for semantic
search, then validates canonical status and exact indexed version. On semantic
failure it uses scoped FTS5 when enabled. Empty stores avoid embedding requests.
Results are capped by count and by a conservative UTF-8-byte token upper-bound
estimate of the entire generated memory block, including its labels and IDs.
This deliberately underuses some providers' token budgets rather than exceeding
them. Only selected memories are placed in a clearly marked system-context block;
they are never appended to persistent user history. Current user statements take
precedence. Workbench Context receives the actual selected records through a
separate `memory` stream event. Reopening a transcript without a new run does not
claim that historical memory context has been reconstructed.

## Extraction and approval

Defaults are recall enabled, maximum 5 memories, estimated budget 400 tokens,
Review mode, every 5 completed turns, semantic retrieval enabled and FTS fallback
enabled. The default extraction model is the active chat model. A configured
explicit provider/model/account overrides it. Provider credentials remain in
Models & Services. No provider fallback is chosen by memory extraction.

A completed turn is a non-generated user event belonging to a run finalized as
completed, not an SSE fragment or tool call. New enrollment establishes a
checkpoint at the existing transcript end so ordinary chat does not backfill old
history. Automatic enqueue considers only newer completed turns. Manual analysis
also considers the enrolled, unprocessed fragment; it does not silently reanalyze
all previously checkpointed turns.

Jobs persist before execution and capture the model selection at enqueue time.
The worker uses a 600-second lease token and processes one extraction at a time
per process. It sends at most 24000 characters of the selected user/assistant
fragment, excluding tools, generated repair prompts and incomplete runs. Accumulated fragments are split at completed-turn boundaries; a single oversized
turn remains pending with an error. Nearby lexical/semantic memories help the
model identify equivalent facts and replacements. Native providers can return a
single structured `memory_candidates` function call; text providers return JSON.
Python validates shape, category, scope, known target, verbatim user evidence and
confirmation. Questions and clearly quoted evidence cannot establish a fact.
Hypotheticals, transient content and semantic interpretation also depend on the
model's extraction instructions and are not perfectly detectable by syntax alone.

Review creates persistent proposals only. Approve checks the target version and
commits the new active state/outbox atomically. Reject leaves active memory alone.
The editor can change proposal content before approval. Duplicate findings add
source references without creating another active fact. Auto only automatically
saves a new directly quoted fact with no existing memory of that category in the
same scope; paraphrases and possible conflicts remain reviewable. Off disables
automatic processing; explicitly requested manual jobs can still run. Switching
Off while an automatic request runs prevents its candidates from being committed.

Failures retain the job, diagnostic error and unchanged checkpoint, with retry
eligible after 60 seconds. Checkpoints advance only in the transaction committing
all validated outcomes, including an empty candidate list. A stale worker cannot
commit after another process has acquired its lease token. A recognizable new
fact may still be proposed again after a genuinely new conversation fragment;
this is not a claim of perfect semantic deduplication.

## Index synchronization and recovery

The default Chroma collection is separate from vault/project collections.
Memory/version outbox writes are transactional. A process-local mutex and shared
OS lock serialize index writes across processes. Upserts are idempotent and use
the latest SQLite record. Completion is marked only after Chroma succeeds. If a
record changes during an upsert, its newer outbox entry remains pending; stale
hits are rejected by recall meanwhile. The worker resumes pending outbox/jobs on
Workbench/CLI startup, without scanning historical conversations.

Retry synchronization preserves canonical records. Rebuild enqueues all SQLite
records and recreates only the dedicated memory collection, allowing recovery
from a removed or incompatible index. Pending batches are processed in groups of
100. SQLite, outbox and checkpoint data must be backed up together using SQLite's
backup facilities or while the application is stopped; copying only the main file
while WAL writes are active is not a reliable backup procedure.

## Settings and API

The existing Settings page contains Appearance, Project defaults and Memory.
Theme uses the existing localStorage preference and was moved with user approval.
Workspace language defaults live in `runtime/settings.json` alongside sessions.
Existing explicit `.laew-project.json` language values remain overrides. New or
reset values inherit the global default.

Right-click a real project, press its context-menu key/Shift+F10, or use its gear
button to open the large project settings dialog. Language and individual memory
values can override their defaults; unchecked memory values inherit later global
changes. General Chat is not a project. Permission mode is a quick control on the
chat heading, not a global/project Settings field.

Memory Settings provides Recall, Off/Review/Auto, interval, extraction model,
advanced recall/index settings, real SQLite/Chroma diagnostics, memory filters,
Add/Edit/Delete/View source, proposals and Approve/Reject/Edit, manual analysis,
synchronization retry and index rebuild. Mutations validate scope in the backend.
Manual asynchronous actions report that they were queued; Refresh shows current
queue counts and errors. They do not claim completion on enqueue.

API routes are `/api/memory/state`, `/api/memory/get`, and POST
`/api/memory/{settings,add,update,delete,decide,analyze,sync,rebuild}`.
`/api/settings` reads/writes global language defaults. `/api/project/config`
reads project inheritance and writes language or memory overrides. They share the
existing loopback/Origin boundary. Canonical record edits require expected versions.

## CLI

`laew chat` and `laew chat --general` use recall. Ordinary persisted chats create a
SessionStore conversation on the first actual input; named legacy sessions remain
supported and are not migrated. `--no-persist` does not enable automatic extraction.
`laew memory list|add|delete|analyze|status|sync` uses the same service. Use `--general`
for User Memory alone; project operations are bound to the configured project root.
Deletion requires `--id` and `--version`. Manual analysis requires `--conversation`
and an explicit `--model` when no fixed extraction model is configured. It never
chooses a potentially paid replacement model.

## Validation and limits

Offline tests use temporary SQLite, sessions, projects and knowledge directories,
block production network ports, and disable memory workers unless explicitly
under test. Real Chroma integration launches a disposable server with a temporary
data directory. The opt-in Gemini acceptance report is in
`runtime/validation/memory-live-20261102-structured/report.json`: extraction in
Review, approval/indexing, recall in a fresh Chief Agent, then reviewed preference
replacement. Each live model request was followed by a 61-second pause. The first
text-JSON attempt was rejected without moving its checkpoint; the structured
native-function run passed. GUI validation uses a separate fixture with synthetic
providers and an independent SQLite/SessionStore, never the production profile.

Extraction quality depends on the selected model. Local small models may produce
invalid output; such jobs remain pending and diagnostically visible. Very long
fragments require user intervention rather than silent checkpoint advancement.
Memory is a single-user local feature, not a multi-tenant authorization service.
