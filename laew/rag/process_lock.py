"""Host-local OS locks and crash-visible synchronization generations."""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


class CollectionLock:
    def __init__(self, key, timeout=30, cancel=None):
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        self.path = Path(tempfile.gettempdir()) / "laew-collection-locks" / (digest + ".lock")
        self.timeout = timeout
        self.cancel = cancel
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+b")
        deadline = time.monotonic() + self.timeout
        while True:
            if self.cancel is not None and self.cancel.is_set():
                self.handle.close(); self.handle = None
                raise RuntimeError("Collection lock acquisition cancelled.")
            try:
                if os.name == "nt":
                    import msvcrt
                    self.handle.seek(0)
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (OSError, BlockingIOError):
                if time.monotonic() >= deadline:
                    self.handle.close(); self.handle = None
                    raise TimeoutError("Timed out waiting for collection synchronization lock.")
                time.sleep(min(.05, max(0, deadline - time.monotonic())))

    def read_state(self):
        self.handle.seek(0)
        try:
            return json.loads(self.handle.read().decode("utf-8"))
        except (ValueError, UnicodeError):
            return {}

    def write_state(self, state):
        encoded = json.dumps(state, separators=(",", ":")).encode("utf-8")
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(encoded)
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def release(self):
        if self.handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close(); self.handle = None
