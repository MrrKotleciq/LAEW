"""Process-local, scope-specific synchronization status and coordination."""

from datetime import datetime, timezone
import threading
import logging

logger = logging.getLogger(__name__)

_guard = threading.Lock()
_entries = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _entry(kb, scope):
    store = kb.project_store if scope == "project" else kb.global_store
    config = kb._vector_store_config if isinstance(kb._vector_store_config, dict) else {}
    # In-memory stores are independent, even when they have identical roots.
    if config.get("enabled"):
        from laew.rag.identity import project_collection_name
        collection = (project_collection_name(kb.project_root) if scope == "project"
                      else config.get("global_collection", "laew_global"))
    else:
        collection = store
    key = (config.get("host"), config.get("port"), collection, scope)
    with _guard:
        return _entries.setdefault(key, {"lock": threading.Lock(), "state": "never synchronized",
            "last_success": None, "last_failure": None, "error": None})


def sync_status(kb, scope):
    entry = _entry(kb, scope)
    with _guard:
        return {key: value for key, value in entry.items() if key != "lock"}


def synchronize_scope(kb, scope, *, force=False):
    # Key even a failed reconnect by its intended persistent collection, not
    # by a transient in-memory fallback, so all callers see the failure.
    entry = _entry(kb, scope)
    if not entry["lock"].acquire(blocking=False):
        raise RuntimeError(f"{scope} synchronization is already in progress; retry when it finishes.")
    try:
        with _guard:
            entry["state"] = "synchronization in progress"
            entry["error"] = None
        try:
            kb.ensure_store(scope)
            result = kb.synchronize(force=force, scope=scope)
        except Exception:
            with _guard:
                entry["state"] = "synchronization failed"
                entry["last_failure"] = _now()
                label = f"project {kb.project_root}" if scope == "project" else "global knowledge"
                entry["error"] = (f"{label} synchronization failed. Existing index data may be partially updated; "
                                  "retrieval is blocked. Check directory access, ChromaDB and the embedding server, "
                                  "then retry synchronization.")
            raise
        with _guard:
            entry["state"] = "successfully synchronized"
            entry["last_success"] = _now()
        return result
    finally:
        entry["lock"].release()


def freshness_error(kb, scope):
    status = sync_status(kb, scope)
    if status["state"] == "successfully synchronized":
        return None
    label = f"project {kb.project_root}" if scope == "project" else "global knowledge"
    return (status["error"] or f"{label}: index freshness is unknown ({status['state']}). "
            "Run synchronization and check ChromaDB, directory access, and the embedding server.")


def acquire_fresh_scopes(kb, scopes):
    """Hold scope locks across retrieval so writes cannot start mid-query."""
    acquired = []
    for scope in sorted(scopes):
        lock = _entry(kb, scope)["lock"]
        if not lock.acquire(blocking=False):
            for held in reversed(acquired):
                held.release()
            return [], f"{scope} synchronization is in progress; retry retrieval when it finishes."
        acquired.append(lock)
        error = freshness_error(kb, scope)
        if error:
            for held in reversed(acquired):
                held.release()
            return [], error
    return acquired, None


class SyncScheduler:
    """One lifecycle-managed periodic global sync, independent of browser sessions."""

    def __init__(self, build_base, interval=1800):
        self._build_base = build_base
        self._interval = interval
        self._stop = threading.Event()
        self._threads = []
        self._thread_guard = threading.Lock()

    def request(self, scope, project_root=None):
        def run():
            try:
                kb = self._build_base(project_root)
                synchronize_scope(kb, scope)
            except Exception:
                logger.exception("%s knowledge synchronization failed", scope)
        thread = threading.Thread(target=run, name=f"laew-sync-{scope}", daemon=True)
        with self._thread_guard:
            self._threads = [t for t in self._threads if t.is_alive()]
            self._threads.append(thread)
            thread.start()

    def start(self, project_root=None):
        self.request("global", project_root)
        if project_root is not None:
            self.request("project", project_root)
        def periodic():
            while not self._stop.wait(self._interval):
                self.request("global", project_root)
        thread = threading.Thread(target=periodic, name="laew-sync-scheduler", daemon=True)
        with self._thread_guard:
            self._threads.append(thread)
            thread.start()

    def close(self):
        self._stop.set()
        with self._thread_guard:
            threads = list(self._threads)
        for thread in threads:
            thread.join()
