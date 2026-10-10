# LAEW Documentation Migration Procedure

Use this procedure only when the user explicitly requests a migration or normalization of an existing vault/directory.

## 1. Audit

Inspect the requested scope before changing anything.

Identify:

- files missing frontmatter,
- inconsistent metadata,
- duplicate or overlapping documents,
- obsolete documents,
- existing useful relationships,
- indexes/MOCs that may require updates.

Do not infer uncertain semantics from filenames alone.

## 2. Plan

Classify each candidate document.

For each proposed change, record:

- current file,
- proposed type/scope/status,
- metadata to add or change,
- proposed relations,
- split required or not,
- ambiguity requiring human review.

Do not silently resolve ambiguous cases.

## 3. Execute in batches

Apply changes in controlled groups rather than rewriting the entire vault in one operation.

Preserve user-authored content.

Do not delete source information unless the user explicitly authorizes it or the migration plan clearly requires it.

When splitting documents:

1. identify independent concepts,
2. create the new notes,
3. preserve metadata and important content,
4. create meaningful Breadcrumb relationships,
5. update the parent/MOC when useful,
6. verify links.

## 4. Validate

After each batch:

- validate YAML,
- check Properties values,
- check Breadcrumb relations,
- check for duplicate content,
- check MOCs/indexes,
- inspect the final diff.

## 5. Report

Report:

- files changed,
- files created,
- files split,
- files intentionally left untouched,
- unresolved ambiguities,
- any remaining cleanup.

Never claim a complete migration unless the requested scope was actually audited and verified.
