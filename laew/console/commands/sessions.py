"""Session persistence commands for the LAEW console (Milestone 13).

Adds ``session save|load|list|show|delete`` so a console session — command
history, overrides, approval mode, and agent conversation memory — can be
saved to disk and resumed across restarts.

The stored payload holds memory and preferences only (ADR-012).  On load the
manifest is re-verified from the filesystem rather than trusted from the file;
project state is never restored from a session.
"""

from pathlib import Path
from typing import Callable, Dict

from laew.console.session_store import (
    DEFAULT_SESSION_STORAGE,
    InvalidSessionName,
    SessionStore,
    SessionStoreError,
    session_store_from_manifest,
)
from laew.console.state import SessionState, StateError


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _resolve_store(state: SessionState) -> SessionStore:
    """
    Resolve the session store for a state.

    Prefers the manifest's ``memory.session.storage`` location; falls back to
    the default ``runtime/sessions`` when the manifest cannot be read, keeping
    the command usable offline.
    """
    try:
        return session_store_from_manifest(state.load_manifest())
    except StateError:
        return SessionStore(DEFAULT_SESSION_STORAGE)


# --------------------------------------------------------------------------- #
# session save <name>
# --------------------------------------------------------------------------- #
def _cmd_save(args: list, state: SessionState) -> int:
    """Save the current console session state to disk under <name>."""
    if len(args) < 1:
        return _err("usage: session save <name>")
    name = args[0]
    store = _resolve_store(state)
    try:
        record = store.save(name, state.to_payload())
    except InvalidSessionName as e:
        return _err(e)
    except SessionStoreError as e:
        return _err(e)
    print(
        f"[OK] session '{name}' saved "
        f"(history {record.history_count}, conversation {record.conversation_count})"
    )
    print(f"  path: {store.path_for(record.name)}")
    return 0


# --------------------------------------------------------------------------- #
# session load <name>
# --------------------------------------------------------------------------- #
def _cmd_load(args: list, state: SessionState) -> int:
    """Restore a saved session into this console session."""
    if len(args) < 1:
        return _err("usage: session load <name>")
    name = args[0]
    store = _resolve_store(state)

    try:
        payload = store.load(name)
        restored = SessionState.from_payload(payload)
    except FileNotFoundError:
        return _err(f"no saved session named '{name}' (see 'session list')")
    except InvalidSessionName as e:
        return _err(e)
    except SessionStoreError as e:
        return _err(e)
    except StateError as e:
        return _err(f"session '{name}' cannot be restored: {e}")

    # ADR-012: never trust stored state as ground truth. Re-verify the saved
    # manifest path against the authoritative manifest; if it is not loadable
    # (e.g. the session came from another project), keep the current manifest.
    original_manifest = state.manifest_path
    try:
        restored.load_manifest()
    except StateError:
        print(
            f"[!] saved manifest '{restored.manifest_path}' is not loadable; "
            f"keeping current '{original_manifest}'"
        )
        restored.manifest_path = original_manifest

    state.restore(restored)
    print(
        f"[OK] session '{name}' loaded "
        f"(history {len(state.history)}, conversation {len(state.conversation)})"
    )
    print(f"  manifest: {state.manifest_path}")
    print(f"  approval: {state.approval}; trace: {'on' if state.trace else 'off'}")
    return 0


# --------------------------------------------------------------------------- #
# session list
# --------------------------------------------------------------------------- #
def _cmd_list(args: list, state: SessionState) -> int:
    """List saved sessions (metadata only, newest first)."""
    store = _resolve_store(state)
    records = store.list_sessions()
    if not records:
        print("(no saved sessions)")
        return 0
    print(f"{len(records)} saved session(s):")
    for record in records:
        print(
            f"  {record.name:<20} {record.kind:<7} "
            f"history={record.history_count:<3} "
            f"conversation={record.conversation_count:<3} "
            f"updated={record.updated_at}"
        )
    return 0


# --------------------------------------------------------------------------- #
# session show <name>
# --------------------------------------------------------------------------- #
def _cmd_show(args: list, state: SessionState) -> int:
    """Show metadata for a saved session without restoring it."""
    if len(args) < 1:
        return _err("usage: session show <name>")
    name = args[0]
    store = _resolve_store(state)
    try:
        payload = store.load(name)
    except FileNotFoundError:
        return _err(f"no saved session named '{name}' (see 'session list')")
    except InvalidSessionName as e:
        return _err(e)
    except SessionStoreError as e:
        return _err(e)

    print(f"session: {name}")
    print(f"  kind: {payload.get('kind', 'console')}")
    print(f"  manifest: {payload.get('manifest_path')}")
    print(f"  created: {payload.get('created_at')}")
    print(f"  updated: {payload.get('updated_at')}")
    print(f"  overrides: {len(payload.get('overrides', {}))}")
    print(f"  approval: {payload.get('approval')}")
    print(f"  trace: {payload.get('trace')}")
    print(f"  history entries: {len(payload.get('history', []))}")
    print(f"  conversation turns: {len(payload.get('conversation', []))}")
    return 0


# --------------------------------------------------------------------------- #
# session delete <name>
# --------------------------------------------------------------------------- #
def _cmd_delete(args: list, state: SessionState) -> int:
    """Delete a saved session from disk."""
    if len(args) < 1:
        return _err("usage: session delete <name>")
    name = args[0]
    store = _resolve_store(state)
    try:
        deleted = store.delete(name)
    except InvalidSessionName as e:
        return _err(e)
    except SessionStoreError as e:
        return _err(e)
    if not deleted:
        return _err(f"no saved session named '{name}' (see 'session list')")
    print(f"[OK] session '{name}' deleted")
    return 0


# --------------------------------------------------------------------------- #
# session — dispatcher
# --------------------------------------------------------------------------- #
def cmd_session(args: list, state: SessionState) -> int:
    """
    Manage durable console sessions: save | load | list | show | delete.

    Persists command history, session overrides, approval mode, and the agent
    conversation so a session can be resumed after a restart.

    Examples:
      session save research       # save current state
      session load research       # restore it into this session
      session list                # show saved sessions (metadata only)
      session show research       # metadata without restoring
      session delete research     # remove a saved session
    """
    if not args:
        return _err(
            "usage: session save|load|list|show|delete ...  (see 'help session')"
        )
    sub = args[0]
    rest = args[1:]
    handlers = {
        "save": _cmd_save,
        "load": _cmd_load,
        "list": _cmd_list,
        "show": _cmd_show,
        "delete": _cmd_delete,
    }
    handler = handlers.get(sub)
    if handler is None:
        return _err(
            f"unknown session subcommand: {sub} "
            f"(save|load|list|show|delete)"
        )
    return handler(rest, state)


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {"session": cmd_session}