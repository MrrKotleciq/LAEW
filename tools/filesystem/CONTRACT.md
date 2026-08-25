# LAEW Tool Contract — Filesystem

## 1. Overview
- **Category**: `filesystem`
- **Domain**: Workspace file inspection, search, navigation, logical root resolution, and modification.
- **Specification Version**: 1.1 (Multi-Root Aliasing & Boundary Security)

---

## 2. Security Enforcement (Below Model Layer — Principles P8 / ADR-010)

All filesystem tool operations MUST be wrapped in a deterministic security boundary enforced programmatically before system execution:

1. **Logical Root Resolution & Path Aliasing (ADR-010)**:
   - Tool operations support and resolve abstract path aliases defined in `SYSTEM_MANIFEST.yaml`:
     - `@project/...` resolves strictly within `PROJECT_ROOT` (`workspace.logical_roots.project`).
     - `@knowledge/...` resolves strictly within `GLOBAL_KNOWLEDGE_ROOT` (`workspace.logical_roots.global_knowledge`).
     - `@projects/...` resolves within `PROJECTS_ROOT` (`workspace.logical_roots.projects_parent`).
   - Unprefixed relative paths default to `@project/...`.
2. **Path Traversal Prevention & Sandbox Confinement**:
   - Relative directory traversal (`../`) escaping the boundary of the target logical root is strictly blocked and rejected with `ERR_PATH_OUT_OF_BOUNDS`.
3. **Deny-by-Default Policy**:
   - Access to any filesystem path outside the explicitly declared logical roots (e.g., `~/.ssh/`, `~/.config/`, root system files) is strictly **DENIED** (`ERR_PATH_DENIED`).
4. **Access Policies per Logical Root**:
   - `@project`: Read-only allowed; mutating operations (`write_file`, `replace_file_content`, `delete_file`) REQUIRE explicit user confirmation.
   - `@knowledge`: Strictly **Read-Only** by default to protect shared cross-project knowledge.
   - `@projects`: Controlled inspection (read-only listing/viewing of neighboring project files).
5. **Restricted Paths & Ignored Patterns**:
   - Direct access to `.git/`, `secrets/`, and matching ignored patterns (`**/.env*`, `**/*.gguf`, `**/*.safetensors`) is blocked without explicit authorization.

---

## 3. Operations

### 3.1. `view_file`
Reads the textual content of a file within an authorized logical root.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `file_path` (string, required): Aliased or relative path (e.g., `@project/docs/README.md`, `@knowledge/AI/RAG.md`).
  - `start_line` (integer, optional, default: 1): 1-indexed starting line number.
  - `end_line` (integer, optional): 1-indexed ending line number (inclusive).
- **Outputs**:
  - `content` (string): Text content of the requested line range.
  - `total_lines` (integer): Total number of lines in the file.
  - `size_bytes` (integer): File size in bytes.
- **Error Codes**:
  - `ERR_FILE_NOT_FOUND`: Target file does not exist.
  - `ERR_PATH_DENIED`: Path is outside authorized logical roots or in restricted paths.
  - `ERR_PATH_OUT_OF_BOUNDS`: Attempted directory traversal escaping the root boundary.
  - `ERR_BINARY_FILE`: File is binary; text viewing is unsupported without specialized parser.

---

### 3.2. `list_dir`
Lists directories and files within an authorized logical root.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `directory_path` (string, required, default: `@project`): Directory path to inspect (e.g., `@project`, `@knowledge`).
  - `depth` (integer, optional, default: 1): Recursion depth.
- **Outputs**:
  - `entries` (array of objects):
    - `name` (string): Entry name.
    - `type` (string: `file` | `directory`).
    - `size_bytes` (integer).
    - `modified_at` (ISO timestamp).
- **Error Codes**:
  - `ERR_DIR_NOT_FOUND`: Specified directory does not exist.
  - `ERR_PATH_DENIED`: Path is restricted or unmapped.

---

### 3.3. `find_by_name`
Searches for files and subdirectories by glob pattern within a specified logical root.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `pattern` (string, required): Glob pattern (e.g., `*.md`, `**/*.py`).
  - `search_directory` (string, optional, default: `@project`): Base directory for search.
  - `type` (string, optional: `file` | `directory` | `any`).
- **Outputs**:
  - `matches` (array of strings): List of matching paths.
  - `match_count` (integer): Total matches found.

---

### 3.4. `grep_search`
Performs literal or regex pattern search across text files within an authorized logical root.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `query` (string, required): Search string or regex.
  - `search_path` (string, optional, default: `@project`): Directory or file to search.
  - `is_regex` (boolean, optional, default: false): Treat query as regex.
  - `case_insensitive` (boolean, optional, default: true): Case insensitive search.
- **Outputs**:
  - `results` (array of objects):
    - `file` (string): Aliased file path.
    - `line_number` (integer): Line index.
    - `line_content` (string): Content of the matching line.

---

### 3.5. `write_file`
Creates or overwrites a file in the workspace (restricted to `@project`).

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `file_path` (string, required): Destination path within `@project`.
  - `content` (string, required): Content to write.
  - `overwrite` (boolean, optional, default: false): Overwrite permission flag.
- **Outputs**:
  - `status` (string: `created` | `overwritten`).
  - `bytes_written` (integer).
- **Error Codes**:
  - `ERR_MUTATION_FORBIDDEN`: Attempted write outside `@project` (e.g., writing to `@knowledge` is forbidden).
  - `ERR_FILE_EXISTS`: File already exists and `overwrite` is false.
  - `ERR_UNAUTHORIZED`: User rejected modification.

---

### 3.6. `replace_file_content`
Performs targeted text replacement in an existing file within `@project`.

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `file_path` (string, required): File to modify within `@project`.
  - `start_line` (integer, required): Starting search line.
  - `end_line` (integer, required): Ending search line.
  - `target_content` (string, required): Exact text block to replace.
  - `replacement_content` (string, required): Replacement text block.
- **Outputs**:
  - `status` (string: `success`).
  - `diff` (string): Standard unified diff.
- **Error Codes**:
  - `ERR_TARGET_NOT_FOUND`: Target content does not match existing file lines.
  - `ERR_UNAUTHORIZED`: User rejected modification.
