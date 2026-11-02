"""Deterministic workbench policy and per-invocation approval requests."""

import copy
import json
import logging
import secrets
import threading

from laew.security.path_resolver import PathResolverError
from laew.tools.base import ErrorCode, ToolResult, authorized_once
from laew.tools.filesystem import FilesystemTool
from laew.tools.terminal import TerminalTool

logger = logging.getLogger(__name__)


class PermissionBroker:
    """Coordinate one-time approvals; grants never survive the broker instance."""

    def __init__(self, project_root, mode="auto", timeout=120):
        self.project_root = project_root.resolve() if project_root is not None else None
        self.mode = mode
        self.timeout = timeout
        self._lock = threading.Lock()
        self._requests = {}
        self._session_grants = set()

    def classify(self, tool, operation, args):
        if self.project_root is None:
            if isinstance(tool, FilesystemTool):
                if tool.resolver.project_root is not None:
                    return "denied"
                if operation == "write_knowledge_note":
                    try:
                        tool.knowledge_note_path(args.get("file_path", ""))
                        return "approval_required"
                    except (PathResolverError, ValueError, TypeError, OSError):
                        return "denied"
                return "safe" if operation in tool.READ_OPS else "denied"
            from laew.rag.rag_tool import RagTool
            from laew.tools.web import WebTool
            if isinstance(tool, RagTool):
                return "safe" if tool._global_only and args.get("scope", "global") == "global" else "denied"
            return "safe" if isinstance(tool, WebTool) else "denied"
        if isinstance(tool, FilesystemTool):
            if operation in tool.READ_OPS:
                return "safe"
            if operation not in tool.WRITE_OPS:
                return "denied"
            if operation == "write_knowledge_note":
                try:
                    tool.knowledge_note_path(args.get("file_path", ""))
                    return "approval_required"
                except (PathResolverError, ValueError, TypeError, OSError):
                    return "denied"
            try:
                path = tool.resolver.resolve(args.get("file_path", ""))
                path.relative_to(self.project_root)
                if tool.resolver.get_alias_for_path(path) != "@project":
                    return "denied"
            except (PathResolverError, ValueError, TypeError, OSError):
                return "denied"
            parts = [part.casefold() for part in path.relative_to(self.project_root).parts]
            name = path.name.casefold()
            sensitive = (any(part in {".github", ".gitlab", "security", "secrets", ".codex", ".claude"} for part in parts)
                         or parts[:2] in (["laew", "tools"], ["laew", "agent"], ["laew", "ui"])
                         or parts[:1] == ["manifests"]
                         or parts in (["laew", "web.py"], ["laew", "runtime.py"], ["laew", "project_config.py"])
                         or name in {".laew-project.json", "system_manifest.yaml", "dockerfile", "makefile", "pyproject.toml",
                                     "setup.py", "sitecustomize.py", "usercustomize.py", "conftest.py", "__main__.py"}
                         or name.startswith(".env") or name.endswith((".pem", ".key", ".ps1", ".bat", ".cmd", ".sh", ".exe")))
            if operation == "delete_file" or sensitive:
                return "approval_required"
            return "safe"
        if isinstance(tool, TerminalTool):
            command = args.get("command", "")
            if not isinstance(command, str) or tool._is_blacklisted(command) or tool._contains_shell_metacharacters(command):
                return "denied"
            try:
                cwd = (tool.workspace_root / args.get("cwd", ".")).resolve()
                cwd.relative_to(self.project_root)
            except (OSError, TypeError, ValueError):
                return "denied"
            # Arbitrary subprocesses are not a sandbox. Only exact, simple
            # inspection commands are admitted without an OS-level boundary.
            if command.strip() in {"git status", "pwd"} and tool._is_allowlisted(command):
                return "safe"
            # This exact diagnostic form disables external diff and textconv.
            # Arbitrary programs/scripts are denied: without an OS sandbox
            # their effects cannot be confined even after approval.
            if command.strip() == "git diff --stat --no-ext-diff --no-textconv":
                return "approval_required"
            return "denied"
        # Other native tool wrappers retain their own existing approval gates.
        return "safe"

    def decide(self, request_id, decision, session_id=None):
        with self._lock:
            pending = self._requests.get(request_id)
            if pending is None or pending["session_id"] != session_id or pending["decision"] is not None or decision not in ("allow", "allow_session", "deny"):
                return False
            if decision == "allow_session" and not pending["allow_session"]:
                return False
            pending["decision"] = decision
            logger.info("Approval decision %s: %s", request_id, decision)
            pending["event"].set()
            return True

    def call(self, tool, operation, args, emit, session_id=None, cancellation=None):
        def check_cancelled():
            if cancellation and cancellation.is_set():
                from laew.agent.executor import StreamCancelled
                raise StreamCancelled()
        check_cancelled()
        args = copy.deepcopy(args)
        valid, error = tool.validate(operation, **args)
        if not valid:
            return ToolResult.error(ErrorCode.ERR_INVALID_INPUT, error or "Invalid operation")
        risk = self.classify(tool, operation, args)
        logger.info("Permission classification %s.%s: %s (mode %s)", tool.name, operation, risk, self.mode)
        if risk == "denied":
            return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Operation blocked by the workbench security policy.")
        target = (str(tool.knowledge_note_path(args["file_path"]) if operation == "write_knowledge_note" else tool.resolver.resolve(args["file_path"]))
                  if isinstance(tool, FilesystemTool) and operation in tool.WRITE_OPS else None)
        session_key = (session_id, tool.name, operation, target,
                       json.dumps(args, sort_keys=True, ensure_ascii=False))
        eligible_session = bool(session_id) and risk == "safe" and isinstance(tool, FilesystemTool) and operation in {"write_file", "replace_file_content"}
        needs_approval = risk == "approval_required" or (
            self.mode in {"manual", "restricted"} and isinstance(tool, FilesystemTool) and operation in tool.WRITE_OPS)
        if self.mode == "manual" and eligible_session and session_key in self._session_grants:
            needs_approval = False
        if needs_approval:
            if self.mode == "restricted":
                return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Operation blocked in restricted mode.")
            if emit is None:
                return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Interactive approval requires a streaming workbench session.")
            request_id = secrets.token_urlsafe(24)
            pending = {"event": threading.Event(), "decision": None, "allow_session": eligible_session, "session_id": session_id}
            with self._lock:
                self._requests[request_id] = pending
            try:
                emit({"type": "approval", "id": request_id, "tool": tool.name, "operation": operation,
                      "project": str(self.project_root), "arguments": args, "risk": "approval_required",
                      "allow_session": eligible_session})
                # Heartbeats let a disconnected client cancel instead of leaving
                # an approval waiting until its full timeout.
                import time
                deadline = time.monotonic() + self.timeout
                next_heartbeat = time.monotonic() + 2
                while not pending["event"].wait(min(.2 if cancellation else 2, max(0, deadline - time.monotonic()))):
                    check_cancelled()
                    if time.monotonic() >= deadline:
                        return ToolResult.error(ErrorCode.ERR_TIMEOUT, "Approval timed out; operation was not executed.")
                    if time.monotonic() >= next_heartbeat:
                        emit({"type": "approval_wait", "id": request_id})
                        next_heartbeat = time.monotonic() + 2
                check_cancelled()
                if pending["decision"] not in {"allow", "allow_session"}:
                    return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "User denied approval; operation was not executed.")
            finally:
                with self._lock:
                    self._requests.pop(request_id, None)
            if self.classify(tool, operation, args) != risk:
                return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Operation changed while awaiting approval.")
            try:
                current_target = (tool.knowledge_note_path(args["file_path"]) if operation == "write_knowledge_note" else tool.resolver.resolve(args["file_path"])) if target is not None else None
            except (PathResolverError, ValueError, TypeError, OSError):
                return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Target changed while awaiting approval.")
            if target is not None and str(current_target) != target:
                return ToolResult.error(ErrorCode.ERR_UNAUTHORIZED, "Target changed while awaiting approval.")
            if pending["decision"] == "allow_session":
                self._session_grants.add(session_key)
        if isinstance(tool, FilesystemTool) and operation in tool.WRITE_OPS:
            check_cancelled()
            with authorized_once(tool):
                return tool.call(operation, **args)
        if isinstance(tool, TerminalTool) and risk == "approval_required":
            with authorized_once(tool):
                return tool.call(operation, **args)
        return tool.call(operation, **args)
