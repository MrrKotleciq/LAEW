# LAEW Tool Contract — Filesystem

## 1. Overview
- **Category**: `filesystem`
- **Domain**: Workspace file inspection, search, navigation, and modification.
- **Specification Version**: 1.0

---

## 2. Security Enforcement (Below Model Layer — Principle P8)

All filesystem tool operations MUST be wrapped in an enforcement boundary that validates requests before execution:

1. **Path Boundary Validation (Sandbox)**:
   - All accessed paths MUST resolve within `workspace.root` (`.`).
   - Absolute paths targeting locations outside the workspace root and relative paths using directory traversal (`../`) to escape the workspace are strictly prohibited.
2. **Restricted Paths**:
   - Direct read/write access to paths listed under `workspace.restricted_paths` (`.git`, `secrets`) is blocked.
3. **Ignored Patterns**:
   - Files matching `workspace.ignored_patterns` (e.g., `**/.env*`, `**/__pycache__/**`, `**/*.gguf`, `**/*.safetensors`) MUST NOT be indexed or returned in broad queries without explicit approval.
4. **Separation of Read vs. Write (Principle P7)**:
   - Read operations execute without explicit user approval.
   - Mutating operations (`write_file`, `replace_file_content`, `delete_file`) REQUIRE explicit user confirmation.

---

## 3. Operations

### 3.1. `view_file`
Reads the textual content of a file within the workspace.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `file_path` (string, required): Relative path to the target file.
  - `start_line` (integer, optional, default: 1): 1-indexed starting line number.
  - `end_line` (integer, optional): 1-indexed ending line number (inclusive).
- **Outputs**:
  - `content` (string): Text content of the requested line range.
  - `total_lines` (integer): Total number of lines in the file.
  - `size_bytes` (integer): File size in bytes.
- **Error Codes**:
  - `ERR_FILE_NOT_FOUND`: Target file does not exist.
  - `ERR_PATH_RESTRICTED`: Path is within a restricted directory.
  - `ERR_BINARY_FILE`: File is binary; text viewing is unsupported without specialized parser.

---

### 3.2. `list_dir`
Lists directories and files within a given workspace directory.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `directory_path` (string, required, default: `.`): Directory path to inspect.
  - `depth` (integer, optional, default: 1): Recursion depth.
- **Outputs**:
  - `entries` (array of objects):
    - `name` (string): Entry name.
    - `type` (string: `file` | `directory`).
    - `size_bytes` (integer).
    - `modified_at` (ISO timestamp).
- **Error Codes**:
  - `ERR_DIR_NOT_FOUND`: Specified directory does not exist.
  - `ERR_PATH_RESTRICTED`: Path is restricted.

---

### 3.3. `find_by_name`
Searches for files and subdirectories by glob pattern.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `pattern` (string, required): Glob pattern (e.g., `*.md`, `**/*.py`).
  - `search_directory` (string, optional, default: `.`): Base directory for search.
  - `type` (string, optional: `file` | `directory` | `any`).
- **Outputs**:
  - `matches` (array of strings): List of relative matching paths.
  - `match_count` (integer): Total matches found.

---

### 3.4. `grep_search`
Performs literal or regex pattern search across text files.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `query` (string, required): Search string or regex.
  - `search_path` (string, optional, default: `.`): Directory or file to search.
  - `is_regex` (boolean, optional, default: false): Treat query as regex.
  - `case_insensitive` (boolean, optional, default: true): Case insensitive search.
- **Outputs**:
  - `results` (array of objects):
    - `file` (string): Relative file path.
    - `line_number` (integer): Line index.
    - `line_content` (string): Content of the matching line.

---

### 3.5. `write_file`
Creates or overwrites a file in the workspace.

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `file_path` (string, required): Destination relative file path.
  - `content` (string, required): Content to write.
  - `overwrite` (boolean, optional, default: false): Overwrite permission flag.
- **Outputs**:
  - `status` (string: `created` | `overwritten`).
  - `bytes_written` (integer).
- **Error Codes**:
  - `ERR_FILE_EXISTS`: File already exists and `overwrite` is false.
  - `ERR_UNAUTHORIZED`: User rejected modification.

---

### 3.6. `replace_file_content`
Performs targeted, deterministic text replacement in an existing file.

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `file_path` (string, required): File to modify.
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
