---
name: project-sync
description: >-
  Synchronizes technical decisions, implementation milestones, architectural changes, and project state from the active conversation into persistent LAEW project documentation, individual ADR files, history logs, and status files. Use whenever the user asks to sync project documentation, record decisions, update project status, or when an engineering milestone is reached.
---

# LAEW Project Sync Skill

## 1. Purpose & Identity
`project-sync` synchronizes ephemeral conversation context into the persistent long-term memory of LAEW (the repository's documentation).

- **Core Role**: Knowledge and state synchronization from active session to project memory.
- **Explicit Exclusions**:
  - It does NOT end, close, or pause the conversation session.
  - It does NOT invoke `/resume` or trigger session management commands.
  - It does NOT execute `git commit`, `git push`, or any destructive Git commands.
- **Repeatability & Idempotency**: Can be safely invoked multiple times within a single conversation turn or session. If no new significant changes or decisions occurred, it performs zero file modifications.

---

## 2. 5-Tier Project Memory Model

Documentation responsibilities are strictly separated to prevent duplication and noise:

| Tier | Component | Path | Responsibility |
| :--- | :--- | :--- | :--- |
| **1** | **Git** | `.git/` | Detailed file diffs, line modifications, commit history. |
| **2** | **Project History** | `docs/history/CHANGELOG.md` | Conceptual milestone completions, major structural shifts, evolutionary events (*Why* changes happened). |
| **3** | **ADRs** | `docs/decisions/ADR-NNN-<title>.md` | Individual architectural decision records (One ADR = One File). |
| **4** | **Project Status** | `docs/PROJECT_STATUS.md` | Current verified operational snapshot, implemented components, and immediate next objective. |
| **5** | **Architecture & Specs** | `docs/architecture/`, `docs/LAEW_CONTEXT.md`, `manifests/` | Living specifications, domain models, principles, system manifests, and tool contracts. |

---

## 3. Synchronization Procedure

When `project-sync` is invoked, execute the following steps:

### Step 1: Conversation & Ground Truth Audit
1. **Analyze Active Conversation**:
   - Identify verified completed milestones or major work items.
   - Identify significant architectural or engineering decisions.
   - Identify technical constraints, discarded alternatives, or discovered architectural risks.
2. **Inspect Actual Repository State**:
   - Run `git status` and `git diff` to verify ground truth.
   - Inspect files to verify physical completion (never record a milestone or component as completed based solely on conversational claims).

### Step 2: Differential Analysis & Idempotency Check
1. Read existing documentation files:
   - `docs/PROJECT_STATUS.md`
   - `docs/history/CHANGELOG.md` (if exists)
   - Existing ADRs in `docs/decisions/` and `docs/decisions/README.md`
   - `docs/architecture/PRINCIPLES.md`
   - `manifests/SYSTEM_MANIFEST.yaml`
2. **Idempotency Gate**:
   - If all decisions, milestones, and status items from the session are already accurately recorded, **STOP** and report: `Documentation is already in sync with current state. No changes needed.`

### Step 3: Targeted Documentation Updates

#### A. Architectural Decisions (Individual ADRs)
- **Rule: One ADR = One File** (`docs/decisions/ADR-NNN-<short-title>.md`).
- Scan `docs/decisions/` to determine the next sequence number (e.g., `ADR-010`, `ADR-011`...).
- Use the standard LAEW ADR structure:
  ```markdown
  # ADR-NNN — Title

  ## Status
  Proposed | Accepted | Deprecated | Superseded by [ADR-YYY](ADR-YYY-name.md)

  ## Context
  Problem statement, architectural motivation, and background.

  ## Decision
  Clear statement of the architectural decision made.

  ## Consequences
  - Positive trade-offs and architectural capabilities.
  - Negative trade-offs and operational overhead.
  ```
- **Superseding Decisions**: If a new decision replaces a prior ADR, do NOT overwrite the old ADR file. Mark the old ADR's status as `Superseded by [ADR-XXX](ADR-XXX-name.md)` and record `Supersedes [ADR-YYY](ADR-YYY-name.md)` in the new ADR.
- **Index Update**: When a new ADR is added, update the table in `docs/decisions/README.md`.
- Do NOT create ADRs for minor implementation details or temporary refactors.

#### B. Project History (`docs/history/CHANGELOG.md`)
- Update ONLY on verified, significant project milestones or major evolutionary events:
  - Milestone completion (e.g., Milestone 1 Declarative Foundation).
  - Introduction of a new subsystem or major architectural pattern.
  - Significant technology, framework, or model role transition.
  - Critical architectural risk resolution or fundamental pivot.
- Do NOT log conversational steps, minor bug fixes, or routine file edits.
- Structure entries with: Date, Milestone / Event Title, Context & Motivation, Key Achievements, Decisions & Consequences.

#### C. Project Status (`docs/PROJECT_STATUS.md`)
- Update current implementation stage.
- Update list of present and verified repository components.
- Update the immediate next objective.

#### D. Principles Protection (`docs/architecture/PRINCIPLES.md`)
- `PRINCIPLES.md` contains fundamental axioms (P1–Pn) and is strictly protected.
- `project-sync` MUST NOT automatically modify `docs/architecture/PRINCIPLES.md`.
- If a proposed change affects a core principle, flag it explicitly in the report for interactive user approval.

#### E. Living Specifications & Manifests
- Update `docs/LAEW_CONTEXT.md` or `manifests/SYSTEM_MANIFEST.yaml` ONLY if underlying domain models, principles, or configuration schemas changed.

### Step 4: Verification & Consistency Check
1. Verify that all recorded statements match verified repository files.
2. Verify that no contradictions exist across ADRs, Project Status, History, and Architecture specs.
3. Ensure no unapproved mutating Git commands were run.

### Step 5: Structured Sync Report
Output a concise summary:
- **ADRs Created / Updated**: Links to specific `ADR-NNN` files.
- **Project History Updated**: Summary of entry added to `docs/history/CHANGELOG.md` (or `None`).
- **Status & Specs Updated**: Specific status lines modified.
- **Principles Flagged (if any)**: Potential principle revisions requiring explicit user approval.
- **Uncertainties / Open Items**: Any ambiguous points flagged.
