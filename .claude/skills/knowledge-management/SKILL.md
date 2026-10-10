---
name: knowledge-management
description: Manage LAEW Markdown knowledge in Obsidian. Use when creating, modifying, splitting, organizing, linking, indexing, or reviewing project and global knowledge documents.
---

# LAEW Knowledge Management

Use this skill to keep the Obsidian knowledge base structured, discoverable, and useful to both humans and agents.

## Core rules

- Prefer atomic documents with one coherent purpose.
- Prefer **3 meaningful links over 20 weak links**.
- Do not create a link merely because two notes mention the same topic.
- Search existing knowledge before creating a new document.
- Metadata helps an agent decide what to read; it must not replace the document itself.
- Preserve existing user-authored content unless the current task requires changing it.
- Do not perform a vault-wide migration unless explicitly requested.

## New documents

Every new knowledge document should use the metadata schema in `references/schema.md`.

At minimum, provide:

- `name`
- `description`
- `type`
- `scope`
- `status`
- `tags`

Add Breadcrumbs relationship properties only when the relationship is materially true. Use `references/relationships.md` for the allowed fields and their meaning.

## Existing documents

When editing an existing note:

1. Preserve meaningful content and existing valid relationships.
2. Normalize metadata when relevant to the current task.
3. Add missing metadata when the document is substantially changed.
4. Do not rewrite unrelated notes just for consistency.

## Before creating or splitting

1. Search for existing notes covering the same concept.
2. Decide whether to extend an existing note or create a new one.
3. If splitting, identify independently useful concepts first.
4. Preserve important information and relationships.
5. Give resulting notes their own metadata.
6. Keep a parent/MOC when it still provides useful navigation.

Use Note Refactor Plus when helpful, but verify frontmatter after splitting.

## Smart Connections

Treat Smart Connections as a **candidate discovery tool**, not an authority.

Workflow:

`Smart Connections → candidate notes → semantic evaluation → meaningful relation?`

Only create a Breadcrumb relationship when the relationship is real and useful. Never convert a similarity score directly into a link.

## MOCs and indexes

Use `type: index` for navigation-oriented notes.

Prefer Dataview for indexes that can be derived reliably from metadata. Do not duplicate the full content of linked notes inside an index.

## Scope

Use `scope: project` for project-specific knowledge.
Use `scope: global` for knowledge intended to be reusable across projects.

Prefer links to shared global knowledge rather than copying the same knowledge into multiple locations.

## Document size

Split a document when it contains multiple independently useful concepts or distinct lifecycles. Do not split merely because it is long.

## Verification

After documentation changes:

1. Validate YAML frontmatter.
2. Confirm Properties use the intended values/types.
3. Check Breadcrumb relationships for semantic correctness.
4. Look for accidental duplicate or weak links.
5. Update a relevant index/MOC when needed.
6. Verify that unrelated files were not changed.

For full migration work, follow `references/migration.md`.

## Reporting

When reporting documentation work, distinguish what was:

- created,
- modified,
- split,
- linked,
- intentionally left unchanged,
- ambiguous.

Never claim the entire vault was normalized unless a complete migration was explicitly performed and verified.
