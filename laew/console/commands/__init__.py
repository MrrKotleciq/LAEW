"""Command handler registry for the LAEW testing console.

Handlers are pure functions ``(args: list[str], state: SessionState) -> int``
that print their output and return an exit code (0 = success).  The REPL
dispatches on this mapping, so adding a command is a one-line registration
plus a handler function.
"""

from typing import Callable, Dict

from laew.console.state import SessionState

# A console command handler: parse *args*, operate on *state*, print output,
# and return an exit code (0 = success, non-zero = failure).
CommandHandler = Callable[[list, "SessionState"], int]

#: Map of command name (first token on the line) to its handler.
COMMAND_HANDLERS: Dict[str, CommandHandler] = {}

# Each command handler is imported here once so that importing
# ``laew.console.commands`` is also the registration step — no eager work
# happens at session start, and handlers only import the runtime modules they
# need (lazy), keeping ``laew console`` fast to boot.
from laew.console.commands import core  # noqa: E402  (registration order)
from laew.console.commands import tool  # noqa: E402
from laew.console.commands import agent  # noqa: E402
from laew.console.commands import rag  # noqa: E402
from laew.console.commands import automation  # noqa: E402

# Merge each module's local registry into the global one.
for _module in (core, tool, agent, rag, automation):
    for _name, _handler in _module.register().items():
        COMMAND_HANDLERS[_name] = _handler