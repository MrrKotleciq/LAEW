---
name: UI Architecture
description: Implementation specification for the LAEW local web workbench MVP.
type: architecture
scope: local web application
status: active
read_when: [implementing or reviewing the local web UI]
---
# UI Architecture

## Shell and layout
The desktop shell has a top bar, 244px navigation rail, fluid conversation workspace, and collapsible 320px context panel. The top bar reports the selected project plus provider/model only when the backend has resolved them. Below 900px the navigation condenses and the context panel overlays; below 620px navigation is hidden.

## Behavior and state
The center contains the current task, readable Chief Agent transcript, and persistent text composer. Submission shows an in-progress state and renders either the actual final response or an actionable error. The Run panel summarizes actual executor steps; Sources explicitly says unavailable until the runtime supplies provenance; Context shows only backend-reported workspace context. No-project, provider-unavailable, empty, successful, error, and no-source states are explicit. Confirmation behavior is inherited from the executor; the UI must not bypass it.

## Responsibilities and security
The static browser client renders state and posts messages. The Python backend owns manifest loading, provider construction, Chief Agent execution, and tool policy. It binds loopback only, offers no permissive CORS or arbitrary filesystem/command endpoint, and preserves all existing tool permissions. Model paths and machine-specific settings remain server-side.

## Visual and accessibility system
Dark graphite tokens are centralized in CSS: background `#1B1F25`, surfaces `#242930`/`#262B33`, accent `#3A6F6D`, warning `#C9A96A`, and error `#C66F72`. Use sans-serif UI text and monospace for runtime identifiers/logs. Controls have visible focus; semantic forms and live transcript updates support keyboard and assistive use.

## MVP and exclusions
MVP includes launch, responsive shell, status, message submission, Chief Agent result/error, and real executor step summaries. Excluded: streaming tokens, cancellation, attachments, project switching, provenance/RAG display, Knowledge/Activity/Models/Settings implementations, theme switching, authentication, remote access, and multi-user support.
