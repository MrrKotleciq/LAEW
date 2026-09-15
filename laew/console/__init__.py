"""LAEW Interactive Testing Console."""

import cmd
import sys
from typing import Optional

from .session import ConsoleSession


def run_console(manifest_path: Optional[str] = None) -> int:
    """
    Run the LAEW interactive testing console.

    Args:
        manifest_path: Optional path to system manifest

    Returns:
        Exit code (0 for normal exit, 1 for error)
    """
    try:
        session = ConsoleSession(manifest_path=manifest_path)
        session.cmdloop()
        return 0
    except KeyboardInterrupt:
        print("\nSession interrupted.")
        return 1
    except Exception as e:
        print(f"[FAIL] Console failed to start: {e}")
        return 1


__all__ = ["run_console", "ConsoleSession"]