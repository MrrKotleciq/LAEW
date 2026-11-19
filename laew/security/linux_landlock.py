"""Experimental fixture-only Landlock subprocess launcher.

Requires Linux x86-64/aarch64, Landlock ABI 9 and trusted separately
provisioned read-only toolchain roots. It handles filesystem rights, TCP,
pathname/abstract UNIX socket connections and signals. ABI 9 does not restrict
UDP, all IPC, or network-based brokers: this is NOT a complete D5/D6 boundary.
No production activation or root trust/ACL verification is implemented here.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RestrictedResult:
    state: str
    returncode: int | None = None
    stdout: bytes = b""
    stderr: bytes = b""


def _path(value):
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("invalid path")
    return path.resolve(strict=True)


def _overlap(a, b):
    return a == b or a in b.parents or b in a.parents


def run_restricted(argv: Sequence[str], *, project: Path, scratch: Path, cwd: Path,
                   readonly_roots: Sequence[Path], private_roots: Sequence[Path],
                   env: dict[str, str], timeout: float = 10,
                   max_output_bytes: int = 65536) -> RestrictedResult:
    """Run a fixture command in a fresh child, or fail closed without running it.

    The caller must independently establish root ownership and trusted binaries.
    This API does not enable a production protected profile.
    """
    if sys.platform != "linux" or platform.machine().lower() not in ("x86_64", "aarch64"):
        return RestrictedResult("unsupported")
    try:
        if (not argv or len(argv) > 256 or any(type(x) is not str or "\0" in x or len(x) > 8192 for x in argv)
                or type(env) is not dict or set(env) - {"LANG", "LC_ALL", "TZ"}
                or any(type(v) is not str or len(v) > 256 or "\0" in v for v in env.values())
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 300
                or type(max_output_bytes) is not int or not 1 <= max_output_bytes <= 1048576):
            raise ValueError("invalid options")
        project, scratch, cwd = _path(project), _path(scratch), _path(cwd)
        readonly = tuple(_path(p) for p in readonly_roots)
        private = tuple(_path(p) for p in private_roots)
        executable = _path(argv[0])
        helper = _path(__file__)
        interpreter = _path(sys.executable)
        if (not readonly or not private or not project.is_dir() or not scratch.is_dir() or not cwd.is_dir()
                or not (cwd == project or project in cwd.parents) or _overlap(project, scratch)
                or any(not root.is_dir() for root in readonly + private)
                or any(_overlap(a, b) for a in (project, scratch, *readonly) for b in private)
                or any(_overlap(root, project) or _overlap(root, scratch) for root in readonly)
                or not any(executable == root or root in executable.parents for root in readonly)
                or not any(interpreter == root or root in interpreter.parents for root in readonly)
                or _overlap(helper, project) or _overlap(helper, scratch)):
            raise ValueError("invalid roots")
        config = json.dumps({"argv": list(argv), "project": str(project), "scratch": str(scratch),
                             "cwd": str(cwd), "readonly": [str(p) for p in readonly], "env": env}).encode()
        if len(config) > 65536:
            raise ValueError("invalid options")
    except (OSError, TypeError, ValueError, RuntimeError):
        return RestrictedResult("invalid")

    try:
        child = subprocess.Popen([str(interpreter), "-I", str(helper), "--child"], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
                                 start_new_session=True, env={"LANG": "C", "LC_ALL": "C"})
        # The helper consumes this pipe before launching the target, and closes it.
        child.stdin.write(config)
        child.stdin.close()
        buffers = [bytearray(), bytearray()]
        exceeded = threading.Event()
        lock = threading.Lock()
        def consume(pipe, buffer):
            while True:
                data = pipe.read(4096)
                if not data:
                    return
                with lock:
                    remaining = max_output_bytes - sum(map(len, buffers))
                    buffer.extend(data[:max(0, remaining)])
                    if len(data) > remaining:
                        exceeded.set()
                        try:
                            os.killpg(child.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
        threads = [threading.Thread(target=consume, args=(pipe, buf), daemon=True)
                   for pipe, buf in zip((child.stdout, child.stderr), buffers)]
        for thread in threads:
            thread.start()
        try:
            code = child.wait(timeout=timeout)
            state = "output_limit" if exceeded.is_set() else "completed"
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()
            code, state = None, "timeout"
        for thread in threads:
            thread.join(timeout=1)
        if state == "completed" and code in (125, 126):
            return RestrictedResult("unsupported" if code == 125 else "setup_failed")
        return RestrictedResult(state, code, bytes(buffers[0]), bytes(buffers[1]))
    except (OSError, ValueError):
        return RestrictedResult("setup_failed")


def _child():
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    syscall.restype = ctypes.c_long
    create, add, restrict = 444, 445, 446
    if syscall(create, 0, 0, 1) < 9:
        return 125
    try:
        config = json.loads(sys.stdin.buffer.read(65537))
        null = os.open(os.devnull, os.O_RDONLY)
        os.dup2(null, 0)
        os.close(null)
        class Ruleset(ctypes.Structure):
            _fields_ = [("fs", ctypes.c_uint64), ("net", ctypes.c_uint64), ("scoped", ctypes.c_uint64)]
        class PathRule(ctypes.Structure):
            _fields_ = [("allowed", ctypes.c_uint64), ("fd", ctypes.c_int32)]
        # Bits 0..15 through RESOLVE_UNIX; TCP bind/connect and both scopes.
        fs = (1 << 16) - 1
        attr = Ruleset(fs, 3, 3)
        rules = syscall(create, ctypes.byref(attr), ctypes.sizeof(attr), 0)
        if rules < 0:
            return 126
        read_exec = (1 << 0) | (1 << 2) | (1 << 3)
        # Never allow device creation or ioctl, or external UNIX connections.
        write = fs & ~((1 << 6) | (1 << 11) | (1 << 14) | (1 << 15))
        for path, rights in [(p, read_exec) for p in config["readonly"]] + [(config["project"], write), (config["scratch"], write)]:
            fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
            try:
                rule = PathRule(rights, fd)
                if syscall(add, rules, 1, ctypes.byref(rule), 0) < 0:
                    return 126
            finally:
                os.close(fd)
        if libc.prctl(38, 1, 0, 0, 0) != 0 or syscall(restrict, rules, 0) < 0:
            return 126
        os.close(rules)
        os.chdir(config["cwd"])
        os.execve(config["argv"][0], config["argv"], config["env"])
    except Exception:
        return 126
    return 126


if __name__ == "__main__" and sys.argv[1:] == ["--child"]:
    raise SystemExit(_child())
