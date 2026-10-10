# LAEW Document Metadata Schema

## Purpose

Define the shared metadata model for LAEW documentation while preserving existing repository conventions.

This schema has two layers:

1. **Core metadata** — the preferred model for new or substantially rewritten documents.
2. **Repository extensions** — established LAEW metadata values that must be preserved when already in use.

The schema is not a mandate to rewrite every existing document. Existing valid conventions take precedence unless an explicit migration is requested.

## Frontmatter applicability

Use YAML frontmatter for new or substantially rewritten documents when the document type supports metadata.

Do not add frontmatter merely for consistency to documents whose repository convention intentionally omits it, such as `docs/history/*.md`.

## Canonical frontmatter

```yaml
---
name: Tool System
description: Defines the architecture and execution model of LAEW's controlled tool layer.
type: architecture
scope: project
status: active
tags:
  - laew
  - architecture
  - tools
---
```

Not every document needs every property. Required fields are determined by document type and repository convention.

## Core Properties

### `name`

Logical name of the document.

Use `name`, not `title`.

Prefer a value that clearly identifies the document independently of its filename.

### `description`

One concise sentence explaining what the document contains and why it may be relevant.

The description supports a decide-before-read workflow: an agent should be able to use it to decide whether the document is worth reading in full.

Do not turn `description` into a summary of the entire document.

### `type`

Preferred values for new documents:

- `project`
- `architecture`
- `decision`
- `specification`
- `research`
- `knowledge`
- `source`
- `guide`
- `task`
- `index`

Use the most specific existing value that accurately describes the document.

Do not invent a new type for a minor distinction.

### `scope`

Preferred values:

- `global`
- `project`

Use `project` for information belonging primarily to one project.
Use `global` for knowledge intended to be reused across projects.

Do not use `scope` to describe lifecycle or maturity.

### `status`

Preferred values:

- `draft`
- `active`
- `implemented`
- `deprecated`
- `superseded`
- `archived`

Preserve an existing repository-specific status convention when it is already established and meaningful.

### `tags`

Use tags for topical classification.

Good:

```yaml
tags:
  - laew
  - security
  - filesystem
```

Bad:

```yaml
tags:
  - depends-on-tool-system
```

Do not encode semantic relationships in tags. Use Breadcrumbs properties instead.

## Repository Extensions

LAEW already contains established document types outside the preferred core set. These values are valid when used by existing repository conventions and must not be mechanically normalized away.

Recognized existing extensions include:

- `adr` — architectural decision record files using the repository's established ADR convention.
- `roadmap` — roadmap and milestone planning documents.
- `status` — project-state/status documents such as `PROJECT_STATUS.md`.
- `docs` — general canonical project documentation such as `LAEW_CONTEXT.md`.
- `report` — completed review, benchmark, baseline, or milestone-report artifacts.

When modifying an existing document with one of these types, preserve the type unless the user explicitly requests a type migration.

Do not automatically map:

```text
adr      → decision
roadmap  → project
status   → another type
docs     → another type
report   → research / architecture
```

The repository's established meaning is more authoritative than the generic core schema.

## Other Existing Metadata

Existing documents may contain additional meaningful properties that are not part of the core schema, for example:

```yaml
read_when:
  - ...
```

Preserve such properties when they are already meaningful to the repository or its tooling.

Do not remove or rename established metadata merely because it is not listed in the core schema.

## Relationship Properties

Breadcrumbs relationship properties are separate from descriptive metadata.

Supported relationship fields:

```text
up
down
same
next
prev
implements
depends-on
defined-by
derived-from
related
supersedes
```

Example:

```yaml
up: "[[LAEW Architecture]]"
implements:
  - "[[Filesystem Security]]"
depends-on:
  - "[[Security Model]]"
defined-by:
  - "[[ADR-002 Tool Architecture]]"
derived-from:
  - "[[External Specification]]"
related:
  - "[[Chief Agent]]"
supersedes:
  - "[[ADR-001 Legacy Architecture]]"
```

Relationship fields should contain only meaningful relationships. Do not add empty fields.

## Migration Rules

- Do not mass-normalize existing document types to match the core schema.
- Preserve intentional repository conventions.
- Add missing metadata only when its value can be established confidently.
- Do not invent semantics to satisfy a schema field.
- Do not force frontmatter onto files whose repository convention intentionally omits it.
- Treat ambiguous classification as a case for review, not automatic conversion.
- Keep document bodies unchanged unless the migration explicitly requires a content change.

## Design Principle

The schema exists to improve discoverability, retrieval, and consistency — not to make every document identical.

Prefer a smaller amount of correct metadata over a complete set of speculative metadata.
