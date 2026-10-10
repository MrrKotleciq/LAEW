# LAEW Breadcrumb Relationships

## Edge fields

Use these edge fields:

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

Breadcrumbs field groups currently used by LAEW include:

```text
ups
├── up
├── implements
├── depends-on
├── defined-by
├── derived-from
└── supersedes

downs
└── down

sames
├── same
└── related

nexts
└── next

prevs
└── prev
```

Note: `same` is the edge field; `sames` is the field group.

## Semantics

### `up`

Structural parent or higher-level document.

### `down`

Structural child. Normally use `up` on the child and let Breadcrumbs provide the inverse when configured.

### `same`

Sibling-level relationship when Breadcrumbs' sibling semantics are genuinely useful.

Do not use it simply because two notes share a topic.

### `next` / `prev`

Use only for genuine sequences.

### `implements`

The current document or implementation directly realizes another concept, requirement, specification, or design.

### `depends-on`

The current document materially depends on another document for understanding, correctness, or operation.

### `defined-by`

Another document defines the rules, contract, or decision governing the current document.

### `derived-from`

The current document is materially derived from another source or document.

### `related`

Meaningful conceptual relationship that does not fit a more specific relationship.

Use sparingly.

### `supersedes`

The current document intentionally replaces an older document.

Do not use when both documents remain valid.

## Link-quality rule

Prefer a small number of strong relations over many weak relations.

Before adding a relation, ask:

> Would this relationship still be useful to an engineer navigating the vault six months from now?

If not, omit it.
