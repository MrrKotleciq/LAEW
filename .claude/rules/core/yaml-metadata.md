---
type: rule
title: YAML Metadata
scope: YAML frontmatter conventions for project documentation
read_when:
  - creating or modifying a documentation file
  - adding YAML frontmatter to a new file
---

# YAML Metadata Convention

## Overview

LAEW uses YAML frontmatter to attach metadata to documentation files. This enables:

- **Document type classification** — distinguishing ADRs, index files, milestones, etc.
- **Searchability** — finding documents by type, scope, or purpose.
- **Tooling support** — automated indexes, navigation, and document discovery.
- **Consistency** — a single, well-defined schema across all documentation.

## Schema

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

### Type Values

| Type | Used For | Example |
|------|-----------|---------|
| `adr` | Architecture Decision Records | `docs/decisions/ADR-001-*.md` |
| `index` | Index/navigation READMEs | `docs/architecture/README.md` |
| `roadmap` | Milestone documents | `docs/roadmap/MXX-*.md` |
| `status` | Project status | `docs/PROJECT_STATUS.md` |
| `history` | Historical records | `docs/history/*.md`, `docs/REORGANIZATION_REPORT.md` |
| `architecture` | Architectural principles/specs | `docs/architecture/*.md` |
| `docs` | General documentation | `docs/INSTALL.md` |
| `report` | Scan/audit reports | `REPOSITORY_SCAN_RESULTS.md` |
| `prompt` | Agent prompts | `prompts/*.md` |
| `rule` | Project rules | `.claude/rules/core/*.md` |
| `rule:python` | Python-specific rules | `.claude/rules/python/*.md` |
| `skill` | Agent skills | `.claude/skills/*.md` |

### Type-Specific Fields

#### ADRs (`type: adr`)

```yaml
type: adr
id: ADR-001
title: Model Abstraction and Roles
status: Accepted
date: 2026-08-25
purpose: Define LAEW's abstract model roles...
scope: LLM provider integration, model roles, multi-model routing
read_when:
  - designing or modifying LLM provider integration
  - adding a new provider or model role
  - implementing multi-model routing or fallback (Milestone 15)
related:
  - ADR-004
  - ADR-019
```

#### Roadmap Milestones (`type: roadmap`)

```yaml
type: roadmap
id: M01
title: Declarative Foundation
status: completed
purpose: Establish the declarative baseline...
read_when:
  - understanding the baseline architecture
  - reading the manifest, tool contracts, or prompt templates
```

#### Index READMEs (`type: index`)

```yaml
type: index
title: Architecture
scope: current architectural intent and principles
read_when:
  - understanding the current architectural direction
  - evaluating new architectural changes
  - reviewing design principles
```

#### Python Rules (`type: rule:python`)

```yaml
type: rule:python
paths:
  - "**/*.py"
  - "**/*.pyi"
---

# Python Security
...
```

## Workflow

1. **Identify the document type** — What kind of document is this? (ADR, milestone, index, etc.)
2. **Choose the type value** — Refer to the table above.
3. **Fill in the fields** — Use the schema appropriate for that type.
4. **Verify** — Ensure the YAML is valid and the fields match the type's schema.

## Examples

### ADR

```yaml
---
type: adr
id: ADR-019
title: Provider Registry and Factory
status: Accepted
date: 2026-09-15
purpose: Dispatch model roles across providers through a registry and factory...
scope: provider registry, role-based routing, fallback
read_when:
  - adding or changing a model provider
  - Milestone 15 (Multi-Model Routing & Provider Fallback)
  - resolving a model role to a provider
related:
  - ADR-001
  - ADR-015
  - ADR-016
---
```

### Prompt

```yaml
---
type: prompt
title: Core Instructions
scope: identity, principles, knowledge priority, tool selection
read_when:
  - understanding the agent's core behavior
---

# LAEW Core Instructions
...
```

### Rule

```yaml
---
type: rule
title: Performance
scope: evidence-based optimization, avoid premature optimization
read_when:
  - optimizing code
---

# Performance
...
```

## Validation

Before committing a file with YAML frontmatter:

1. Ensure the `type` field is one of the valid values above.
2. Ensure `title` is a concise, descriptive title.
3. Ensure `scope` briefly describes what the document covers.
4. Ensure `read_when` contains conditions that help decide when to read the document.
5. For ADRs, ensure `status` is one of: `Proposed`, `Accepted`, `Deprecated`, `Superseded`.
6. For ADRs, ensure `id` follows the `ADR-NNN` format.
7. For roadmap milestones, ensure `id` follows the `MXX` format and `status` is one of: `completed`, `in-progress`, `backlog`.

## Verification

After making changes:

```bash
# Check git status
git status

# Verify YAML validity in modified files
python -c "import yaml; yaml.safe_load(open('file.md').read())"
```

## See Also

- [Project Structure](./project-structure.md) — overall project layout
- [Project Sync Skill](../../skills/project-sync/SKILL.md) — documentation synchronization