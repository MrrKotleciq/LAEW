---
name: Chroma recovery procedure
title: Chroma recovery procedure
description: Synthetic en retrieval fixture.
type: docs
scope: global
status: active
tags: [chroma]
read_when:
  - Evaluating retrieval
---

## Recovery

Keep the approved Markdown when Chroma is unavailable and retry indexing after recovery.

## Deletion

Upsert the current chunks and delete obsolete chunk IDs after a document shrinks.
