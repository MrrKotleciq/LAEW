"""Host-local lifetime locks for cooperating LAEW writers and maintenance.

The profile owner provisions and protects the stable directory, its ancestors
and lock file from replacement. Use one file per installation on a supported
local filesystem. External writer acknowledgements are a separate barrier.
"""

import errno
import math
import os
import stat
import time
from contextlib import contextmanager
from pathlib import Path


FENCE_FILENAME = "installation.lock"


class FenceBusyError(TimeoutError):
    """Other cooperating participants hold an incompatible lock."""


class FenceConfigurationError(ValueError):
    """The configured installation lock cannot be used safely."""


def _is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _open_lock(directory):
    root = Path(directory)
    if not root.is_absolute() or ".." in root.parts:
        raise FenceConfigurationError("The installation fence needs an absolute local directory.")
    if os.name == "nt" and (
        root.drive.startswith("\\\\") or any(":" in part for part in root.parts[1:])
    ):
        raise FenceConfigurationError("Unsupported installation fence path.")
    if os.name == "nt" and _drive_type(root.anchor) != 3:  # DRIVE_FIXED
        raise FenceConfigurationError("The installation fence requires a fixed local volume.")
    for path in (*reversed(root.parents), root):
        info = path.lstat()
        if _is_link(info) or not stat.S_ISDIR(info.st_mode):
            raise FenceConfigurationError("Unsafe installation fence directory.")
    if os.name == "posix" and info.st_mode & 0o022:
        raise FenceConfigurationError("The installation fence directory permits other writers.")
    path = root / FENCE_FILENAME
    before = path.lstat()
    if _is_link(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise FenceConfigurationError("Unsafe installation fence file.")
    fd = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        opened = os.fstat(fd)
        after = path.lstat()
        if not (os.path.samestat(before, opened) and os.path.samestat(opened, after)):
            raise FenceConfigurationError("Installation fence file changed during acquisition.")
        if opened.st_nlink != 1 or _is_link(after):
            raise FenceConfigurationError("Unsafe installation fence file.")
        return fd
    except BaseException:
        os.close(fd)
        raise


if os.name == "nt":
    import ctypes
    import msvcrt
    from ctypes import wintypes

    class _Overlapped(ctypes.Structure):
        _fields_ = [
            ("Internal", ctypes.c_size_t),
            ("InternalHigh", ctypes.c_size_t),
            ("Offset", wintypes.DWORD),
            ("OffsetHigh", wintypes.DWORD),
            ("hEvent", wintypes.HANDLE),
        ]

    _lock_file = ctypes.WinDLL("kernel32", use_last_error=True).LockFileEx
    _lock_file.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                           wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_Overlapped)]
    _lock_file.restype = wintypes.BOOL
    _drive_type = ctypes.WinDLL("kernel32", use_last_error=True).GetDriveTypeW
    _drive_type.argtypes = [wintypes.LPCWSTR]
    _drive_type.restype = wintypes.UINT

    def _try_lock(fd, exclusive):
        # LOCKFILE_FAIL_IMMEDIATELY, optionally LOCKFILE_EXCLUSIVE_LOCK.
        flags = 1 | (2 if exclusive else 0)
        if _lock_file(msvcrt.get_osfhandle(fd), flags, 0, 1, 0, ctypes.byref(_Overlapped())):
            return True
        error = ctypes.get_last_error()
        if error == 33:  # ERROR_LOCK_VIOLATION
            return False
        raise ctypes.WinError(error)

elif os.name == "posix":
    import fcntl

    def _try_lock(fd, exclusive):
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(fd, operation | fcntl.LOCK_NB)
            return True
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                return False
            raise


@contextmanager
def host_fence(lock_directory, *, mode, timeout=0.0):
    """Hold a shared writer or exclusive maintenance lease for the context.

    The yielded path identifies the lock. Its file must never be removed
    during normal operation. Worker processes independently acquire leases
    for their full writer lifetime. Use spawn/exec for independent workers.
    """
    if mode not in ("writer", "maintenance"):
        raise ValueError("Invalid installation fence mode.")
    if not math.isfinite(timeout) or timeout < 0:
        raise ValueError("Fence timeout must be finite and nonnegative.")
    if os.name not in ("nt", "posix"):
        raise FenceConfigurationError("Unsupported installation fence platform.")
    deadline = time.monotonic() + timeout
    try:
        fd = _open_lock(lock_directory)
    except OSError as exc:
        raise FenceConfigurationError("Cannot open the provisioned installation fence.") from exc
    try:
        while not _try_lock(fd, mode == "maintenance"):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise FenceBusyError("Installation fence is busy.")
            time.sleep(min(0.025, remaining))
        yield Path(lock_directory) / FENCE_FILENAME
    finally:
        os.close(fd)
