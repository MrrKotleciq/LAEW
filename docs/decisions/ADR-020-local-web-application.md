---
type: adr
id: ADR-020
title: Local Web Application Architecture
name: Local Web Application Architecture
description: Provides a loopback-only browser workbench over the established LAEW runtime.
tags: [web, local-first, security]
status: Accepted
date: 2026-10-20
purpose: Add a browser interface without creating a second agent or provider runtime.
scope: browser frontend, local HTTP boundary, runtime integration
related: [ADR-001, ADR-006, ADR-017, ADR-019]
---
# ADR-020 — Local Web Application Architecture

## Status
Accepted

## Context
LAEW needs an engineering-oriented browser interface while retaining its local-first, provider-independent runtime and programmatic tool controls.

## Decision
Ship a dependency-free Python local web server for the initial slice. `laew ui` binds only to `127.0.0.1`, serves a same-origin static browser client, and exposes a deliberately small JSON boundary: runtime status and Chief Agent chat. The server composes the existing manifest, provider registry, Chief Agent, `AgentExecutor`, and tool suite; it does not create a second LLM or tool runtime.

The browser renders state returned by that boundary only. No CORS is enabled; cross-origin POSTs are rejected. The API has no arbitrary command or filesystem endpoint. Tool calls continue through the executor and existing authorization and hard restrictions.

## Alternatives considered
- A separate TypeScript/React and FastAPI deployment: richer ecosystem, but unnecessary process and dependency overhead for the first vertical slice.
- A browser client calling providers directly: rejected because it would leak machine configuration and bypass LAEW orchestration/security.
- Extending the terminal UI: rejected because browser layout and progressive operational detail are required.

## Consequences
The first slice is easy to install and launches as one command, but has no streaming, multi-user sessions, or LAN deployment. Providers remain replaceable adapters and manifest-driven Ollama remains the default. A future richer frontend may replace the static client while preserving the API boundary and loopback/security defaults.
