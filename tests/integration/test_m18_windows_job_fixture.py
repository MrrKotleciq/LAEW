"""Synthetic tests of atomic Windows job assignment; not barrier qualification."""
import ctypes
import os
from pathlib import Path
import sys
import time

import pytest
from laew.security import windows_appcontainer as ac
from tests.integration.m18_windows_job_fixture import launch

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job Objects")


def test_job_tracks_child_after_parent_exits_and_closes_it(tmp_path):
    from ctypes import wintypes as W

    ready = tmp_path / "ready"
    child = (
        "import os,pathlib,time,sys; "
        "ready=pathlib.Path(sys.argv[1]); "
        "stage=ready.with_suffix('.tmp'); "
        "stage.write_text(str(os.getpid())); "
        "stage.replace(ready); "
        "time.sleep(30)"
    )
    parent = "import subprocess,sys; subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])"
    open_process = ac._api(ac._K, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
    exit_code = ac._api(ac._K, "GetExitCodeProcess", W.BOOL, W.HANDLE, ctypes.POINTER(W.DWORD))
    child_handle = None
    try:
        with launch([sys.executable, "-c", parent, child, str(ready)], tmp_path) as (process, active):
            assert ac._wait(process, 10000) == 0
            status = W.DWORD()
            ac._required(exit_code(process, ctypes.byref(status)))
            assert status.value == 0
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            assert ready.exists()
            child_handle = ac._required(open_process(0x00100000, False, int(ready.read_text())))
            assert ac._wait(child_handle, 0) == 0x102
            assert active() >= 1
        assert ac._wait(child_handle, 10000) == 0
    finally:
        if child_handle:
            ac._close(child_handle)


def test_requires_absolute_executable_and_directory(tmp_path):
    with pytest.raises(ValueError):
        with launch(["relative.exe"], tmp_path):
            pass
    with pytest.raises(ValueError):
        with launch([sys.executable], Path("relative")):
            pass
