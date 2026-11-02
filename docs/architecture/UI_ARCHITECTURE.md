---
name: UI Architecture
description: Engineering Workbench layout, provider management, theme and interaction contracts.
type: architecture
scope: local web application
status: active
read_when: [implementing or reviewing the local web UI]
---
# Engineering Workbench UI

The dependency-free HTML/CSS/JavaScript client uses the existing loopback HTTP boundary and one Chief Agent, AgentExecutor, PermissionBroker and project RAG for every provider. Provider-specific inference and authentication stay in the backend. See [Unified providers](../CLOUD_CHAT.md).

## Layout and connections

The shell contains project navigation, a conversation with a persistent composer and a collapsible Context/Run/Sources panel. Models & Services is a separate main view; navigating there does not replace conversation nodes or switch the active model. Its provider cards report authentication configuration separately from connectivity. Catalog checks prove catalog reachability, not inference or billing eligibility. Counts come only from returned catalogs.

The composer uses a native keyboard-accessible grouped model select. Catalogs are discovered for local backends and configured cloud accounts; unlisted exact model IDs may be entered in Models & Services. Use in chat explicitly activates that selection. The backend validates actual model support on use. While a run is active the model selector, credential editor, project switch and conversation reset are disabled. Project and transcript survive model changes.

API keys can be entered only for the API-key methods. POST /api/cloud/key requires same-origin JSON, validates the fixed provider allowlist and refuses changes during an active run. Windows persists values as OPENAI_API_KEY or GEMINI_API_KEY under the current user's Environment registry key and updates the current backend environment. Explorer is notified for newly launched applications; already-running terminals retain their inherited values. The API returns configuration status only. The UI clears the password field on submission; no key is saved in browser storage. This storage is the Windows user environment, not an encrypted credential store. OAuth retains its protected keyring and existing registration, refresh and sign-out flow. Non-Windows installations use backend environment configuration. Local endpoint editing has no existing backend contract and is shown as manifest/environment configuration guidance.

## Theme and accessibility

Light, Dark and System preferences use the laew-theme browser-storage key. System is the initial default and tracks prefers-color-scheme changes. A synchronous head script applies the theme before styles render. Storage failures fall back without breaking startup. CSS custom properties define surfaces, typography, borders and semantic colors. Dark Violet uses background #0D0B15, surface #171425 and elevated #211B32; the main action uses #6D28D9 with white text and accent text/focus uses #A78BFA. Light uses #F6F5FA, white surfaces and #6D28D9 accents. Both preserve semantic error, warning and success colors. Reduced-motion preferences disable transitions.

Tabs have tablist/tab/tabpanel roles, a shared panel relationship, aria-selected and roving tabindex. Arrow keys, Home and End select tabs. Native selects provide keyboard and Escape behavior. Escape closes narrow navigation/details. Dialogs use the native HTML dialog focus/keyboard contract. Small screens use drawers and a single conversation column; long content scrolls inside its own region. Mobile controls have at least 44px height.

## Context and execution state

ui-state.js owns the active detail tab. Rendering updates its content, selection, tabindex and ARIA together. A new run resets the automatic-switch guard. The first tool step or approval selects Run once. Later tool events and finalization preserve a user's subsequent manual selection. Text-only runs do not force Run. Project reset returns to Context. Polling does not rebuild controls while a user has focus inside the panel.

Context groups Active project, expandable workspace paths, Retrieved knowledge, Last response usage, Project settings, Permissions and Memory. Token numbers represent the reported response usage, not a fabricated context-capacity gauge. Synchronization state and last success are explicitly historical sync data, not a current ChromaDB connection check. Sources are shown only from actual step provenance. Direct successful FilesystemTool.view_file events are labeled file reads; the UI does not invent a path when the event omits it.

Run shows pending approval and its accepted decision, then uses the actual tool result for Completed, Failed or Denied. Approved means awaiting a result, not success. Stop invalidates pending controls and marks pending UI steps Cancelled; backend cancellation semantics remain authoritative. Tool duration and running-start timestamps are not reported by the current event contract and are not fabricated.

## Verification boundaries

Node tests cover Markdown, stream framing, panel policy and theme persistence/system changes. Backend tests mock Windows credential persistence and exercise the actual same-origin HTTP key boundary. Browser checks use a disposable WorkspaceService fixture with synthetic model catalogs/responses and real PermissionBroker/FilesystemTool operations restricted to its temporary project. They do not establish live model eligibility. Production scheduler and ChromaDB are not started for visual QA.
