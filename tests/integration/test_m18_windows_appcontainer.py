"""Native Windows profile checks on unique, disposable synthetic state."""

import ctypes
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

import pytest

from laew.security import windows_appcontainer as ac


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows AppContainer")


@pytest.fixture
def app_fixture(tmp_path):
    from ctypes import wintypes as W

    create = ac._api(ac._U, "CreateAppContainerProfile", W.LONG, W.LPCWSTR, W.LPCWSTR, W.LPCWSTR,
                     ac._P, W.DWORD, ctypes.POINTER(ac._P))
    delete = ac._api(ac._U, "DeleteAppContainerProfile", W.LONG, W.LPCWSTR)
    name = "LAEW.Fixture." + uuid4().hex
    sid = ac._P()
    result = create(name, name, "Disposable LAEW integration test", None, 0, ctypes.byref(sid))
    assert result == 0, f"Cannot provision synthetic AppContainer (HRESULT {result & 0xffffffff:#x})"
    windows = Path(os.environ["SystemRoot"])
    project = tmp_path / "project"
    private = tmp_path / "operator"
    try:
        label = W.LPWSTR()
        ac._required(ac._sid_string(sid, ctypes.byref(label)))
        try:
            account = "*" + label.value
        finally:
            ac._free(ctypes.cast(label, ac._P))
        project.mkdir()
        private.mkdir()
        (project / "allowed.txt").write_text("project fixture", encoding="ascii")
        marker = private / "private.txt"
        marker.write_text("private fixture", encoding="ascii")
        acl = str(windows / "System32" / "icacls.exe")
        for path, arguments in (
            (project, ["/grant", account + ":(OI)(CI)M"]),
            (project, ["/setintegritylevel", "(OI)(CI)L"]),
            (private, ["/deny", account + ":(OI)(CI)F"]),
        ):
            subprocess.run([acl, str(path), *arguments], check=True, capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
        env = {key: os.environ[key] for key in ("SYSTEMROOT", "LOCALAPPDATA", "TEMP", "TMP")}
        yield name, project, marker, str(windows / "System32" / "cmd.exe"), env
    finally:
        ac._free_sid(sid)
        assert delete(name) == 0, "Synthetic Windows profile cleanup failed."


def test_direct_and_grandchild_private_denial_and_project_access(app_fixture, monkeypatch):
    profile, project, marker, cmd, env = app_fixture
    monkeypatch.setenv("LAEW_FIXTURE_PRIVATE_ENV", "parent-only")
    # Each script checks its own positive and negative access. Only status is
    # emitted. A missing project grant fails the positive control.
    child = r"""@echo off
type allowed.txt >nul || exit /b 21
type ..\operator\private.txt >nul 2>nul && exit /b 22
echo projected>grand-output.txt || exit /b 23
if defined LAEW_FIXTURE_PRIVATE_ENV exit /b 24
echo GRAND_OK
exit /b 0
"""
    direct = r"""@echo off
type allowed.txt >nul || exit /b 11
type ..\operator\private.txt >nul 2>nul && exit /b 12
echo bad>..\operator\new.txt 2>nul
if exist ..\operator\new.txt exit /b 13
echo projected>direct-output.txt || exit /b 14
echo DIRECT_OK
"%SystemRoot%\System32\cmd.exe" /d /c child.cmd
exit /b %errorlevel%
"""
    for filename, script in (("direct.cmd", direct), ("child.cmd", child)):
        (project / filename).write_text(script, encoding="ascii")
    run = ac.run_appcontainer([cmd, "/d", "/c", "direct.cmd"], profile_name=profile, cwd=project, env=env, timeout=10)
    assert run.returncode == 0, (run.stdout, run.stderr)
    assert run.stdout.splitlines() == ["DIRECT_OK", "GRAND_OK"]
    assert all((project / name).is_file() for name in ("direct-output.txt", "grand-output.txt"))
    assert not (marker.parent / "new.txt").exists()
    assert marker.read_text(encoding="ascii") == "private fixture"


def test_time_and_output_limits(app_fixture):
    profile, project, _, cmd, env = app_fixture
    kwargs = dict(profile_name=profile, cwd=project, env=env)
    (project / "busy.cmd").write_text("@echo off\n:again\ngoto again\n", encoding="ascii")
    with pytest.raises(subprocess.TimeoutExpired):
        ac.run_appcontainer([cmd, "/d", "/c", "busy.cmd"], timeout=.15, **kwargs)
    with pytest.raises(ac.OutputLimitExceeded):
        ac.run_appcontainer([cmd, "/d", "/c", "echo long-output"], max_output_bytes=3, **kwargs)
    finished = ac.run_appcontainer([cmd, "/d", "/c", "echo ok"], text=False, **kwargs)
    assert finished.stdout.strip() == b"ok"


def test_backup_projection_read_only_for_native_restricted_consumer(app_fixture, monkeypatch):
    from ctypes import wintypes as W
    from datetime import datetime, timezone
    import json

    from laew.backup.controls import workbench_view
    from laew.security.windows_security import get_current_user_sid

    profile, project, marker, cmd, env = app_fixture
    sid = ac._P()
    assert ac._derive(profile, ctypes.byref(sid)) == 0
    try:
        label = W.LPWSTR()
        ac._required(ac._sid_string(sid, ctypes.byref(label)))
        try:
            reader = "*" + label.value
        finally:
            ac._free(ctypes.cast(label, ac._P))
    finally:
        ac._free_sid(sid)
    owner = get_current_user_sid()
    projection = project.parent / "projection"
    projection.mkdir()
    acl = Path(env["SYSTEMROOT"]) / "System32/icacls.exe"
    for operations in (
        ("/inheritance:r", "/grant:r", f"*{owner}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F",
         "*S-1-5-32-544:(OI)(CI)F", reader + ":(OI)(CI)RX"),
        ("/setintegritylevel", "(OI)(CI)L"),
    ):
        subprocess.run([str(acl), str(projection), *operations], check=True, capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    view = projection / "backup-settings.json"
    original = json.dumps(dict(state="enabled", revision="a" * 64, directories=[], keys=[], local="validated",
                               local_backup="ok", connection="connected", remote="verified",
                               observed_at=datetime.now(timezone.utc).isoformat())).encode("ascii")
    view.write_bytes(original)
    # This fixture checks real reader access to the projection, with temp
    # ancestry that is unsuitable for deployment.
    monkeypatch.setattr("laew.backup.health._check_ancestry", lambda *_: None)
    assert workbench_view(view, owner)["remote"] == "verified"
    (project / "acl.cmd").write_text(r"""@echo off
type ..\projection\backup-settings.json >nul || exit /b 11
type ..\operator\private.txt >nul 2>nul && exit /b 12
echo bad>>..\projection\backup-settings.json 2>nul && exit /b 13
echo bad>..\projection\new.json 2>nul && exit /b 14
del ..\projection\backup-settings.json >nul 2>nul
if not exist ..\projection\backup-settings.json exit /b 15
move ..\projection ..\replaced >nul 2>nul && exit /b 16
exit /b 0
""", encoding="ascii")
    result = ac.run_appcontainer([cmd, "/d", "/c", "acl.cmd"], profile_name=profile, cwd=project, env=env, timeout=10)
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert view.read_bytes() == original and not (projection / "new.json").exists()
    assert marker.is_file() and not projection.with_name("replaced").exists()


def test_profile_git_environment_uses_scratch_and_fixed_settings(app_fixture):
    profile, project, _, cmd, env = app_fixture
    from types import SimpleNamespace
    from laew.security.protected_profile import _environment

    scratch = project / "scratch"
    scratch.mkdir()
    env = _environment(SimpleNamespace(scratch=scratch), {"cmd": Path(cmd)})
    run = ac.run_appcontainer([cmd, "/d", "/c", "echo %GIT_CONFIG_NOSYSTEM% %GIT_CONFIG_GLOBAL% %GIT_TERMINAL_PROMPT%"],
                              profile_name=profile, cwd=project, env=env)
    assert run.returncode == 0 and run.stdout.strip() == "1 nul 0"
    for key, value in {"HOME": str(project), "GIT_CONFIG_GLOBAL": "untrusted.gitconfig",
                       "GIT_CONFIG_NOSYSTEM": "0", "GIT_TERMINAL_PROMPT": "1"}.items():
        with pytest.raises(ValueError):
            ac.run_appcontainer([cmd, "/d", "/c", "echo bad"], profile_name=profile, cwd=project,
                                env=env | {key: value})


def test_absent_profile_or_unapproved_environment_never_runs(tmp_path):
    windows = Path(os.environ["SystemRoot"])
    argv = [str(windows / "System32" / "cmd.exe"), "/d", "/c", "echo BAD>launched.txt"]
    options = dict(profile_name="LAEW.Missing." + uuid4().hex, cwd=tmp_path)
    with pytest.raises(ac.IsolationUnavailable):
        ac.run_appcontainer(argv, env={"SYSTEMROOT": str(windows)}, **options)
    with pytest.raises(ValueError):
        ac.run_appcontainer(argv, env={"SYSTEMROOT": str(windows), "API_KEY": "synthetic"}, **options)
    assert not (tmp_path / "launched.txt").exists()


def test_unlisted_inheritable_handle_absent_from_suspended_child(app_fixture, monkeypatch):
    import msvcrt
    from ctypes import wintypes as W

    profile, project, marker, cmd, env = app_fixture
    duplicate = ac._api(ac._K, "DuplicateHandle", W.BOOL, W.HANDLE, W.HANDLE, W.HANDLE,
                        ctypes.POINTER(W.HANDLE), W.DWORD, W.BOOL, W.DWORD)
    same = ac._api(ctypes.WinDLL("KernelBase"), "CompareObjectHandles", W.BOOL, W.HANDLE, W.HANDLE)
    original_verify = ac._verify_token
    checked = []
    with marker.open("rb") as fixture_handle:
        fd = fixture_handle.fileno()
        os.set_inheritable(fd, True)
        handle = msvcrt.get_osfhandle(fd)

        def check(process, sid):
            original_verify(process, sid)
            clone = W.HANDLE()
            if duplicate(process, handle, -1, ctypes.byref(clone), 0, False, 2):
                try:
                    assert not same(handle, clone)
                finally:
                    ac._close(clone)
            else:
                assert ctypes.get_last_error() == 6  # ERROR_INVALID_HANDLE
            checked.append(True)

        monkeypatch.setattr(ac, "_verify_token", check)
        run = ac.run_appcontainer([cmd, "/d", "/c", "echo ok"], profile_name=profile, cwd=project, env=env)
    assert checked == [True] and run.returncode == 0


def test_native_job_terminates_live_grandchild_on_timeout(app_fixture, monkeypatch):
    from ctypes import wintypes as W

    profile, project, _, cmd, env = app_fixture
    (project / "busy.cmd").write_text("@echo off\n:again\ngoto again\n", encoding="ascii")
    (project / "parent.cmd").write_text('@echo off\n"%SystemRoot%\\System32\\cmd.exe" /d /c busy.cmd\n',
                                        encoding="ascii")
    query = ac._api(ac._K, "QueryInformationJobObject", W.BOOL, W.HANDLE, W.INT, ac._P, W.DWORD, ac._DWORD_P)
    open_process = ac._api(ac._K, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)

    class Pids(ctypes.Structure):
        _fields_ = [("count", W.DWORD), ("listed", W.DWORD), ("pids", ac._SIZE * 8)]

    original_collect = ac._collect
    handles = []

    def observe(process, job, *args):
        deadline = time.monotonic() + 3
        pids = Pids()
        while time.monotonic() < deadline:
            ac._required(query(job, 3, ctypes.byref(pids), ctypes.sizeof(pids), None))
            if pids.listed >= 2:
                break
            time.sleep(.01)
        assert pids.listed == 2
        for pid in pids.pids[:pids.listed]:
            handles.append(ac._required(open_process(0x100000, False, pid)))  # SYNCHRONIZE
        return original_collect(process, job, *args)

    monkeypatch.setattr(ac, "_collect", observe)
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            ac.run_appcontainer([cmd, "/d", "/c", "parent.cmd"], profile_name=profile, cwd=project,
                                env=env, timeout=.05)
        assert len(handles) == 2
        assert all(ac._wait(handle, 2000) == 0 for handle in handles)
    finally:
        for handle in handles:
            ac._close(handle)
