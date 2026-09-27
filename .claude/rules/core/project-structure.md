---
type: rule
title: Project Structure
scope: source code, documentation, and directory organization
read_when:
  - understanding the project layout
---

# LAEW Project Structure 

## Project 

LAEW is a local-first AI Engineering Workspace. 

### Source Code 

- `./laew/` — application source code. 
- `./tests/` — automated tests. 
- `./tools/` — development and utility tooling. 
- `./manifests/` — system and configuration manifests.

### Documentation 

- `./docs/README.md` — documentation index and navigation entry point. 
- `./docs/LAEW_CONTEXT.md` — concise project context and scope. 
- `./docs/PROJECT_STATUS.md` — current implementation status. 
- `./docs/architecture/` — current architectural principles and intent. 
- `./docs/decisions/` — Architecture Decision Records (ADRs). 
- `./docs/roadmap/` — roadmap, milestones, and planned work. 
- `./docs/history/` — chronological development history. 
- `./docs/performance/` — performance measurements and baselines. 
- `./docs/security/` — security reviews and findings. 
- `./docs/source/` — source/reference material used during project development. 

## Documentation Navigation 

Do not read the entire `docs/` directory by default. 

Before reading a document: 

1. Start with `./docs/README.md` when the relevant location is unknown. 
2. Use filenames, directory structure, and document metadata to identify relevant documents. 
3. Read only documents relevant to the current task. 
4. Prefer targeted search before opening large documents. 
5. Do not read historical material unless historical context is needed. 

## Documentation Semantics 

- `docs/decisions/` records architectural decisions. 
- `docs/architecture/` describes current architectural intent. 
- `docs/PROJECT_STATUS.md` summarizes the current implemented state. 
- `docs/roadmap/` describes planned work, not implemented functionality. 
- `docs/history/` records what happened in the past. 
- `docs/source/` contains reference material and is not itself project policy. 

When documentation conflicts with implemented behavior, inspect the current code and tests before deciding what is true. 

When changing architecture, interfaces, security boundaries, or other ADR-governed behavior, identify and read the relevant ADR before implementation. 

## Document Metadata 

Project documentation uses YAML frontmatter to describe documents. 

### YAML Frontmatter Schema

All documents use this unified schema:

```yaml
---
type: <type>
title: Title
scope: Brief description of the document's scope
read_when:
  - Condition 1
  - Condition 2
---
```

**Type values:**
- `adr` — Architecture Decision Record (`docs/decisions/`)
- `index` — Index/navigation README (`docs/architecture/`, `docs/performance/`, `docs/security/`, `docs/source/`, `docs/roadmap/`)
- `roadmap` — Milestone document (`docs/roadmap/MXX-*.md`)
- `status` — Current project status (`docs/PROJECT_STATUS.md`)
- `history` — Historical record (`docs/history/`, `docs/REORGANIZATION_REPORT.md`)
- `architecture` — Architectural principles/specs (`docs/architecture/`)
- `docs` — General documentation (`docs/INSTALL.md`, `docs/REORGANIZATION_REPORT.md`)
- `report` — Scan or audit reports (`REPOSITORY_SCAN_RESULTS.md`)
- `prompt` — Agent prompt/instruction file (`prompts/`)
- `rule` — Project rule (`.claude/rules/core/`)
- `skill` — Agent skill (` .claude/skills/`)
- `rule:python` — Python-specific rule (`.claude/rules/python/`)

**Type-specific fields:**

- **ADRs** (`type: adr`): `id`, `title`, `status`, `date`, `purpose`, `scope`, `read_when`, `related`
- **Roadmap milestones** (`type: roadmap`): `id`, `title`, `status` (completed/in-progress/backlog), `purpose`, `read_when`
- **Index READMEs** (`type: index`): `title`, `scope`, `read_when`
- **Python rules** (`.claude/rules/python/`): `paths` — list of file patterns the rule applies to

**Placeholders:** `docs/history/*.md` and `docs/source/*.md` intentionally omit YAML frontmatter because they are chronological records and external reference material respectively.

### Applying YAML Frontmatter

When creating or substantially modifying a documentation file:

1. Check if the file already has YAML frontmatter.
2. If not, and the file type warrants it, add the frontmatter at the top of the file.
3. Use the appropriate `type` and fields based on the document category.
4. For ADRs, ensure `status` is one of: `Proposed`, `Accepted`, `Deprecated`, `Superseded`.
5. For roadmap milestones, use `status: completed`, `status: in-progress`, or `status: backlog`.
6. For Python rules, include `paths` to indicate which files the rule applies to.

### Existing Conventions

The following file types intentionally do NOT use YAML frontmatter:

- `docs/history/*.md` — chronological records
- `docs/source/*.md` — external reference material
- `tools/*/*.md` — tool contracts (use their own format)
- `tests/*/*.md` — test specifications (use their own format)

## See Also

- [YAML Frontmatter Guide](./yaml-metadata.md) — detailed schema reference