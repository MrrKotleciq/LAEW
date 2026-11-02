"""Console approval handler for the shared permission broker."""

import json
import sys
from pathlib import Path

from laew.security.permissions import PermissionBroker


def console_broker(state, project_root):
    project = Path(project_root).resolve()
    mode = {"auto": "auto", "ask": "manual", "deny": "restricted"}[state.approval]
    broker = getattr(state, "_permission_broker", None)
    if broker is None or broker.project_root != project:
        broker = PermissionBroker(project, mode)
        state._permission_broker = broker
    broker.mode = mode
    return broker


def console_call(broker, tool, operation, args, session_id):
    def prompt(event):
        if event["type"] != "approval":
            return
        if not sys.stdin.isatty():
            broker.decide(event["id"], "deny", session_id)
            return
        print(f"Approval requested: {event['tool']}.{event['operation']} in {event['project']}")
        print(json.dumps(event["arguments"], ensure_ascii=False, indent=2))
        try:
            answer = input("Allow once? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        broker.decide(event["id"], "allow" if answer == "y" else "deny", session_id)
    return broker.call(tool, operation, args, prompt, session_id)
