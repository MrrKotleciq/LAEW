"""Filesystem tool wrapper (ADR-010, CONTRACT.md)."""

import os
from pathlib import Path
from typing import Optional

from laew.security import PathResolver, PathResolverError
from laew.tools.base import ErrorCode, Tool, ToolResult


class FilesystemTool(Tool):
    """
    Filesystem operations with security enforcement (P8).

    Implements tools/filesystem/CONTRACT.md v1.1.

    Operations:
        - view_file: Read file contents
        - list_dir: List directory entries
        - find_by_name: Search by glob pattern
        - grep_search: Search file contents
        - write_file: Create/overwrite file (requires approval)
        - replace_file_content: Modify file in place (requires approval)
    """

    READ_OPS = {"view_file", "list_dir", "find_by_name", "grep_search"}
    WRITE_OPS = {"write_file", "replace_file_content", "delete_file"}

    def __init__(self, resolver: Optional[PathResolver] = None):
        """
        Initialize filesystem tool.

        Args:
            resolver: PathResolver instance (creates default if None)
        """
        super().__init__(requires_approval=False)
        self.resolver = resolver or PathResolver()
        # Track explicit approval for mutating operations
        self._mutation_approved = False

    def approve(self):
        """Mark this tool as user-approved for mutating operations."""
        self._mutation_approved = True

    def is_approved(self) -> bool:
        """Check if mutating operations are approved."""
        return self._mutation_approved

    def _validate_mutation_operation(self, operation: str, file_path: str) -> tuple[Optional[ToolResult], Optional[Path]]:
        """
        Validate mutation operation: check approval and path constraints.

        Args:
            operation: Operation name (for error messages)
            file_path: File path to validate

        Returns:
            Tuple of (error_result, resolved_path) where error_result is None if valid
        """
        # Check user approval first (P7)
        approval_error = self._check_operation_approval(operation, True)
        if approval_error:
            return approval_error, None

        # Check if path is within @project
        try:
            resolved = self._resolve_path(file_path)
        except PathResolverError:
            error_msg = f"{operation.replace('_', ' ').title()} operations only allowed within @project"
            return ToolResult.error(ErrorCode.ERR_MUTATION_FORBIDDEN, error_msg), None

        alias = self.resolver.get_alias_for_path(resolved)
        if alias != "@project":
            error_msg = f"{operation.replace('_', ' ').title()} operations only allowed within @project, got {alias}"
            return ToolResult.error(ErrorCode.ERR_MUTATION_FORBIDDEN, error_msg), None

        return None, resolved

    def validate(self, operation: str, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate filesystem operation."""

        if operation not in self.READ_OPS and operation not in self.WRITE_OPS:
            return False, f"Unknown operation: {operation}"

        # All operations need a path
        path_key = "file_path" if "file_path" in kwargs else "directory_path"
        if path_key not in kwargs and operation not in {"grep_search", "find_by_name"}:
            return False, f"Missing required parameter: path"

        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """Execute filesystem operation."""

        try:
            if operation == "view_file":
                return self._view_file(**kwargs)
            elif operation == "list_dir":
                return self._list_dir(**kwargs)
            elif operation == "find_by_name":
                return self._find_by_name(**kwargs)
            elif operation == "grep_search":
                return self._grep_search(**kwargs)
            elif operation == "write_file":
                return self._write_file(**kwargs)
            elif operation == "replace_file_content":
                return self._replace_file_content(**kwargs)
            elif operation == "delete_file":
                return self._delete_file(**kwargs)
            else:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, f"Unknown operation: {operation}")

        except PathResolverError as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))
        except FileNotFoundError as e:
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, str(e))
        except IsADirectoryError:
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, "Path is a directory, not a file")
        except NotADirectoryError:
            return ToolResult.error(ErrorCode.ERR_DIR_NOT_FOUND, "Path is a file, not a directory")
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _resolve_path(self, path: str) -> Path:
        """Resolve aliased path to absolute path."""
        return self.resolver.resolve(path)

    def view_file(self, file_path: str, start_line: int = 1, end_line: Optional[int] = None) -> ToolResult:
        """Public interface for view_file operation."""
        return self.call("view_file", file_path=file_path, start_line=start_line, end_line=end_line)

    def _view_file(self, file_path: str, start_line: int = 1, end_line: Optional[int] = None) -> ToolResult:
        """Read file contents with optional line range."""

        resolved = self._resolve_path(file_path)

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, f"File not found: {file_path}")

        if not resolved.is_file():
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, f"Not a file: {file_path}")

        # Check for binary file
        try:
            with open(resolved, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return ToolResult.error(ErrorCode.ERR_BINARY_FILE, f"Binary file: {file_path}")
        except IOError as e:
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, str(e))

        # Read text content
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return ToolResult.error(ErrorCode.ERR_BINARY_FILE, f"Cannot decode as UTF-8: {file_path}")

        total_lines = len(lines)

        # Apply line range (1-indexed to 0-indexed)
        start_idx = max(0, start_line - 1)
        end_idx = total_lines if end_line is None else min(total_lines, end_line)

        content = "".join(lines[start_idx:end_idx])

        return ToolResult.ok({
            "content": content,
            "total_lines": total_lines,
            "size_bytes": resolved.stat().st_size,
        })

    def list_dir(self, directory_path: str = "@project", depth: int = 1) -> ToolResult:
        """Public interface for list_dir operation."""
        return self.call("list_dir", directory_path=directory_path, depth=depth)

    def _list_dir(self, directory_path: str = "@project", depth: int = 1) -> ToolResult:
        """List directory contents."""

        resolved = self._resolve_path(directory_path)

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_DIR_NOT_FOUND, f"Directory not found: {directory_path}")

        if not resolved.is_dir():
            return ToolResult.error(ErrorCode.ERR_DIR_NOT_FOUND, f"Not a directory: {directory_path}")

        entries = []

        def scan_dir(path: Path, current_depth: int):
            if current_depth > depth:
                return
            try:
                for entry in path.iterdir():
                    stat = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size_bytes": stat.st_size,
                        "modified_at": stat.st_mtime,
                    })
                    if entry.is_dir() and current_depth < depth:
                        scan_dir(entry, current_depth + 1)
            except PermissionError:
                pass

        scan_dir(resolved, 1)

        return ToolResult.ok({"entries": entries})

    def find_by_name(
        self,
        pattern: str,
        search_directory: str = "@project",
        entry_type: str = "any"
    ) -> ToolResult:
        """Public interface for find_by_name operation."""
        return self.call("find_by_name", pattern=pattern, search_directory=search_directory, entry_type=entry_type)

    def _find_by_name(
        self,
        pattern: str,
        search_directory: str = "@project",
        entry_type: str = "any"
    ) -> ToolResult:
        """Search for files by glob pattern."""

        resolved = self._resolve_path(search_directory)

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_DIR_NOT_FOUND, f"Directory not found: {search_directory}")

        if not resolved.is_dir():
            return ToolResult.error(ErrorCode.ERR_DIR_NOT_FOUND, f"Not a directory: {search_directory}")

        matches = []

        try:
            for match in resolved.rglob(pattern):
                if entry_type == "file" and not match.is_file():
                    continue
                if entry_type == "directory" and not match.is_dir():
                    continue
                matches.append(str(match.relative_to(resolved)))
        except PermissionError:
            pass

        return ToolResult.ok({
            "matches": matches,
            "match_count": len(matches),
        })

    def grep_search(
        self,
        query: str,
        search_path: str = "@project",
        is_regex: bool = False,
        case_insensitive: bool = True
    ) -> ToolResult:
        """Public interface for grep_search operation."""
        return self.call("grep_search", query=query, search_path=search_path, is_regex=is_regex, case_insensitive=case_insensitive)

    def _grep_search(
        self,
        query: str,
        search_path: str = "@project",
        is_regex: bool = False,
        case_insensitive: bool = True
    ) -> ToolResult:
        """Search file contents."""

        import re

        resolved = self._resolve_path(search_path)

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, f"Path not found: {search_path}")

        results = []

        # Build pattern
        if is_regex:
            flags = re.IGNORECASE if case_insensitive else 0
            try:
                pattern = re.compile(query, flags)
            except re.error as e:
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, f"Invalid regex: {e}")
        else:
            search_query = query.lower() if case_insensitive else query

        def search_file(file_path: Path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        match = False
                        if is_regex:
                            match = pattern.search(line) is not None
                        else:
                            line_to_check = line.lower() if case_insensitive else line
                            match = search_query in line_to_check

                        if match:
                            results.append({
                                "file": str(file_path.relative_to(resolved.parent)),
                                "line_number": line_num,
                                "line_content": line.rstrip("\n"),
                            })
            except (UnicodeDecodeError, PermissionError, IOError):
                pass

        if resolved.is_file():
            search_file(resolved)
        elif resolved.is_dir():
            for file_path in resolved.rglob("*"):
                if file_path.is_file():
                    search_file(file_path)

        return ToolResult.ok({"results": results})

    def write_file(
        self,
        file_path: str,
        content: str,
        overwrite: bool = False
    ) -> ToolResult:
        """Public interface for write_file operation."""
        return self.call("write_file", file_path=file_path, content=content, overwrite=overwrite)

    def _write_file(
        self,
        file_path: str,
        content: str,
        overwrite: bool = False
    ) -> ToolResult:
        """Create or overwrite file."""

        # Validate mutation operation
        validation_error, resolved = self._validate_mutation_operation("write_file", file_path)
        if validation_error:
            return validation_error

        # Check if file exists BEFORE writing
        file_existed = resolved.exists()

        if file_existed and not overwrite:
            return ToolResult.error(ErrorCode.ERR_FILE_EXISTS, f"File already exists: {file_path}")

        # Write file
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            bytes_written = len(content.encode("utf-8"))
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))

        return ToolResult.ok({
            "status": "overwritten" if file_existed else "created",
            "bytes_written": bytes_written,
        })

    def replace_file_content(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        target_content: str,
        replacement_content: str
    ) -> ToolResult:
        """Public interface for replace_file_content operation."""
        return self.call(
            "replace_file_content",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            target_content=target_content,
            replacement_content=replacement_content
        )

    def _replace_file_content(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        target_content: str,
        replacement_content: str
    ) -> ToolResult:
        """Replace content in file."""

        # Validate mutation operation
        validation_error, resolved = self._validate_mutation_operation("replace_file_content", file_path)
        if validation_error:
            return validation_error

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, f"File not found: {file_path}")

        # Read file
        try:
            with open(resolved, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except (PermissionError, IOError) as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))

        # Find and replace
        start_idx = start_line - 1
        end_idx = end_line

        if start_idx < 0 or end_idx > len(lines):
            return ToolResult.error(ErrorCode.ERR_TARGET_NOT_FOUND, "Line range out of bounds")

        actual_content = "".join(lines[start_idx:end_idx])
        if actual_content != target_content:
            return ToolResult.error(ErrorCode.ERR_TARGET_NOT_FOUND, "Target content does not match")

        # Perform replacement
        lines[start_idx:end_idx] = [replacement_content]

        try:
            resolved.write_text("".join(lines), encoding="utf-8")
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))

        return ToolResult.ok({"status": "success"})

    def delete_file(self, file_path: str) -> ToolResult:
        """Public interface for delete_file operation."""
        return self.call("delete_file", file_path=file_path)

    def _delete_file(self, file_path: str) -> ToolResult:
        """Delete file."""

        # Validate mutation operation
        validation_error, resolved = self._validate_mutation_operation("delete_file", file_path)
        if validation_error:
            return validation_error

        if not resolved.exists():
            return ToolResult.error(ErrorCode.ERR_FILE_NOT_FOUND, f"File not found: {file_path}")

        try:
            resolved.unlink()
        except PermissionError as e:
            return ToolResult.error(ErrorCode.ERR_PATH_DENIED, str(e))

        return ToolResult.ok({"status": "deleted"})
