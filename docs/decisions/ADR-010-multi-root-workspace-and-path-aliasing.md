# ADR-010 — Multi-Root Workspace Boundaries and Logical Path Aliasing

## Status
Accepted

## Context
LAEW is one individual project residing within a broader user workspace alongside other repositories and a global knowledge base:
```text
~/Projects/
├── projects/
│   ├── LAEW/
│   ├── project-2/
│   └── project-3/
└── knowledge/
```
LAEW is not the root container of the user's workspace. Agents operating inside LAEW require controlled access to project files, neighboring projects, and the global knowledge base.

Relying on arbitrary relative path navigation (`../`, `../../`) is fragile, security-prone, and binds tool logic to specific folder nesting depths. Granting unrestricted filesystem access to `$HOME` violates Principle P8 (Security below the model layer).

## Decision
1. Define three explicit logical roots:
   - `PROJECT_ROOT`: The current project repository directory.
   - `PROJECTS_ROOT`: The parent directory containing independent project repositories.
   - `GLOBAL_KNOWLEDGE_ROOT`: The global Obsidian knowledge vault.
2. Introduce abstract logical path aliases:
   - `@project`: Maps to `PROJECT_ROOT` (e.g., `@project/docs/PROJECT_STATUS.md`).
   - `@projects`: Maps to `PROJECTS_ROOT` (e.g., `@projects/project-2/...`).
   - `@knowledge`: Maps to `GLOBAL_KNOWLEDGE_ROOT` (e.g., `@knowledge/AI/RAG.md`).
3. Enforce access control programmatically in the filesystem tool layer:
   - Access to `@project` is standard read/write (with approval for mutations).
   - Access to `@knowledge` is strictly read-only by default.
   - Access to `@projects` is controlled inspection only.
   - All unmapped paths outside these roots (such as `~/.ssh/`, `~/.config/`, system directories) are strictly **DENIED BY DEFAULT**.

## Consequences
### Positive
- Eliminates fragile `../` path navigation and decouples agents from filesystem nesting depth.
- Restricts agent reach strictly to designated engineering directories, protecting user privacy and system integrity.
### Negative
- Requires filesystem tool wrappers to parse, resolve, and validate path aliases before invoking system calls.
