"""Windows child process launcher for an already-provisioned protected profile.

The operator separately verifies the installation identity, executable tree,
project permissions, profile ownership, and access denied to private roots.
No API here provisions a profile, changes ACLs, or launches unrestricted.
"""

from contextlib import ExitStack, contextmanager
import ctypes
import locale
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time


class IsolationUnavailable(RuntimeError):
    """The protected launch could not establish the requested isolation."""


class OutputLimitExceeded(RuntimeError):
    """The command exceeded its combined stdout and stderr budget."""


if os.name == "nt":
    import _winapi
    from ctypes import wintypes as W
    import msvcrt
    import winreg

    _K = ctypes.WinDLL("kernel32", use_last_error=True)
    _A = ctypes.WinDLL("advapi32", use_last_error=True)
    _U = ctypes.WinDLL("userenv", use_last_error=True)
    _P = ctypes.c_void_p
    _SIZE = ctypes.c_size_t
    _DWORD_P = ctypes.POINTER(W.DWORD)

    class _Startup(ctypes.Structure):
        _fields_ = [
            ("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
            ("x", W.DWORD), ("y", W.DWORD), ("xsize", W.DWORD), ("ysize", W.DWORD),
            ("xchars", W.DWORD), ("ychars", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
            ("show", W.WORD), ("reserved_size", W.WORD), ("reserved2", _P),
            ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE),
        ]

    class _StartupEx(ctypes.Structure):
        _fields_ = [("startup", _Startup), ("attributes", _P)]

    class _Process(ctypes.Structure):
        _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]

    class _Capabilities(ctypes.Structure):
        _fields_ = [("sid", _P), ("capabilities", _P), ("count", W.DWORD), ("reserved", W.DWORD)]

    class _BasicLimit(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", W.DWORD), ("min_working_set", _SIZE), ("max_working_set", _SIZE),
                    ("max_processes", W.DWORD), ("affinity", _SIZE), ("priority", W.DWORD),
                    ("scheduling", W.DWORD)]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [("basic", _BasicLimit), ("io_counters", ctypes.c_ulonglong * 6),
                    ("process_memory", _SIZE), ("job_memory", _SIZE),
                    ("peak_process_memory", _SIZE), ("peak_job_memory", _SIZE)]

    def _api(dll, name, result, *arguments):
        fn = getattr(dll, name)
        fn.restype, fn.argtypes = result, arguments
        return fn

    _derive = _api(_U, "DeriveAppContainerSidFromAppContainerName", W.LONG, W.LPCWSTR, ctypes.POINTER(_P))
    _free_sid = _api(_A, "FreeSid", _P, _P)
    _sid_string = _api(_A, "ConvertSidToStringSidW", W.BOOL, _P, ctypes.POINTER(W.LPWSTR))
    _free = _api(_K, "LocalFree", _P, _P)
    _job = _api(_K, "CreateJobObjectW", W.HANDLE, _P, W.LPCWSTR)
    _job_info = _api(_K, "SetInformationJobObject", W.BOOL, W.HANDLE, W.INT, _P, W.DWORD)
    _end_job = _api(_K, "TerminateJobObject", W.BOOL, W.HANDLE, W.UINT)
    _close = _api(_K, "CloseHandle", W.BOOL, W.HANDLE)
    _init_attrs = _api(_K, "InitializeProcThreadAttributeList", W.BOOL, _P, W.DWORD, W.DWORD,
                       ctypes.POINTER(_SIZE))
    _delete_attrs = _api(_K, "DeleteProcThreadAttributeList", None, _P)
    _update_attr = _api(_K, "UpdateProcThreadAttribute", W.BOOL, _P, W.DWORD, _SIZE, _P, _SIZE, _P, _P)
    _create = _api(_K, "CreateProcessW", W.BOOL, W.LPCWSTR, W.LPWSTR, _P, _P, W.BOOL, W.DWORD,
                   _P, W.LPCWSTR, ctypes.POINTER(_StartupEx), ctypes.POINTER(_Process))
    _resume = _api(_K, "ResumeThread", W.DWORD, W.HANDLE)
    _wait = _api(_K, "WaitForSingleObject", W.DWORD, W.HANDLE, W.DWORD)
    _exit_code = _api(_K, "GetExitCodeProcess", W.BOOL, W.HANDLE, _DWORD_P)
    _open_token = _api(_A, "OpenProcessToken", W.BOOL, W.HANDLE, W.DWORD, ctypes.POINTER(W.HANDLE))
    _token_info = _api(_A, "GetTokenInformation", W.BOOL, W.HANDLE, W.INT, _P, W.DWORD, _DWORD_P)
    _equal_sid = _api(_A, "EqualSid", W.BOOL, _P, _P)


def _required(result):
    if not result:
        raise IsolationUnavailable("Windows protected launch failed.") from ctypes.WinError(ctypes.get_last_error())
    return result


def _profile(name, stack):
    sid = _P()
    if _derive(name, ctypes.byref(sid)) != 0:
        raise IsolationUnavailable("Cannot resolve Windows isolation profile.")
    stack.callback(_free_sid, sid)
    label = W.LPWSTR()
    _required(_sid_string(sid, ctypes.byref(label)))
    stack.callback(_free, ctypes.cast(label, _P))
    # Derivation alone succeeds for arbitrary names. Require an existing
    # per-account profile mapping and verify its moniker before process creation.
    mapping = r"Software\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppContainer\Mappings"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, mapping + "\\" + label.value) as key:
            registered, kind = winreg.QueryValueEx(key, "Moniker")
    except OSError as exc:
        raise IsolationUnavailable("A provisioned Windows isolation profile is required.") from exc
    if kind != winreg.REG_SZ or registered.casefold() != name.casefold():
        raise IsolationUnavailable("Windows isolation profile identity mismatch.")
    return sid


def _token_value(token, field):
    needed = W.DWORD()
    _token_info(token, field, None, 0, ctypes.byref(needed))
    if ctypes.get_last_error() != 122 or not 0 < needed.value <= 65536:
        raise IsolationUnavailable("Unable to inspect protected child token.")
    buffer = ctypes.create_string_buffer(needed.value)
    _required(_token_info(token, field, buffer, needed, ctypes.byref(needed)))
    return buffer


def _verify_token(process, sid):
    token = W.HANDLE()
    _required(_open_token(process, 8, ctypes.byref(token)))  # TOKEN_QUERY
    try:
        is_container = W.DWORD.from_buffer(_token_value(token, 29)).value
        capabilities = W.DWORD.from_buffer(_token_value(token, 30)).value
        sid_buffer = _token_value(token, 31)
        child_sid = _P.from_buffer(sid_buffer).value
        if is_container != 1 or capabilities != 0 or not child_sid or not _equal_sid(child_sid, sid):
            raise IsolationUnavailable("Child token does not match the requested Windows isolation profile.")
    finally:
        _close(token)


@contextmanager
def _pipes():
    with ExitStack() as keep, ExitStack() as inherited:
        stdin, unused = os.pipe()
        os.close(unused)
        inherited.callback(os.close, stdin)
        readers, child = [], [stdin]
        for _ in range(2):
            read, write = os.pipe()
            keep.callback(os.close, read)
            inherited.callback(os.close, write)
            readers.append(read)
            child.append(write)
        for fd in child:
            os.set_inheritable(fd, True)
        yield readers, [msvcrt.get_osfhandle(fd) for fd in child], inherited


def _start(argv, cwd, block, profile_name, handles, stack):
    sid = _profile(profile_name, stack)
    job = _required(_job(None, None))
    stack.callback(_close, job)
    limits = _ExtendedLimit()
    limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; breakaway is disabled.
    _required(_job_info(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
    size = _SIZE()
    _init_attrs(None, 3, 0, ctypes.byref(size))
    if ctypes.get_last_error() != 122 or not 0 < size.value <= 65536:
        raise IsolationUnavailable("Windows extended process attributes are unavailable.")
    attrs = ctypes.create_string_buffer(size.value)
    _required(_init_attrs(attrs, 3, 0, ctypes.byref(size)))
    stack.callback(_delete_attrs, attrs)
    security = _Capabilities(sid, None, 0, 0)
    handle_list = (W.HANDLE * 3)(*handles)
    job_list = (W.HANDLE * 1)(job)
    for kind, value in ((0x20009, security), (0x20002, handle_list), (0x2000D, job_list)):
        _required(_update_attr(attrs, 0, kind, ctypes.byref(value), ctypes.sizeof(value), None, None))
    startup = _StartupEx()
    startup.startup.cb = ctypes.sizeof(startup)
    startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
    startup.startup.stdin, startup.startup.stdout, startup.startup.stderr = handles
    startup.attributes = ctypes.cast(attrs, _P)
    process = _Process()
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
    # Extended startup attributes, Unicode env, no console window, suspended.
    _required(_create(argv[0], command, None, None, True, 0x00080000 | 0x400 | 0x08000000 | 4,
                      block, cwd, ctypes.byref(startup), ctypes.byref(process)))
    stack.callback(_close, process.thread)
    stack.callback(_close, process.process)
    _verify_token(process.process, sid)
    if _resume(process.thread) != 1:
        raise IsolationUnavailable("Windows could not resume the verified process.")
    return process.process, job


def _available(fd):
    try:
        amount, _ = _winapi.PeekNamedPipe(msvcrt.get_osfhandle(fd), 0)
        return amount
    except OSError as exc:
        if exc.winerror in (109, 232):  # All write handles closed.
            return 0
        raise


def _collect(process, job, readers, argv, timeout, maximum):
    deadline = time.monotonic() + timeout
    data = [bytearray(), bytearray()]
    done = False
    while True:
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(argv, timeout)
        received = False
        for fd, output in zip(readers, data):
            available = _available(fd)
            if available:
                if available + sum(map(len, data)) > maximum:
                    raise OutputLimitExceeded("Protected process output limit exceeded.")
                output.extend(os.read(fd, min(available, 65536)))
                received = True
        if done and not received:
            break
        if not done:
            result = _wait(process, 0 if received else 10)
            if result == 0:
                _required(_end_job(job, 1))  # Close the lifetime of background descendants too.
                done = True
            elif result != 258:  # WAIT_TIMEOUT
                raise IsolationUnavailable("Cannot wait for protected process.")
    code = W.DWORD()
    _required(_exit_code(process, ctypes.byref(code)))
    return code.value, bytes(data[0]), bytes(data[1])


def _local_path(value, directory):
    path = Path(value)
    if not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive) or ".." in path.parts:
        raise IsolationUnavailable("Protected process requires a fixed absolute local path.")
    if any(":" in part or part.endswith((" ", ".")) for part in path.parts[1:]):
        raise IsolationUnavailable("Unsupported protected process path syntax.")
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise IsolationUnavailable("Reparse points are unsupported in protected launch paths.")
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise IsolationUnavailable("Invalid protected launch path.")
    return str(path)


def run_appcontainer(argv, *, profile_name, cwd, env, timeout=30.0, text=True, max_output_bytes=1048576):
    """Run an absolute trusted executable within an existing no-capabilities profile.

    All three standard streams are private pipes. Stdin is EOF. The caller
    supplies trusted values for the allowed environment keys. Result stdout
    and stderr are captured and combined output size is bounded.
    """
    if os.name != "nt":
        raise IsolationUnavailable("Windows AppContainer is unavailable on this host.")
    if not isinstance(profile_name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", profile_name):
        raise ValueError("Invalid protected profile name.")
    if (not isinstance(argv, (list, tuple)) or not argv or
            not all(isinstance(arg, str) and "\x00" not in arg for arg in argv)):
        raise ValueError("Invalid protected process arguments.")
    if not math.isfinite(timeout) or not 0 < timeout <= 3600 or type(max_output_bytes) is not int or not 0 < max_output_bytes <= 64 << 20:
        raise ValueError("Invalid protected process budget.")
    exe = _local_path(argv[0], False)
    cwd = _local_path(cwd, True)
    if not exe.lower().endswith(".exe"):
        raise IsolationUnavailable("Protected launch requires a native executable.")
    git_settings = {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    allowed = {"SYSTEMROOT", "WINDIR", "LOCALAPPDATA", "PATH", "TEMP", "TMP", "HOME", "LANG", "LC_ALL", *git_settings}
    normalized = {}
    for key, value in env.items():
        if (not isinstance(key, str) or key.upper() not in allowed or key.upper() in normalized
                or not isinstance(value, str) or "\x00" in value):
            raise ValueError("Unapproved protected process environment.")
        normalized[key.upper()] = value
    if any(key in normalized and normalized[key] != value for key, value in git_settings.items()):
        raise ValueError("Unapproved protected Git setting.")
    if "HOME" in normalized:
        scratch = _local_path(normalized["HOME"], True)
        if not all(os.path.normcase(normalized.get(key, "")) == os.path.normcase(scratch) for key in ("TEMP", "TMP")):
            raise ValueError("Protected HOME must use the approved scratch directory.")
    if "SYSTEMROOT" not in normalized:
        raise ValueError("Protected environment requires SystemRoot.")
    block = ctypes.create_unicode_buffer("\x00".join(f"{key}={value}" for key, value in sorted(normalized.items())) + "\x00")
    with ExitStack() as resources, _pipes() as (readers, handles, inherited):
        process, job = _start([exe, *argv[1:]], cwd, block, profile_name, handles, resources)
        inherited.close()
        code, stdout, stderr = _collect(process, job, readers, argv, timeout, max_output_bytes)
    if text:
        encoding = "utf-8" if sys.flags.utf8_mode else locale.getencoding()
        stdout, stderr = (data.decode(encoding, errors="replace").replace("\r\n", "\n") for data in (stdout, stderr))
    return subprocess.CompletedProcess(argv, code, stdout, stderr)
