"""Tool command handlers for the LAEW testing console.

Drives the four security-gated :class:`Tool` wrappers (filesystem, git,
terminal, web) through ``tool <name> <op> [k=v ...]``, honouring the session's
approval-gate mode (``ask`` | ``auto`` | ``deny``) through the shared broker.
Auto permits classified safe actions; ask prompts; deny blocks gated actions.
"""

import json
from typing import Callable, Dict, Optional

from laew.console.state import SessionState
from laew.runtime import terminal_allowlist_from_manifest
from laew.tools import ErrorCode, FilesystemTool, GitTool, TerminalTool, WebTool

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


def _OP_TABLE() -> str:
    """Render the per-tool operation table (without instantiating tools)."""
    lines = ["Available tools and their operations:", ""]
    for name, factory in TOOL_FACTORIES.items():
        tool = factory([])  # empty allowlist; we only read the operation table
        lines.append(f"{name}  ({tool.name})")
        operations = tool.operations if hasattr(tool, "operations") and tool.operations else {}
        for op, meta in operations.items():
            params = ", ".join(str(p) for p in meta.get("params", [])) or "(no params)"
            ro = "read" if meta.get("read_only") else "write (requires approval)"
            lines.append(f"  .{op:<22} {ro:<26} {params}")
        lines.append("")
    return "\n".join(lines).rstrip()


def cmd_tool(args: list, state: SessionState) -> int:
    """
    tool <name> <op> [k=v ...] — execute a security-gated tool operation.

    Tools: filesystem, git, terminal, web.
    Ops:  see 'tools' for the full table, or 'tool help' / 'tool <name> help'.

    Examples:
      tool filesystem list_dir directory_path=@project
      tool git status
      tool terminal run_command command=ls
      tool web search_web query=LAEW

    Approval gates (set approval auto|ask|deny):
      auto  — executes classified safe actions without prompting.
      ask   — prompts before actions requiring approval.
      deny  — blocks actions requiring approval.
    Use <name>=<value> arguments; exact operation names differ from shell
    commands (use 'tool terminal run_command command=ls', not 'tool ls').
    """
    if not args:
        return _err("usage: tool <filesystem|git|terminal|web> <operation> [k=v ...]")

    # `tool help`, `tool -h`, and `tool <name> help` are help requests, never
    # tool operations.
    if args[0] in ("help", "-h", "--help"):
        print("tool <name> <op> [k=v ...] — execute a security-gated tool operation.\n")
        print(_OP_TABLE())
        print("Approval gates (set approval auto|ask|deny):")
        print("  auto  — executes classified safe actions without prompting.")
        print("  ask   — prompts before actions requiring approval.")
        print("  deny  — blocks actions requiring approval.")
        return 0

    name, operation = args[0], args[1] if len(args) > 1 else None
    if name not in TOOL_FACTORIES:
        return _err(f"unknown tool '{name}' (choose: {', '.join(TOOL_FACTORIES)})")
    if operation in ("help", "-h", "--help"):
        print(f"{name} — available operations:\n")
        print(_OP_TABLE())
        return 0
    if operation is None:
        return _err(f"usage: tool <{name}> <operation> [k=v ...]  (see 'tool help' for the operation list)")

    tool_kwargs, parse_err = _parse_kv_args(args[2:])
    if parse_err:
        return _err(parse_err)

    try:
        manifest = state.load_manifest()
        allowlist = terminal_allowlist_from_manifest(manifest)
    except Exception as e:
        return _err(e)
    tool = TOOL_FACTORIES[name](allowlist)

    from pathlib import Path
    from laew.console.permissions import console_broker, console_call
    project_root = getattr(getattr(tool, "resolver", None), "project_root", None) or getattr(tool, "workspace_root", None) or Path.cwd()
    broker = console_broker(state, Path(project_root))
    result = console_call(broker, tool, operation, tool_kwargs, f"console-{id(state)}")

    if result.success:
        print("[OK] operation succeeded")
        if result.data is not None:
            if isinstance(result.data, str):
                print(result.data)
            else:
                print(json.dumps(result.data, indent=2, default=str))
        return 0

    # ``error_code`` may be an ``ErrorCode`` enum member; on Python 3.11+
    # ``str()`` on a str-Enum renders the repr (``ErrorCode.ERR_...``), so read
    # ``.value`` for the bare code. ``ERR_INVALID_INPUT`` with an "Unknown
    # operation" message usually means the user typed a shell command instead of
    # a tool operation name — show the real operation list as a hint.
    code = getattr(result.error_code, "value", result.error_code) or "ERROR"
    print(f"[FAIL] {code}")
    if result.error_message:
        print(f"  {result.error_message}")
    if (
        code == ErrorCode.ERR_INVALID_INPUT.value
        and "operation" in (result.error_message or "").lower()
    ):
        ops = ", ".join((tool.operations or {}).keys())
        print(f"  available {name} operations: {ops or '(none declared)'}")
        print("  (shell commands belong under 'tool terminal run_command command=...')")
    return 1


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {"tool": cmd_tool}
