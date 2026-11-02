"""Filesystem tool wrapper (ADR-010, CONTRACT.md)."""

import os
import hashlib
import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Optional

from laew.security import PathResolver, PathResolverError
from laew.tools.base import ErrorCode, Tool, ToolResult, has_scoped_approval


def coerce_line_number(value, param_name: str) -> int:
    """
    Coerce a value to a positive integer line number, or raise ``ValueError``.

    Accepts an ``int`` or an int-parseable ``str`` (the console's ``k=v`` arg
    parser and LLM tool-call args can both deliver line numbers as strings);
    rejects booleans, floats, and non-numeric values with a clear message so the
    caller can return a proper ``ERR_INVALID_INPUT`` instead of letting a
    ``TypeError`` escape to the generic handler.

    Raises:
        ValueError: The value is not a positive integer (or cannot be parsed).
    """
    # bool is an int subclass; a float would silently truncate.  Reject both.
    if isinstance(value, bool):
        raise ValueError(f"{param_name} must be an integer, got boolean")
    if isinstance(value, float):
        raise ValueError(f"{param_name} must be an integer, got float")
    try:
        as_int = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{param_name} must be an integer, got {type(value).__name__}"
        ) from None
    if as_int < 1:
        raise ValueError(f"{param_name} must be >= 1, got {as_int}")
    return as_int


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

    description = ("Read project files and shared @knowledge notes. For profile requests, "
                   "inspect @knowledge/profile first; distinguish education, skills, interests "
                   "and goals, and do not infer skills. Ask one question at a time. "
                   "Propose edits before writing; write_knowledge_note requires explicit approval. "
                   "Only claim a write after the tool confirms success.")
    system_contract_path = "@project/tools/filesystem/CONTRACT.md"
    operations = {
        "view_file": {
            "params": ["file_path", "start_line", "end_line"],
            "description": "Read file contents (default: full file)",
            "read_only": True,
        },
        "list_dir": {
            "params": ["directory_path", "depth"],
            "description": "List directory entries",
            "read_only": True,
        },
        "find_by_name": {
            "params": ["pattern", "search_directory", "entry_type"],
            "description": "Search by glob pattern",
            "read_only": True,
        },
        "grep_search": {
            "params": ["query", "search_path", "is_regex", "case_insensitive"],
            "description": "Search file contents",
            "read_only": True,
        },
        "write_file": {
            "params": ["file_path", "content", "overwrite"],
            "description": "Create/overwrite file (requires approval)",
            "read_only": False,
        },
        "replace_file_content": {
            "params": ["file_path", "start_line", "end_line", "target_content", "replacement_content"],
            "description": "Modify file in place (requires approval)",
            "read_only": False,
        },
        "delete_file": {
            "params": ["file_path"],
            "description": "Delete file (requires approval)",
            "read_only": False,
        },
        "write_knowledge_note": {
            "params": ["file_path", "content", "expected_sha256"],
            "description": "Write a global Markdown note after explicit approval; use an empty expected_sha256 only for a new file. Preserve metadata and links. Notes are normally Polish.",
            "read_only": False,
        },
    }

    READ_OPS = {"view_file", "list_dir", "find_by_name", "grep_search"}
    WRITE_OPS = {"write_file", "replace_file_content", "delete_file", "write_knowledge_note"}

    def knowledge_note_path(self, value: str) -> Path:
        """Resolve a note within the vault and reject hidden paths and links."""
        if not isinstance(value, str) or not value:
            raise PathResolverError("A knowledge note path is required.")
        root = self.resolver.knowledge_root.resolve(strict=True)
        if value.startswith("@knowledge/"):
            candidate = root / value[len("@knowledge/"):]
        elif Path(value).is_absolute():
            candidate = Path(value)
        else:
            raise PathResolverError("Use @knowledge/ or an absolute vault path.")
        try:
            relative = candidate.absolute().relative_to(root)
        except ValueError:
            raise PathResolverError("Knowledge path is outside the vault.") from None
        if not relative.parts or any(p in (".", "..") or p.startswith(".") for p in relative.parts):
            raise PathResolverError("Hidden paths and traversal are forbidden.")
        if candidate.suffix.lower() != ".md":
            raise PathResolverError("Only Markdown knowledge notes can be written.")
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
                raise PathResolverError("Symlinks and junctions are forbidden for knowledge writes.")
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            raise PathResolverError("Knowledge path escapes the vault.") from None
        if not resolved.parent.is_dir():
            raise PathResolverError("The target directory must already exist.")
        return resolved

    def __init__(self, resolver: Optional[PathResolver] = None):
        """
        Initialize filesystem tool.

        Args:
            resolver: PathResolver instance (creates default if None)
        """
        super().__init__(requires_approval=False)
        self.resolver = resolver or PathResolver()
        if self.resolver.project_root is None:
            self.description = ("Read shared @knowledge notes. Global note writes require explicit approval. "
                                "Project paths and ordinary filesystem mutations are unavailable.")
            self.system_contract_path = None
            self.operations = {key: value for key, value in self.operations.items()
                               if key in self.READ_OPS or key == "write_knowledge_note"}
        # Track explicit approval for mutating operations
        self._mutation_approved = False

    def approve(self):
        """Mark this tool as user-approved for mutating operations."""
        self._mutation_approved = True

    def is_approved(self) -> bool:
        """Check if mutating operations are approved."""
        return self._mutation_approved or has_scoped_approval(self)

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

        # Validate write operation parameters
        if operation in self.WRITE_OPS:
            if operation == "write_knowledge_note":
                if not all(k in kwargs for k in ("file_path", "content", "expected_sha256")):
                    return False, "file_path, content and expected_sha256 are required"
                if not isinstance(kwargs["content"], str) or not isinstance(kwargs["expected_sha256"], str):
                    return False, "content and expected_sha256 must be strings"
            elif operation == "write_file":
                if "file_path" not in kwargs:
                    return False, "Missing required parameter: file_path"
                if "content" not in kwargs:
                    return False, "Missing required parameter: content"
            elif operation == "replace_file_content":
                required = ["file_path", "start_line", "end_line", "target_content", "replacement_content"]
                for param in required:
                    if param not in kwargs:
                        return False, f"Missing required parameter: {param}"
                # Type checks for line numbers
                if not isinstance(kwargs.get("start_line"), int) or not isinstance(kwargs.get("end_line"), int):
                    return False, "start_line and end_line must be integers"
            elif operation == "delete_file":
                if "file_path" not in kwargs:
                    return False, "Missing required parameter: file_path"

        # Validate view_file line parameters (int, or int-parseable str — the
        # console k=v parser and LLM tool-call args both deliver strings).
        if operation == "view_file":
            for param in ("start_line", "end_line"):
                value = kwargs.get(param)
                if value is None:
                    continue
                try:
                    coerce_line_number(value, param)
                except ValueError as e:
                    return False, str(e)

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
            elif operation == "write_knowledge_note":
                return self._write_knowledge_note(**kwargs)
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
        except UnicodeError:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, "The note must be valid UTF-8.")
        except Exception as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

    def _resolve_path(self, path: str) -> Path:
        """Resolve aliased path to absolute path."""
        return self.resolver.resolve(path)

    def _safe_general_entry(self, path: Path) -> bool:
        if self.resolver.project_root is not None:
            return True
        try:
            return (not path.is_symlink()
                    and not (hasattr(path, "is_junction") and path.is_junction())
                    and self.resolver.is_within_root(path, "@knowledge"))
        except OSError:
            return False

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

        # Line-range semantics: the DEFAULT is the full file.  start_line and
        # end_line may arrive as strings (console k=v parsing, LLM tool-call
        # args) or be silently guessed by a model, so coerce/validate them here
        # and reject bad values with a clear error instead of letting a
        # TypeError escape to the generic handler as a misleading
        # ERR_INVALID_INPUT.
        try:
            start_line = coerce_line_number(start_line, "start_line")
            end_line = None if end_line is None else coerce_line_number(end_line, "end_line")
        except ValueError as e:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, str(e))

        if end_line is not None and end_line < start_line:
            return ToolResult.error(
                ErrorCode.ERR_INVALID_INPUT,
                f"end_line ({end_line}) must be >= start_line ({start_line})",
            )

        total_lines = len(lines)

        # Apply line range (1-indexed to 0-indexed)
        start_idx = start_line - 1
        end_idx = total_lines if end_line is None else min(total_lines, end_line)

        content = "".join(lines[start_idx:end_idx])

        return ToolResult.ok({
            "content": content,
            "total_lines": total_lines,
            "size_bytes": resolved.stat().st_size,
            "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        })

    def _write_knowledge_note(self, file_path: str, content: str, expected_sha256: str) -> ToolResult:
        """Validate content independently of the broker's one-operation approval."""
        import yaml
        from laew.rag.obsidian import FRONTMATTER_RE

        if not has_scoped_approval(self):
            return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Knowledge writes require a broker approval.")
        path = self.knowledge_note_path(file_path)
        encoded = content.encode("utf-8")
        if len(encoded) > 1024 * 1024:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, "Knowledge note exceeds 1 MiB.")
        def metadata(text):
            match = FRONTMATTER_RE.match(text.replace("\r\n", "\n"))
            if not match:
                raise ValueError("A YAML frontmatter block is required.")
            try:
                data = yaml.safe_load(match.group(1))
            except yaml.YAMLError:
                raise ValueError("Invalid YAML frontmatter.") from None
            if not isinstance(data, dict) or data.get("scope") != "global" or not data.get("type"):
                raise ValueError("Frontmatter must include type and global scope.")
            if not isinstance(data["type"], str) or ("tags" in data and not isinstance(data["tags"], list)):
                raise ValueError("Frontmatter type must be a string and tags must be a list.")
            return data
        new_metadata = metadata(content)
        exists = path.exists()
        if exists:
            old_bytes = path.read_bytes()
            if not expected_sha256 or hashlib.sha256(old_bytes).hexdigest() != expected_sha256:
                return ToolResult.error(ErrorCode.ERR_TARGET_NOT_FOUND, "Note changed or expected hash is missing; read it again.")
            old = old_bytes.decode("utf-8")
            old_metadata = metadata(old)
            if any(new_metadata.get(k) != v for k, v in old_metadata.items()):
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, "Existing frontmatter must be preserved.")
            links = r"!?\[\[[^\]]+\]\]"
            if Counter(re.findall(links, old)) - Counter(re.findall(links, content)):
                return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, "Existing wikilinks must be preserved.")
        elif expected_sha256:
            return ToolResult.error(ErrorCode.ERR_TARGET_NOT_FOUND, "Expected existing note does not exist.")
        if not exists:
            if self.knowledge_note_path(file_path) != path:
                return ToolResult.error(ErrorCode.ERR_PATH_DENIED, "Knowledge target changed during approval.")
            with path.open("xb") as handle:
                handle.write(encoded)
        else:
            temp_name = None
            try:
                with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".laew-note-", delete=False) as handle:
                    temp_name = handle.name
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                if self.knowledge_note_path(file_path) != path or hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
                    return ToolResult.error(ErrorCode.ERR_TARGET_NOT_FOUND, "Note changed during approval; retry.")
                os.replace(temp_name, path)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)
        return ToolResult.ok({"status": "updated" if exists else "created", "sha256": hashlib.sha256(encoded).hexdigest(),
                              "sync_required": True, "message": "Synchronize global knowledge before retrieval; excluded folders remain excluded."})

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
                    if not self._safe_general_entry(entry):
                        continue
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
                if not self._safe_general_entry(match):
                    continue
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
                if self._safe_general_entry(file_path) and file_path.is_file():
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

        # Perform replacement without mutating the read list (immutability rule)
        new_lines = lines[:start_idx] + [replacement_content] + lines[end_idx:]

        try:
            resolved.write_text("".join(new_lines), encoding="utf-8")
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
