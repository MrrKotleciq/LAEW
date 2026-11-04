---
type: architecture
title: Global Knowledge Curation
scope: completed turns, proposal review, Obsidian publication, Global RAG synchronization
read_when:
  - Changing how conversation knowledge becomes a global note
  - Diagnosing proposal approval or indexing failures
---

# Global Knowledge Curation

Workbench and persistent CLI chat register `KnowledgeProposalTool` for the current conversation. It accepts a title, reason, Markdown addition, source classification, verification state, and exact user evidence. Updates additionally identify an existing `@knowledge` Markdown note. The tool has create-proposal, update-proposal, and status operations. Publication runs separately from agent tool calls.

An independent worker analyzes completed turns, five by default. SQLite tracks the initial enrollment checkpoint, leased windows, and retries. Analysis uses bounded conversation text and accepts up to three candidate results. Short memories and project-specific candidates are skipped. Explicit evidence and source scope are checked against SessionStore. Source classification records uncertainty and does not independently verify an external claim. Technical conclusions still need user review. Existing Global RAG can suggest candidate documents when fresh. The service also reads eligible vault notes to check content and suggest related targets. Review handles ambiguity explicitly.

Settings → Knowledge controls the interval and automatic analysis. The default model source is the explicitly configured Memory extraction model, including project overrides. If no model is configured, extraction waits. Selecting **Active chat model** uses the active provider and model for a separate request, which may incur API charges. Manual analysis uses the same selection. The curation database is separate from memory records and uses the existing provider registry and conversation events.

The nonmodal drawer shows proposals from the selected conversation scope. Users can inspect the path, provenance, Markdown and diff, edit, defer, reject, or approve. Batch selection requires previewing each proposal version. Approval checks the reviewed version and file hash. If the file changed, a fresh proposal is required. Updates preserve existing metadata and wikilinks. Existing vault folders and source exclusions govern destinations.

An approval commits the proposal version before invoking the existing PermissionBroker and FilesystemTool writer. The broker still enforces restricted mode. Recovery checks the exact bytes when resuming a committed approval. Creation publishes a flushed temporary file without overwriting an existing destination. Update replaces an existing file after checking its current hash. The writer verifies the saved bytes before scheduling ingestion.

An applied proposal can remain pending in Global RAG if the service is unavailable. The worker retries from SQLite and uses the existing scope synchronization. It scans the vault, embeds changed documents, and removes obsolete chunks. The drawer reports write and index outcomes separately. The [Global RAG audit](../reports/GLOBAL_RAG_AUDIT.md) describes the broader freshness and quality limitations.
