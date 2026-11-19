"""Read-only, conservative Windows ownership and DACL inspection.

Both checks reject unknown ACE layouts. The private check rejects any allow
ACE for identities other than the expected user, LocalSystem, or Builtin
Administrators. The trusted-toolchain check permits other principals only
read and execute rights. Deny ACEs do not grant access and are not treated as
allow ACEs. Inherited ACEs are checked like explicit ACEs; inherit-only allows
are also checked conservatively.
This is not an effective-access calculation, a filesystem isolation proof, or
an atomic guarantee against replacement between inspection and use. Callers
must secure and separately verify parent directories and the execution boundary.
No ACLs or file contents are modified or read here.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
from ctypes import wintypes


class WindowsSecurityError(RuntimeError):
    """The requested security properties could not be established."""


_SID = re.compile(r"S-1-(?:[0-9]+-)*[0-9]+\Z")
_SYSTEM = "S-1-5-18"
_ADMINS = "S-1-5-32-544"
_REPARSE = 0x400
# GENERIC_READ, GENERIC_EXECUTE, READ_CONTROL, SYNCHRONIZE and the file or
# directory-specific read/list, read-EA, execute/traverse and read-attributes
# bits. Every other bit, including DELETE_CHILD, is forbidden for outsiders.
_READ_EXECUTE_MASK = 0xA01200A9


def _apis():
    if os.name != "nt":
        raise WindowsSecurityError("Windows security inspection is unavailable")
    try:
        adv = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
        adv.OpenProcessToken.restype = wintypes.BOOL
        adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        adv.GetTokenInformation.restype = wintypes.BOOL
        adv.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
            ctypes.POINTER(wintypes.LPVOID), ctypes.c_void_p, ctypes.POINTER(wintypes.LPVOID),
            ctypes.c_void_p, ctypes.POINTER(wintypes.LPVOID)]
        adv.GetNamedSecurityInfoW.restype = wintypes.DWORD
        adv.ConvertSidToStringSidW.argtypes = [wintypes.LPVOID, ctypes.POINTER(wintypes.LPWSTR)]
        adv.ConvertSidToStringSidW.restype = wintypes.BOOL
        adv.IsValidSid.argtypes = [wintypes.LPVOID]
        adv.IsValidSid.restype = wintypes.BOOL
        adv.IsValidAcl.argtypes = [wintypes.LPVOID]
        adv.IsValidAcl.restype = wintypes.BOOL
        adv.GetAclInformation.argtypes = [wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.c_int]
        adv.GetAclInformation.restype = wintypes.BOOL
        adv.GetAce.argtypes = [wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.LPVOID)]
        adv.GetAce.restype = wintypes.BOOL
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.LocalFree.argtypes = [wintypes.LPVOID]
        kernel.LocalFree.restype = wintypes.LPVOID
        return adv, kernel
    except (OSError, AttributeError):
        raise WindowsSecurityError("Windows security inspection is unavailable") from None


def _sid_string(adv, kernel, sid):
    if not sid or not adv.IsValidSid(sid):
        raise WindowsSecurityError("invalid security descriptor")
    text = wintypes.LPWSTR()
    if not adv.ConvertSidToStringSidW(sid, ctypes.byref(text)):
        raise WindowsSecurityError("security identity unavailable")
    try:
        return text.value
    finally:
        kernel.LocalFree(ctypes.cast(text, wintypes.LPVOID))


def get_current_user_sid() -> str:
    """Return the current process token user SID; never an account name."""
    adv, kernel = _apis()
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008, ctypes.byref(token)):
        raise WindowsSecurityError("process identity unavailable")
    try:
        size = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))
        if not 0 < size.value <= 65536:
            raise WindowsSecurityError("process identity unavailable")
        buf = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buf, size, ctypes.byref(size)):
            raise WindowsSecurityError("process identity unavailable")
        sid = ctypes.cast(buf, ctypes.POINTER(wintypes.LPVOID)).contents
        return _sid_string(adv, kernel, sid)
    finally:
        kernel.CloseHandle(token)


def _checked_path(path):
    try:
        path = Path(path)
        if not path.is_absolute() or ".." in path.parts:
            raise WindowsSecurityError("invalid security path")
        for part in reversed((path, *path.parents)):
            info = part.lstat()
            if getattr(info, "st_file_attributes", 0) & _REPARSE:
                raise WindowsSecurityError("reparse paths are unsupported")
        return path
    except (OSError, TypeError, ValueError):
        raise WindowsSecurityError("security path unavailable") from None


def get_path_owner_sid(path) -> str:
    """Return the owner SID of an existing non-reparse path, without changes."""
    adv, kernel = _apis()
    checked = _checked_path(path)
    owner, descriptor = wintypes.LPVOID(), wintypes.LPVOID()
    result = adv.GetNamedSecurityInfoW(str(checked), 1, 0x1, ctypes.byref(owner),
                                       None, None, None, ctypes.byref(descriptor))
    if result != 0 or not descriptor:
        raise WindowsSecurityError("security descriptor unavailable")
    try:
        return _sid_string(adv, kernel, owner)
    finally:
        kernel.LocalFree(descriptor)


def assert_private_owned_path(path, expected_sid: str) -> None:
    """Require an owned path whose DACL has only trusted allow trustees.

    The caller must provide the expected canonical SID. Missing/null DACLs,
    reparse points, unsupported ACE forms and uncertain results fail closed.
    A valid but empty DACL passes this confidentiality check, even if access
    by the expected user would be denied. Parent ACLs and races are not proven.
    """
    _assert_owned_path(path, expected_sid, allow_read_execute=False)


def assert_trusted_owned_path(path, expected_sid: str) -> None:
    """Allow outsiders only read/execute grants on an owned toolchain path.

    The same conservative ACE, inheritance and reparse restrictions as the
    private check apply. This is not an effective access or race-free proof.
    """
    _assert_owned_path(path, expected_sid, allow_read_execute=True)


def _assert_owned_path(path, expected_sid, *, allow_read_execute):
    if not isinstance(expected_sid, str) or not _SID.fullmatch(expected_sid):
        raise WindowsSecurityError("invalid expected security identity")
    adv, kernel = _apis()
    checked = _checked_path(path)
    owner, dacl, descriptor = wintypes.LPVOID(), wintypes.LPVOID(), wintypes.LPVOID()
    # OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION; SE_FILE_OBJECT.
    result = adv.GetNamedSecurityInfoW(str(checked), 1, 0x5, ctypes.byref(owner), None,
                                       ctypes.byref(dacl), None, ctypes.byref(descriptor))
    if result != 0 or not descriptor:
        raise WindowsSecurityError("security descriptor unavailable")
    try:
        if _sid_string(adv, kernel, owner) != expected_sid:
            raise WindowsSecurityError("security owner mismatch")
        if not dacl or not adv.IsValidAcl(dacl):
            raise WindowsSecurityError("invalid or null DACL")
        class AclSize(ctypes.Structure):
            _fields_ = [("ace_count", wintypes.DWORD), ("bytes_in_use", wintypes.DWORD),
                        ("bytes_free", wintypes.DWORD)]
        info = AclSize()
        if not adv.GetAclInformation(dacl, ctypes.byref(info), ctypes.sizeof(info), 2) or info.ace_count > 65535:
            raise WindowsSecurityError("DACL inspection failed")
        trusted = {expected_sid, _SYSTEM, _ADMINS}
        for index in range(info.ace_count):
            ace = wintypes.LPVOID()
            if not adv.GetAce(dacl, index, ctypes.byref(ace)) or not ace:
                raise WindowsSecurityError("DACL inspection failed")
            header = ctypes.string_at(ace, 4)
            ace_type, flags = header[0], header[1]
            size = int.from_bytes(header[2:4], "little")
            if ace_type not in (0, 1) or flags & ~0x1f or size < 16:
                raise WindowsSecurityError("unsupported DACL entry")
            sid = wintypes.LPVOID(ace.value + 8)
            identity = _sid_string(adv, kernel, sid)
            if ace_type == 0 and identity not in trusted:
                mask = int.from_bytes(ctypes.string_at(ace.value + 4, 4), "little")
                if not allow_read_execute or mask & ~_READ_EXECUTE_MASK:
                    raise WindowsSecurityError("untrusted access grant")
    finally:
        kernel.LocalFree(descriptor)
