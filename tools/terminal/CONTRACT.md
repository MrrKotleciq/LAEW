# LAEW Tool Contract — Terminal

## 1. Overview
- **Category**: `terminal`
- **Domain**: Shell command execution, build automation, test runners, and script evaluation.
- **Specification Version**: 1.0

---

## 2. Security Enforcement (Below Model Layer — Principle P8)

1. **Strict Pattern & Command Blacklist**:
   - The execution engine MUST block and reject commands containing:
     - Privilege escalation: `sudo`, `su`, `doas`
     - Destructive file operations: `rm -rf`, `mkfs`, `dd if=`
     - System permission modifications: `chmod`, `chown`
     - Device redirection: `> /dev/*`
     - Network tunneling / reverse shells: `nc -e`, `/dev/tcp/*`
2. **Execution Working Directory**:
   - Commands MUST execute with `cwd` confined within `workspace.root`.
3. **Safe Command Allowlist (Auto-approved)**:
   - Read-only inspection commands execute without interactive approval:
     - `ls`, `cat`, `head`, `tail`, `grep`, `find`, `git status`, `git diff`, `git log`
4. **Approval for Active Execution (Principle P7)**:
   - Compilers, build tools, package managers, and test suites REQUIRE explicit user confirmation prior to execution.

---

## 3. Operations

### 3.1. `run_command`
Executes a terminal command within the workspace environment.

- **Type**: `Conditional` (`Read-Only` for allowlisted inspect commands; `Mutating/Active` for general commands).
- **User Approval Required**:
  - `No` for read-only allowlist.
  - `YES` for builds, scripts, tests, package managers, and external binaries.
- **Inputs**:
  - `command` (string, required): Exact command string to execute.
  - `cwd` (string, optional, default: `.`): Working directory relative to workspace root.
  - `timeout_ms` (integer, optional, default: 30000): Maximum execution time in milliseconds.
- **Outputs**:
  - `exit_code` (integer): Process exit code (0 for success).
  - `stdout` (string): Standard output stream.
  - `stderr` (string): Standard error stream.
  - `duration_ms` (integer): Execution duration in milliseconds.
- **Error Codes**:
  - `ERR_COMMAND_BLOCKED`: Command violates security blacklist.
  - `ERR_UNAUTHORIZED`: User rejected command execution.
  - `ERR_TIMEOUT`: Process exceeded maximum execution time.
  - `ERR_NON_ZERO_EXIT`: Process exited with non-zero code.
