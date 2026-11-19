"""Hold the provisioned installation fence for an enrolled writer process."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from laew.backup.fence import FENCE_FILENAME, FenceConfigurationError, host_fence


_guard = threading.Lock()
_lease = None
_lock_path = None
_owner_pid = None


def enroll_writer_process():
    """Hold a shared lease until process exit, including worker shutdown.

    Older installations without the operator's enrollment variable follow their
    original path. Capture still requires confirmation that such writers have
    stopped and cannot restart during the cut.
    """
    global _lease, _lock_path, _owner_pid
    configured = os.environ.get("LAEW_INSTALLATION_FENCE")
    if not configured:
        return
    path = Path(configured)
    if not path.is_absolute() or path.name != FENCE_FILENAME or ".." in path.parts:
        raise FenceConfigurationError("Invalid installation fence path.")
    with _guard:
        if _lease is not None:
            if _lock_path != path or _owner_pid != os.getpid():
                raise FenceConfigurationError("Installation fence identity changed.")
            return
        lease = host_fence(path.parent, mode="writer")
        lease.__enter__()
        _lease = lease
        _lock_path = path
        _owner_pid = os.getpid()
