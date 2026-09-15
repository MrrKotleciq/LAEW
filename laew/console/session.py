"""Console session REPL and command dispatcher."""

import cmd
import shlex
import sys
from typing import Dict, List, Optional
from laew.console.state import SessionState
from laew.console.commands import COMMAND_HANDLERS

class ConsoleSession(cmd.Cmd):
    """
    Interactive REPL for LAEW testing.

    Reuses all core runtime blocks (Tool classes, AgentExecutor, engines) via
    the command handlers in :mod:`laew.console.commands`. Input is split with
    :func:`shlex.split` so quoted arguments (prompts, paths) work. Unknown or
    malformed commands produce a readable error instead of crashing the REPL.
    """

    intro = (
        "LAEW Interactive Console. Type 'help' or '?' for commands, "
        "'exit' or 'quit' to leave."
    )
    prompt = "(laew) "

    def __init__(self, manifest_path: Optional[str] = None):
        super().__init__()
        self.state = SessionState(
            manifest_path=manifest_path or "manifests/SYSTEM_MANIFEST.yaml"
        )

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #
    def default(self, line: str) -> None:
        """Parse a command line and dispatch to a registered handler."""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            print(f"[FAIL] Could not parse command: {e}")
            return
        if not parts:
            return

        cmd_name = parts[0]
        args = parts[1:]

        # Ignore echo'd history repeats from the interactive loop.
        self.state.record(line)

        # ``!N`` is not a valid ``do_`` method name, so intercept it here.
        if cmd_name.startswith("!"):
            self.do_rerepeat(cmd_name[1:])
            return

        handler = COMMAND_HANDLERS.get(cmd_name)
        if handler is None:
            print(f"Unknown command: {cmd_name}  (type 'help' for a list)")
            return

        try:
            exit_code = handler(args, self.state)
        except Exception as e:  # handlers print their own errors; this is a net
            print(f"[FAIL] {e}")
            return

        if exit_code != 0:
            print(f"[FAIL] Command '{cmd_name}' failed (code {exit_code})")

    # ------------------------------------------------------------------ #
    # Built-in commands
    # ------------------------------------------------------------------ #
    def do_exit(self, arg: str) -> bool:
        """Exit the console."""
        return True

    def do_quit(self, arg: str) -> bool:
        """Exit the console."""
        return True

    def do_history(self, arg: str) -> None:
        """Show in-session command history."""
        if not self.state.history:
            print("(history is empty)")
            return
        width = len(str(len(self.state.history)))
        for i, line in enumerate(self.state.history, 1):
            print(f"{i:>{width}}  {line}")

    def do_rerepeat(self, arg: str) -> None:
        """Re-run a history entry: !N re-runs entry N."""
        try:
            index = int(arg)
        except ValueError:
            print("[FAIL] usage: !<number>  (see 'history')")
            return
        if not (1 <= index <= len(self.state.history)):
            print(f"[FAIL] history entry {index} out of range")
            return
        line = self.state.history[index - 1]
        print(f"-> {line}")
        self.onecmd(line)

    def emptyline(self) -> None:
        """Ignore empty input (cmd.Cmd would otherwise repeat the last line)."""

    def do_help(self, arg: str) -> None:
        """Show help for a console command, or list all commands."""
        topic = arg.strip() if arg else ""
        if topic:
            self._help_for_topic(topic)
            return

        # No topic: list every registered command with its one-line docstring.
        lines = ["Documented commands:", ""]
        for name in sorted(COMMAND_HANDLERS):
            doc = getattr(COMMAND_HANDLERS[name], "__doc__") or "(no help)"
            lines.append(f"  {name:<12} {doc.strip().splitlines()[0]}")
        lines.append("")
        lines.append("Console: 'history', '!<N>' (re-run history entry), 'exit'/'quit'.")
        print("\n".join(lines))

    def _help_for_topic(self, topic: str) -> None:
        """Print help for a single topic (registered command or built-in)."""
        cmd_name = topic.split()[0]

        if cmd_name.startswith("!"):
            print("Re-run a history entry: !<N> (see 'history').")
            return

        handler = COMMAND_HANDLERS.get(cmd_name)
        if handler is not None:
            print((getattr(handler, "__doc__") or "No help available.").strip())
            return

        builtins = {
            "exit": "Exit the console.",
            "quit": "Exit the console.",
            "history": "Show in-session command history.",
            "help": "Show help for a command, or list all commands.",
        }
        if cmd_name in builtins:
            print(builtins[cmd_name])
            return

        print(f"Unknown command: {cmd_name}  (type 'help' for a list)")


def run_console(manifest_path: Optional[str] = None) -> int:
    """
    Run the LAEW interactive console until 'exit'/'quit' or EOF.

    Args:
        manifest_path: Optional path to the system manifest.

    Returns:
        0 on normal exit, 1 on interruption or startup failure.
    """
    # ToolLogger (laew.tools, ADR-016) has its own StreamHandler that emits the
    # raw JSON line. Without ``propagate=False`` each record also travels up to
    # the ``laew`` logger added by configure_logging() and prints a second,
    # formatted copy — the duplicate per-call log lines in the console. Stop
    # the propagation here so only the single ADR-016 line reaches the session.
    import logging

    tools_logger = logging.getLogger("laew.tools")
    tools_logger.propagate = False

    try:
        session = ConsoleSession(manifest_path=manifest_path)
        session.cmdloop()
        return 0
    except KeyboardInterrupt:
        print("\nSession interrupted.")
        return 1
    except Exception as e:
        print(f"[FAIL] Console could not start: {e}")
        return 1