"""Disposable single-host maintenance fence checks with real OS processes."""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from laew.backup.fence import FENCE_FILENAME, FenceBusyError, FenceConfigurationError, host_fence


@pytest.fixture
def lock_root(tmp_path):
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    (directory / FENCE_FILENAME).touch(mode=0o600)
    return directory


_HOLDER = """
import sys
from laew.backup.fence import host_fence
with host_fence(sys.argv[1], mode=sys.argv[2]):
    print('locked', flush=True)
    sys.stdin.readline()
"""


@pytest.mark.parametrize("mode", ["writer", "maintenance"])
def test_process_compatibility_and_crash_release(lock_root, mode):
    child = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(lock_root), mode],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            assert pool.submit(child.stdout.readline).result(timeout=10).strip() == "locked"
            if mode == "writer":
                with host_fence(lock_root, mode="writer"):
                    pass
            else:
                with pytest.raises(FenceBusyError), host_fence(lock_root, mode="writer"):
                    pass
            start = time.monotonic()
            with pytest.raises(FenceBusyError), host_fence(lock_root, mode="maintenance", timeout=.08):
                pass
            assert .06 <= time.monotonic() - start < 3
        finally:
            child.kill()
            child.wait(timeout=5)
            child.stdin.close()
            child.stdout.close()
    with host_fence(lock_root, mode="maintenance", timeout=1):
        pass


def test_release_on_error_and_stable_identity(lock_root):
    original = (lock_root / FENCE_FILENAME).stat()
    with pytest.raises(RuntimeError), host_fence(lock_root, mode="writer"):
        raise RuntimeError("fixture failure")
    with host_fence(lock_root, mode="maintenance") as path:
        assert os.path.samestat(original, path.stat())
    assert path.read_bytes() == b""


def test_missing_lock_is_never_provisioned(tmp_path):
    directory = tmp_path / "absent"
    with pytest.raises(FenceConfigurationError), host_fence(directory, mode="maintenance"):
        pass
    assert not directory.exists()
    directory.mkdir(mode=0o700)
    with pytest.raises(FenceConfigurationError), host_fence(directory, mode="writer"):
        pass
    assert not list(directory.iterdir())


def test_hard_link_is_rejected(lock_root):
    os.link(lock_root / FENCE_FILENAME, lock_root / "alias")
    with pytest.raises(FenceConfigurationError), host_fence(lock_root, mode="writer"):
        pass


def test_linked_directory_is_rejected(lock_root):
    alias = lock_root.parent / "alias"
    try:
        alias.symlink_to(lock_root, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation unavailable for this fixture.")
    with pytest.raises(FenceConfigurationError), host_fence(alias, mode="maintenance"):
        pass


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junction")
def test_windows_junction_is_rejected(lock_root):
    import _winapi

    alias = lock_root.parent / "junction"
    _winapi.CreateJunction(str(lock_root), str(alias))
    try:
        with pytest.raises(FenceConfigurationError), host_fence(alias, mode="writer"):
            pass
    finally:
        alias.rmdir()
