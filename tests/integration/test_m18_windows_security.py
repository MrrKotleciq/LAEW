"""Disposable Windows ACL checks; never touches the installation ACL."""
import os
from pathlib import Path
import subprocess

import pytest

from laew.security.windows_security import (
    WindowsSecurityError, assert_private_owned_path, assert_trusted_owned_path,
    get_current_user_sid, get_path_owner_sid,
)

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows security APIs required')


def icacls(path, *options):
    result = subprocess.run(['icacls', str(path), *options], capture_output=True, text=True)
    if result.returncode:
        pytest.skip('synthetic ACL fixture unavailable')


@pytest.fixture
def private_dir(tmp_path):
    root = tmp_path / 'protected'
    root.mkdir()
    user = get_current_user_sid()
    icacls(root, '/inheritance:r', '/grant:r',
           f'*{user}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F', '*S-1-5-32-544:(OI)(CI)F')
    try:
        yield root, user
    finally:
        # A synthetic deny ACE can block the isolated runner's cleanup.
        subprocess.run(['icacls', str(root), '/remove:d', '*S-1-1-0'],
                       capture_output=True, text=True)


def test_current_identity_and_private_owned_directory(private_dir):
    path, user = private_dir
    assert user.startswith('S-1-')
    assert get_path_owner_sid(path) == user
    assert_private_owned_path(path, user)


def test_wrong_owner_and_invalid_expected_sid_are_sanitized(private_dir):
    path, user = private_dir
    for expected in ('S-1-5-18', 'not-a-sid-secret'):
        with pytest.raises(WindowsSecurityError) as error:
            assert_private_owned_path(path, expected)
        assert str(path) not in str(error.value)
        assert expected not in str(error.value)


def test_foreign_allow_is_rejected(private_dir):
    path, user = private_dir
    icacls(path, '/grant', '*S-1-1-0:(R)')
    with pytest.raises(WindowsSecurityError, match='untrusted access grant'):
        assert_private_owned_path(path, user)


def test_inherit_only_foreign_allow_is_rejected(private_dir):
    path, user = private_dir
    icacls(path, '/grant', '*S-1-1-0:(OI)(CI)(IO)(R)')
    with pytest.raises(WindowsSecurityError, match='untrusted access grant'):
        assert_private_owned_path(path, user)


def test_deny_ace_is_not_a_grant(private_dir):
    path, user = private_dir
    icacls(path, '/deny', '*S-1-1-0:(W)')
    assert_private_owned_path(path, user)


def test_reparse_point_is_rejected(private_dir, tmp_path):
    path, user = private_dir
    link = tmp_path / 'junction-link'
    try:
        link.symlink_to(path, target_is_directory=True)
    except OSError:
        pytest.skip('symlink creation unavailable')
    with pytest.raises(WindowsSecurityError, match='reparse'):
        assert_private_owned_path(link, user)
    with pytest.raises(WindowsSecurityError, match='reparse'):
        get_path_owner_sid(link)


def test_private_inherited_file(private_dir):
    root, user = private_dir
    file = root / 'trace.jsonl'
    file.write_text('synthetic')
    assert get_path_owner_sid(file) == user
    assert_private_owned_path(file, user)


def test_null_dacl_is_rejected(private_dir):
    import ctypes
    from ctypes import wintypes
    path, user = private_dir
    adv = ctypes.WinDLL('advapi32', use_last_error=True)
    adv.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
                                          wintypes.LPVOID, wintypes.LPVOID,
                                          wintypes.LPVOID, wintypes.LPVOID]
    adv.SetNamedSecurityInfoW.restype = wintypes.DWORD
    if adv.SetNamedSecurityInfoW(str(path), 1, 0x4, None, None, None, None):
        pytest.skip('could not create synthetic null DACL')
    try:
        with pytest.raises(WindowsSecurityError, match='null DACL'):
            assert_private_owned_path(path, user)
    finally:
        icacls(path, '/reset')


def test_unsupported_ace_type_is_rejected(private_dir, monkeypatch):
    import ctypes
    import laew.security.windows_security as security
    path, user = private_dir
    original = security._apis
    adv, kernel = original()
    entry = ctypes.create_string_buffer(bytes([5, 0, 16, 0]) + bytes(12))
    class AdvProxy:
        def __getattr__(self, name):
            return getattr(adv, name)
        def GetAce(self, acl, index, output):
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(entry)
            return True
    monkeypatch.setattr(security, '_apis', lambda: (AdvProxy(), kernel))
    with pytest.raises(WindowsSecurityError, match='unsupported DACL entry'):
        assert_private_owned_path(path, user)


def test_trusted_toolchain_allows_foreign_read_execute_but_private_does_not(private_dir):
    path, user = private_dir
    icacls(path, '/grant', '*S-1-1-0:(RX)')
    assert_trusted_owned_path(path, user)
    with pytest.raises(WindowsSecurityError, match='untrusted access grant'):
        assert_private_owned_path(path, user)


@pytest.mark.parametrize('right', ['W', 'DC', 'D', 'WDAC', 'WO'])
def test_trusted_toolchain_rejects_foreign_mutation(private_dir, right):
    path, user = private_dir
    icacls(path, '/grant', f'*S-1-1-0:({right})')
    with pytest.raises(WindowsSecurityError, match='untrusted access grant'):
        assert_trusted_owned_path(path, user)
