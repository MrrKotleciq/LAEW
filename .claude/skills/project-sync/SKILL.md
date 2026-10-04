---
name: project-sync
type: skill
title: Project Sync
scope: synchronize conversation decisions into persistent LAEW project documentation
read_when:
  - user asks to sync, record, or update project documentation
  - an engineering milestone is reached
  - a significant architectural decision was made
---

# LAEW Project Sync

## Purpose

`project-sync` moves ephemeral conversation context into LAEW's persistent
long-term memory (the repository's documentation). It is a documentation task,
not a session task.

- **Does NOT** end, close, or pause the conversation session.
- **Does NOT** invoke session-management commands (`/resume`, `/exit`, etc.).
- **Does NOT** execute `git commit`, `git push`, or any destructive Git commands.
- **Is idempotent**: if the session's decisions and milestones are already
  accurately recorded, make **zero** file modifications and report that.

## Memory Model

Documentation responsibilities are separated to prevent duplication:

| Layer | Path | Responsibility |
| :--- | :--- | :--- |
| **Git** | `.git/` | File diffs and commit history. Never the sync target. |
| **History** | `docs/history/*.md` + `docs/history/README.md` | Verified milestone completions and evolutionary events (*why* things changed). |
| **ADRs** | `docs/decisions/ADR-NNN-<title>.md` | Individual architectural decisions (one decision = one file). |
| **Status** | `docs/PROJECT_STATUS.md` | Current verified snapshot: implemented components and next objective. |
| **Roadmap** | `docs/roadmap/` | Planned milestones (M16–M21) and in-progress work. |
| **Architecture** | `docs/architecture/`, `docs/LAEW_CONTEXT.md`, `manifests/` | Living specs, principles, manifests, tool contracts. |

## Procedure

### Step 1: Ground-Truth Audit
Never record a milestone or component as done from conversation alone.
1. Inspect the actual repository: `git status`, `git diff`, and the files
   themselves.
2. Read the relevant existing docs before writing (`PROJECT_STATUS.md`,
   `docs/history/README.md`, `docs/decisions/README.md`, `PRINCIPLES.md`).

### Step 2: Idempotency Gate
If every decision, milestone, and status item from the session is already
accurately recorded, **stop** and report: `Documentation is already in sync
with current state. No changes needed.`

### Step 3: Targeted Updates

#### A. Architectural Decisions (ADRs)
- **One ADR = One File** (`docs/decisions/ADR-NNN-<short-title>.md`).
- Scan `docs/decisions/` for the next sequence number.
- Use the LAEW ADR frontmatter (see `yaml-metadata.md`): `type: adr`, `id`,
  `title`, `status`, `purpose`, `scope`, `read_when`, `related`.
- **Superseding**: do not overwrite the old ADR. Set its `status` to
  `Superseded` and record `related`/`Supersedes` in the new one.
- Update `docs/decisions/README.md` when a new ADR is added.
- Do NOT create ADRs for minor details or temporary refactors.

#### B. Project History (`docs/history/*.md`)
- Update **only** for verified, significant milestones or evolutionary events:
  milestone completion, new subsystems, technology/model-role transitions,
  critical risk resolution.
- Do NOT log conversational steps, minor fixes, or routine edits.
- Match the existing format: a `## [YYYY-MM-DD] Title` header followed by
  `- **Context & Motivation:**`, `- **Key Achievements:**`, and
  `- **Decisions & Consequences:**` bullet lists, each ending with a `---`.
- History files intentionally omit YAML frontmatter (per project-structure rules).
- Update the `docs/history/README.md` index with a new row.

#### C. Project Status (`docs/PROJECT_STATUS.md`)
- Update the implementation stage and the "current focus" statement.
- Update the list of present, verified components.
- Update the next objective.

#### D. Roadmap (`docs/roadmap/`)
- Record in-progress milestones and their objectives here; do not duplicate
  them as if completed in Status or History.
- Use the milestone file naming and frontmatter conventions (`MXX`, `yaml-metadata.md`).

#### E. Principles Protection (`docs/architecture/PRINCIPLES.md`)
- `PRINCIPLES.md` holds fundamental axioms (P1–Pn) and is protected.
- Do NOT auto-modify it. If a proposed change affects a principle, flag it in
  the report for explicit user approval.

#### F. Living Specs & Manifests
- Update `docs/LAEW_CONTEXT.md` or `manifests/SYSTEM_MANIFEST.yaml` only when
  domain models, principles, or configuration schemas genuinely change.

### Step 4: Verification
1. Confirm every recorded statement matches verified repository files.
2. Confirm no contradictions across Status, History, ADRs, and Architecture.
3. Confirm no unapproved mutating Git commands were run.

### Step 5: Sync Report
Report concisely:
- **ADRs Created / Updated**: links to `ADR-NNN` files.
- **History Updated**: entry added to `docs/history/` (or `None`).
- **Status / Roadmap / Specs Updated**: specific lines or files.
- **Principles Flagged (if any)**: proposed revisions awaiting approval.
- **Uncertainties / Open Items**: ambiguous points.
