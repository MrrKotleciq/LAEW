"""Tool command handlers for the LAEW testing console.

Drives the four security-gated :class:`Tool` wrappers (filesystem, git,
terminal, web) through ``tool <name> <op> [k=v ...]``, honouring the session's
approval-gate mode (``ask`` | ``auto`` | ``deny``) so the P8 boundary can be
demonstrated from one session: **auto** approves before mutating, **ask**
prompts interactively, **deny** lets mutating operations return their
``ERR_UNAUTHORIZED`` result untouched.
"""

import json
from typing import Callable, Dict, Optional

from laew.console.state import SessionState
from laew.runtime import terminal_allowlist_from_manifest
from laew.tools import FilesystemTool, GitTool, TerminalTool, WebTool

#: Tool name (console command token) -> factory (:class:`Tool` instances).
TOOL_FACTORIES = {
    "filesystem": lambda allowlist: FilesystemTool(),
    "git": lambda allowlist: GitTool(),
    "terminal": lambda allowlist: TerminalTool(allowlist=allowlist),
    "web": lambda allowlist: WebTool(),
}


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _parse_kv_args(raw: Optional[list]) -> tuple[dict, Optional[str]]:
    """Parse ``key=value`` pairs; return (args, None) or ({}, error_msg)."""
    args: dict = {}
    for item in raw or []:
        if "=" not in item:
            return {}, f"invalid argument '{item}' (expected key=value)"
        key, value = item.split("=", 1)
        args[key] = value
    return args, None


def _approve_for_mode(tool, operation: str, state: SessionState) -> bool:
    """
    Apply the session approval mode to *tool* before a mutation.

    Returns True when the operation may proceed (already approved or read-only).
    In ``deny`` mode we never approve: the tool's own gate then rejects the
    mutation with ``ERR_UNAUTHORIZED``.
    """
    if state.approval == "auto":
        tool.approve()
        return True
    if state.approval == "ask":
        try:
            answer = input(f"Approve {tool.name}.{operation}? [y/N]: ").strip().lower()
        except EOFError:
            return False
        if answer == "y":
            tool.approve()
            return True
        print("[!] not approved")
        return False
    # deny mode: leave the gate armed so the mutation is refused.
    return True


def cmd_tool(args: list, state: SessionState) -> int:
    """tool <name> <op> [k=v ...] — execute a security-gated tool operation."""
    if len(args) < 2:
        return _err("usage: tool <filesystem|git|terminal|web> <operation> [k=v ...]")

    name, operation = args[0], args[1]
    if name not in TOOL_FACTORIES:
        return _err(f"unknown tool '{name}' (choose: {', '.join(TOOL_FACTORIES)})")

    tool_kwargs, parse_err = _parse_kv_args(args[2:])
    if parse_err:
        return _err(parse_err)

    try:
        manifest = state.load_manifest()
        allowlist = terminal_allowlist_from_manifest(manifest)
    except Exception as e:
        return _err(e)
    tool = TOOL_FACTORIES[name](allowlist)

    # Honour the approval gate BEFORE the mutating call so the P8 boundary is
    # the demonstrated behaviour, not a wall: ask/auto grant, deny refuses.
    if not _approve_for_mode(tool, operation, state):
        return 1

    result = tool.call(operation, **tool_kwargs)

    if result.success:
        print("[OK] operation succeeded")
        if result.data is not None:
            if isinstance(result.data, str):
                print(result.data)
            else:
                print(json.dumps(result.data, indent=2, default=str))
        return 0

    print(f"[FAIL] {result.error_code or 'ERROR'}")
    if result.error_message:
        print(f"  {result.error_message}")
    return 1


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {"tool": cmd_tool}