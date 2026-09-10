"""Git operations tool wrapper (tools/git/CONTRACT.md)."""

import subprocess
from pathlib import Path
from typing import List, Optional

from laew.security import PathResolver, PathResolverError
from laew.tools.base import ErrorCode, Tool, ToolResult


class GitTool(Tool):
    """
    Git version control tool wrapper with security compliance (P8 / ADR-006).

    Implements tools/git/CONTRACT.md.

    Operations:
        - git_status: Read staged, unstaged, untracked files
        - git_diff: Diff working tree or commits
        - git_log: Inspect commit history
        - git_commit: Commit changes (requires approval)
        - git_checkout: Switch branches or restore files (requires approval)
        - git_branch: Create branch (requires approval)
    """

    description = "Inspect and manage a Git repository (status, diff, log, commit)"

    # Strictly forbidden Git commands
    FORBIDDEN_COMMANDS = {
        "reset --hard",
        "push --force", "push -f",
        "clean -f", "clean -fd",
        "branch -D"
    }

    def __init__(self, repo_root: Optional[Path | str] = None):
        """
        Initialize git tool.

        Args:
            repo_root: Root path of git repository (defaults to cwd)
        """
        super().__init__(requires_approval=False)
        if repo_root is None:
            self.repo_root = Path.cwd().resolve()
        else:
            self.repo_root = Path(repo_root).resolve()

        self._git_approved = False
        # Path resolver gates which files may be staged (P8 / ADR-010).
        self.resolver = PathResolver(project_root=self.repo_root)

    def approve(self):
        """Approve git state change."""
        self._git_approved = True

    def is_approved(self) -> bool:
        """Check if approved."""
        return self._git_approved

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate operation input."""
        valid_ops = {"git_status", "git_diff", "git_log", "git_commit", "git_checkout", "git_branch"}
        if operation not in valid_ops:
            return False, f"Unknown operation: {operation}"
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """Execute git operation."""
        if operation == "git_status":
            return self._git_status()
        elif operation == "git_diff":
            return self._git_diff(**kwargs)
        elif operation == "git_log":
            return self._git_log(**kwargs)
        elif operation == "git_commit":
            return self._git_commit(**kwargs)
        elif operation == "git_checkout":
            return self._git_checkout(**kwargs)
        elif operation == "git_branch":
            return self._git_branch(**kwargs)
        return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, f"Unknown operation: {operation}")

    def _run_git(self, args: List[str]) -> subprocess.CompletedProcess:
        """Run raw git process in repo_root with English locale."""
        # Enforce check for forbidden subcommands
        cmd_str = " ".join(args)
        for forbidden in self.FORBIDDEN_COMMANDS:
            if forbidden in cmd_str:
                raise PermissionError(f"Forbidden git subcommand: {forbidden}")

        import os
        env = os.environ.copy()
        env["LC_ALL"] = "C"
        env["LANG"] = "C"

        return subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env
        )

    # Public wrappers
    def git_status(self) -> ToolResult:
        return self.call("git_status")

    def git_diff(self, file_path: Optional[str] = None, staged: bool = False, revision: Optional[str] = None) -> ToolResult:
        return self.call("git_diff", file_path=file_path, staged=staged, revision=revision)

    def git_log(self, max_count: int = 10, file_path: Optional[str] = None) -> ToolResult:
        return self.call("git_log", max_count=max_count, file_path=file_path)

    def git_commit(self, message: str, files: Optional[List[str]] = None) -> ToolResult:
        return self.call("git_commit", message=message, files=files)

    def git_checkout(self, branch_name: str, create_new: bool = False) -> ToolResult:
        return self.call("git_checkout", branch_name=branch_name, create_new=create_new)

    def git_branch(self, branch_name: str, delete: bool = False) -> ToolResult:
        return self.call("git_branch", branch_name=branch_name, delete=delete)

    def _git_status(self) -> ToolResult:
        """Get git status parsing."""
        try:
            # 1. Get branch info
            proc_branch = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
            branch = proc_branch.stdout.strip() if proc_branch.returncode == 0 else "HEAD"

            # 2. Get upstream tracking status
            proc_tracking = self._run_git(["rev-parse", "--abbrev-ref", "@{u}"])
            tracking = proc_tracking.stdout.strip() if proc_tracking.returncode == 0 else ""

            # 3. Get changes
            proc_status = self._run_git(["status", "--porcelain=v1"])
            if proc_status.returncode != 0:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc_status.stderr)

            staged = []
            unstaged = []
            untracked = []

            for line in proc_status.stdout.splitlines():
                if len(line) < 4:
                    continue
                x, y = line[0], line[1]
                path = line[3:]

                # Porcelain status codes
                if x in {"M", "A", "D", "R", "C"}:
                    staged.append(path)
                if y in {"M", "D"}:
                    unstaged.append(path)
                if x == "?" and y == "?":
                    untracked.append(path)

            return ToolResult.ok({
                "branch": branch,
                "tracking": tracking,
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "is_clean": len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0
            })
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _git_diff(self, file_path: Optional[str] = None, staged: bool = False, revision: Optional[str] = None) -> ToolResult:
        """Diff workspace or revision."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        if revision:
            args.append(revision)
        if file_path:
            args.extend(["--", file_path])

        try:
            proc = self._run_git(args)
            if proc.returncode != 0:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc.stderr)

            # Count files changed
            proc_num = self._run_git(args + ["--numstat"])
            num_changed = len(proc_num.stdout.splitlines())

            return ToolResult.ok({
                "diff": proc.stdout,
                "files_changed": num_changed
            })
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_COMMAND_BLOCKED, str(e))
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _git_log(self, max_count: int = 10, file_path: Optional[str] = None) -> ToolResult:
        """Return history log."""
        args = ["log", f"-{max_count}", "--pretty=format:%H|%an|%ae|%aI|%s"]
        if file_path:
            args.extend(["--", file_path])

        try:
            proc = self._run_git(args)
            if proc.returncode != 0:
                # Empty repo (no commits) is not an error - return empty list
                if "does not have any commits yet" in proc.stderr or "no commits yet" in proc.stderr:
                    return ToolResult.ok({"commits": []})
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc.stderr)

            commits = []
            for line in proc.stdout.splitlines():
                if not line:
                    continue
                parts = line.split("|")
                if len(parts) >= 5:
                    commits.append({
                        "hash": parts[0],
                        "author": f"{parts[1]} <{parts[2]}>",
                        "date": parts[3],
                        "message": parts[4]
                    })

            return ToolResult.ok({"commits": commits})
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _git_commit(self, message: str, files: Optional[List[str]] = None) -> ToolResult:
        """Record changes via commit (requires approval)."""
        approval_error = self._check_operation_approval("git_commit", True)
        if approval_error:
            return approval_error

        try:
            # Stage files
            if files:
                # Validate every path stays inside the repository boundary and
                # is not a restricted path before passing it to `git add`.
                for path in files:
                    try:
                        self.resolver.resolve(path)
                    except PathResolverError as e:
                        return ToolResult.error(
                            ErrorCode.ERR_PATH_DENIED,
                            f"Refusing to stage '{path}': {e}"
                        )
                proc_add = self._run_git(["add"] + files)
                if proc_add.returncode != 0:
                    return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc_add.stderr)
            else:
                # Commit staged changes, check if they exist
                proc_status = self._run_git(["status", "--porcelain"])
                has_staged = any(line[0] in {"M", "A", "D", "R", "C"} for line in proc_status.stdout.splitlines())
                if not has_staged:
                    return ToolResult.error(ErrorCode.ERR_NOTHING_TO_COMMIT, "Nothing staged to commit")

            # Execute commit
            proc_commit = self._run_git(["commit", "-m", message])
            if proc_commit.returncode != 0:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc_commit.stderr)

            # Retrieve commit hash
            proc_hash = self._run_git(["rev-parse", "HEAD"])
            commit_hash = proc_hash.stdout.strip()

            return ToolResult.ok({
                "commit_hash": commit_hash,
                "status": "success"
            })
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _git_checkout(self, branch_name: str, create_new: bool = False) -> ToolResult:
        """Switch branches or create new (requires approval)."""
        approval_error = self._check_operation_approval("git_checkout", True)
        if approval_error:
            return approval_error

        args = ["checkout"]
        if create_new:
            args.append("-b")
        args.append(branch_name)

        try:
            proc = self._run_git(args)
            if proc.returncode != 0:
                # Check for dirty working tree preventing switch
                stderr_lower = proc.stderr.lower()
                if ("local changes" in stderr_lower and "would be overwritten" in stderr_lower) or \
                   ("would be overwritten by checkout" in stderr_lower):
                    return ToolResult.error(ErrorCode.ERR_DIRTY_WORKING_TREE, proc.stderr)
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc.stderr)

            return ToolResult.ok({"current_branch": branch_name})
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _git_branch(self, branch_name: str, delete: bool = False) -> ToolResult:
        """Git branch creation or manipulation (requires approval)."""
        approval_error = self._check_operation_approval("git_branch", True)
        if approval_error:
            return approval_error

        args = ["branch"]
        if delete:
            args.append("-d")
        args.append(branch_name)

        try:
            proc = self._run_git(args)
            if proc.returncode != 0:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, proc.stderr)
            return ToolResult.ok({"branch": branch_name})
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_COMMAND_BLOCKED, str(e))
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))
