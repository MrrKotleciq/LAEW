"""Disposable Windows Job Object experiment; not a managed backup barrier.

Only processes started through this object are covered. It does not establish
writer identity, exclude external writers, inhibit restarts, or survive its owner.
"""
import ctypes
import os
from pathlib import Path
import subprocess
from contextlib import contextmanager

from laew.security import windows_appcontainer as ac


@contextmanager
def launch(argv, cwd):
    """Atomically launch one fixture process in an unnamed kill-on-close job.

    Yields (process handle, active-count callback). Handles are private and all
    contained processes are terminated when the context closes. The caller must
    separately verify the executable, arguments, environment and identity.
    """
    if os.name != "nt":
        raise ac.IsolationUnavailable("Windows Job Objects are unavailable.")
    from ctypes import wintypes as W

    if not argv or not all(isinstance(arg, str) and '\x00' not in arg for arg in argv):
        raise ValueError("Invalid fixture command.")
    if not Path(argv[0]).is_absolute() or not Path(cwd).is_absolute():
        raise ValueError("Fixture executable and working directory must be absolute.")

    class Accounting(ctypes.Structure):
        _fields_ = [("user", ctypes.c_longlong), ("kernel", ctypes.c_longlong),
                    ("period_user", ctypes.c_longlong), ("period_kernel", ctypes.c_longlong),
                    ("faults", W.DWORD), ("total", W.DWORD), ("active", W.DWORD),
                    ("terminated", W.DWORD)]

    query = ac._api(ac._K, "QueryInformationJobObject", W.BOOL, W.HANDLE, W.INT,
                    ac._P, W.DWORD, ctypes.POINTER(W.DWORD))
    job = ac._required(ac._job(None, None))
    attrs = None
    initialized = False
    process = ac._Process()
    try:
        limits = ac._ExtendedLimit()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ac._required(ac._job_info(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        size = ac._SIZE()
        ac._init_attrs(None, 1, 0, ctypes.byref(size))
        if not size.value:
            raise ac.IsolationUnavailable("Cannot size process attributes.")
        buf = ctypes.create_string_buffer(size.value)
        attrs = ctypes.cast(buf, ac._P)
        ac._required(ac._init_attrs(attrs, 1, 0, ctypes.byref(size)))
        initialized = True
        jobs = (W.HANDLE * 1)(job)
        ac._required(ac._update_attr(attrs, 0, 0x2000D, ctypes.byref(jobs), ctypes.sizeof(jobs), None, None))
        startup = ac._StartupEx()
        startup.startup.cb = ctypes.sizeof(startup)
        startup.attributes = attrs
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        ac._required(ac._create(argv[0], command, None, None, False, 0x00080000 | 0x08000000,
                                None, str(cwd), ctypes.byref(startup), ctypes.byref(process)))
        ac._close(process.thread)
        process.thread = None

        def active_count():
            counts = Accounting()
            ac._required(query(job, 1, ctypes.byref(counts), ctypes.sizeof(counts), None))
            return counts.active

        yield process.process, active_count
    finally:
        if initialized:
            ac._delete_attrs(attrs)
        if process.thread:
            ac._close(process.thread)
        if process.process:
            ac._close(process.process)
        ac._close(job)
