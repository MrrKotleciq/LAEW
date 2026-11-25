"""Disposable guest-only SCM and Job Object experiment; not a backup controller.

Run elevated: python tests/integration/m18_windows_scm_job_drill.py --run SENTINEL
The sentinel must be a regular file containing exactly LAEW DISPOSABLE GUEST.
Requires this checkout and its existing Windows job fixture module in the guest.
The synthetic service runs as LocalSystem and is deleted on exit. Never run on a
production host. A crash may leave the fixed service requiring manual cleanup.
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

NAME = "LAEW-BW08-Fixture"
PHRASE = "LAEW DISPOSABLE GUEST"


def service(marker):
    from ctypes import wintypes as W
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.integration.m18_windows_job_fixture import launch

    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    CALLBACK = ctypes.WINFUNCTYPE(None, W.DWORD, ctypes.POINTER(W.LPWSTR))
    HANDLER = ctypes.WINFUNCTYPE(None, W.DWORD)

    class STATUS(ctypes.Structure):
        _fields_ = [(name, W.DWORD) for name in ("kind", "state", "controls", "win32", "specific", "checkpoint", "hint")]

    class ENTRY(ctypes.Structure):
        _fields_ = [("name", W.LPWSTR), ("proc", CALLBACK)]

    adv.RegisterServiceCtrlHandlerW.argtypes = [W.LPCWSTR, HANDLER]
    adv.RegisterServiceCtrlHandlerW.restype = W.HANDLE
    adv.SetServiceStatus.argtypes = [W.HANDLE, ctypes.POINTER(STATUS)]
    adv.SetServiceStatus.restype = W.BOOL
    adv.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(ENTRY)]
    adv.StartServiceCtrlDispatcherW.restype = W.BOOL
    stop = threading.Event()
    result = [1]
    refs = []

    @HANDLER
    def handler(code):
        if code in (1, 5):
            stop.set()

    @CALLBACK
    def main(argc, argv):
        handle = adv.RegisterServiceCtrlHandlerW(NAME, handler)
        if not handle:
            return
        def report(state, controls=0, error=0, hint=0):
            status = STATUS(0x10, state, controls, error, 0, 0, hint)
            if not adv.SetServiceStatus(handle, ctypes.byref(status)):
                raise ctypes.WinError(ctypes.get_last_error())
        try:
            report(2, hint=10000)
            child = [sys.executable, str(Path(__file__).resolve()), "--child", marker]
            with launch(child, str(Path(marker).parent)):
                report(4, controls=1 | 4)
                stop.wait()
                report(3, hint=10000)
            report(1)
            result[0] = 0
        except BaseException:
            try:
                report(1, error=1)
            except OSError:
                pass
    refs.extend((handler, main))
    entries = (ENTRY * 2)(ENTRY(NAME, main), ENTRY(None, CALLBACK()))
    if not adv.StartServiceCtrlDispatcherW(entries):
        raise ctypes.WinError(ctypes.get_last_error())
    return result[0]


def run(sentinel):
    from ctypes import wintypes as W
    if (os.name != "nt" or os.environ.get("COMPUTERNAME", "").upper() != "LAEW-BW08-FX"
            or not Path(sentinel).is_file() or Path(sentinel).read_text(encoding="utf-8").strip() != PHRASE):
        raise RuntimeError("Disposable guest sentinel missing or invalid.")
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise RuntimeError("Administrator token required.")
    sc = str(Path(os.environ["SystemRoot"]) / "System32" / "sc.exe")
    def call(*args, check=True):
        return subprocess.run([sc, *args], capture_output=True, text=True, timeout=20, check=check)
    existing = call("query", NAME, check=False)
    if existing.returncode != 1060:
        raise RuntimeError("Fixture service already exists or SCM query failed; no changes made.")
    created = False
    handle = None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
    kernel.OpenProcess.restype = W.HANDLE
    kernel.WaitForSingleObject.argtypes = [W.HANDLE, W.DWORD]
    kernel.WaitForSingleObject.restype = W.DWORD
    kernel.CloseHandle.argtypes = [W.HANDLE]
    # The sentinel resides in fixture-owned storage writable by the administrator and SYSTEM.
    with tempfile.TemporaryDirectory(prefix="laew-bw08-", dir=Path(sentinel).parent) as directory:
        marker = str(Path(directory) / "child.pid")
        command = subprocess.list2cmdline([sys.executable, str(Path(__file__).resolve()), "--service", marker])
        try:
            call("create", NAME, "binPath=", command, "start=", "demand")
            created = True
            call("start", NAME)
            deadline = time.monotonic() + 30
            while not Path(marker).exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            if not Path(marker).exists():
                raise RuntimeError("Service child did not start.")
            handle = kernel.OpenProcess(0x00100000, False, int(Path(marker).read_text()))
            if not handle or kernel.WaitForSingleObject(handle, 0) != 0x102:
                raise RuntimeError("Child was not observed alive.")
            call("config", NAME, "start=", "disabled")
            call("stop", NAME)
            if kernel.WaitForSingleObject(handle, 15000) != 0:
                raise RuntimeError("Child survived service stop.")
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                state = call("query", NAME).stdout
                if "STOPPED" in state:
                    break
                time.sleep(0.2)
            else:
                raise RuntimeError("Service did not reach stopped state.")
            if call("start", NAME, check=False).returncode != 1058:
                raise RuntimeError("SCM did not prove that a disabled service cannot restart.")
            print("PASS: SCM stop closed the job, terminated the observed child and denied restart.")
        finally:
            if handle:
                kernel.CloseHandle(handle)
            if created:
                call("stop", NAME, check=False)
                deletion = call("delete", NAME, check=False)
                if deletion.returncode:
                    raise RuntimeError("Fixture service deletion failed; manual guest cleanup required.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--run":
        run(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--service":
        raise SystemExit(service(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--child":
        marker = Path(sys.argv[2])
        stage = marker.with_suffix(".tmp")
        stage.write_text(str(os.getpid()), encoding="ascii")
        stage.replace(marker)
        time.sleep(120)
    else:
        raise SystemExit("Refusing: pass --run and the disposable guest sentinel.")
