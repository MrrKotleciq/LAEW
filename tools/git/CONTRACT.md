# LAEW Tool Contract — Git

## 1. Overview
- **Category**: `git`
- **Domain**: Git repository inspection, state tracking, revision history, and controlled versioning.
- **Specification Version**: 1.0

---

## 2. Security Enforcement (Below Model Layer — Principle P8)

1. **Inspection First (Principle P3)**:
   - Read-only inspection operations (`status`, `diff`, `log`) execute automatically to ascertain ground truth.
2. **Strict Block on Destructive Commands**:
   - The following operations are strictly FORBIDDEN and rejected at the wrapper level:
     - `reset --hard`
     - `push --force` / `push -f`
     - `clean -f` / `clean -fd`
     - `branch -D`
3. **User Confirmation for State Changes (Principle P7)**:
   - Any operation that creates commits, switches branches, or checks out revisions REQUIRES explicit user approval.

---

## 3. Operations

### 3.1. `git_status`
Retrieves working tree status, staged files, modified files, and untracked files.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**: None.
- **Outputs**:
  - `branch` (string): Current branch name.
  - `tracking` (string): Upstream tracking status.
  - `staged` (array of strings): Files staged for commit.
  - `unstaged` (array of strings): Modified unstaged files.
  - `untracked` (array of strings): Untracked files.
  - `is_clean` (boolean): True if working directory is clean.

---

### 3.2. `git_diff`
Retrieves working tree or commit differences.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `file_path` (string, optional): Specific file path to diff.
  - `staged` (boolean, optional, default: false): Diff against index (`--cached`).
  - `revision` (string, optional): Specific commit or branch ref to diff against.
- **Outputs**:
  - `diff` (string): Standard unified diff output.
  - `files_changed` (integer): Number of modified files.

---

### 3.3. `git_log`
Retrieves commit history and metadata.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `max_count` (integer, optional, default: 10): Maximum commits to return.
  - `file_path` (string, optional): Filter history by file path.
- **Outputs**:
  - `commits` (array of objects):
    - `hash` (string): Full/abbreviated commit hash.
    - `author` (string): Author name and email.
    - `date` (ISO timestamp).
    - `message` (string): Commit message.

---

### 3.4. `git_commit`
Records changes to the repository with a descriptive message.

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `message` (string, required): Commit message adhering to project conventions.
  - `files` (array of strings, optional): Specific files to stage and commit.
- **Outputs**:
  - `commit_hash` (string): New commit hash.
  - `status` (string: `success`).
- **Error Codes**:
  - `ERR_NOTHING_TO_COMMIT`: Working tree is clean.
  - `ERR_UNAUTHORIZED`: User rejected commit operation.

---

### 3.5. `git_checkout` / `git_branch`
Creates or switches branches.

- **Type**: `Mutating`
- **User Approval Required**: `YES`
- **Inputs**:
  - `branch_name` (string, required): Target branch name.
  - `create_new` (boolean, optional, default: false): Flag to create new branch (`-b`).
- **Outputs**:
  - `current_branch` (string): Active branch after operation.
- **Error Codes**:
  - `ERR_DIRTY_WORKING_TREE`: Local changes would be overwritten.
  - `ERR_UNAUTHORIZED`: User rejected branch switch.
