---
type: docs
title: Persistent conversation history
scope: session storage and conversation execution
status: active
read_when:
  - implementing conversation persistence
  - resuming conversations or tool calls
---

# Persistent conversation history

Workbench and `laew chat` use the existing SessionStore directory configured by `memory.session.storage`. Each new conversation is a versioned `laew.conversation` JSON document with a UUID, title, immutable general/project scope, project ID, timestamps, status and ordered events. Legacy named console/chat sessions remain separate version-one documents in the same directory and are readable by the existing commands. They are not automatically migrated or assumed to contain missing tool calls.

Events have stable IDs, sequence numbers, timestamps, run IDs, a kind and execution status. Assistant messages, calls and results retain the provider-neutral roles, call identifiers and content needed for continuation. Recognizable credentials are redacted before writing. The implementation retains only bounded Gemini thought signatures as optional provider continuation metadata; other raw provider transport payloads are discarded. Redaction is heuristic and cannot identify every possible secret, so credentials should not be entered into conversations.

Each update is written to a same-directory temporary file, flushed and atomically replaced. A per-conversation OS lock serializes modifications, and a separate exclusive run lease prevents concurrent CLI/Workbench runs and deletion or renaming during a run. Locks live inside the configured store so processes sharing it use the same lock paths. IDs are validated before path construction.

AgentExecutor emits events before tool execution and after each result. On restart, abandoned runs are marked failed under the run lease. Missing results are represented in the provider context as unknown outcomes; historical calls are never executed during restoration. An interrupted or failed response is not presented as a completed answer. Tool data is historical evidence, not authoritative current project state.

General conversations have a null project ID; project conversations carry the stable project identifier. Workbench requires the active scope to match the conversation before starting a run. Opening a conversation explicitly selects its scope, and project tools remain subject to the existing resolver and PermissionBroker. Scope cannot be changed through the conversation API.

Workbench lists conversations, opens them, renames them and deletes them after confirmation. New conversations are persisted on the first message; drafts stay in the browser while switching views. `laew chat --general --new-conversation` creates a general conversation; `laew chat --conversation ID` resumes a conversation and `laew chat --list-conversations` lists them. A project conversation can be resumed only when its ID matches the CLI's configured project. Legacy `--session` and `--resume` keep their original behavior.

This is conversation history, not Long-Term Memory: no cross-conversation extraction, semantic recall or memory management is performed.
