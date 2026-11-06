"""Run LAEW pytest or an evaluation module with per-run temporary storage."""

import argparse
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time


REPO = Path(__file__).resolve().parents[1]
REPARSE_POINT = stat.FILE_ATTRIBUTE_REPARSE_POINT


class WindowsJob:
    """Track descendants from before launch, including detached browsers."""

    class Accounting(ctypes.Structure):
        _fields_ = [
            ("times", ctypes.c_longlong * 4),
            ("page_faults", wintypes.DWORD),
            ("total_processes", wintypes.DWORD),
            ("active_processes", wintypes.DWORD),
            ("terminated_processes", wintypes.DWORD),
        ]

    def __init__(self):
        kernel = self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD, wintypes.LPVOID
        ]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE
        ]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.SetFileInformationByHandle.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD
        ]

        self.handle = kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        # Children inherit the job at creation, so no process can start before
        # it is tracked. The job allows neither breakaway nor kill-on-close.
        if not kernel.AssignProcessToJobObject(self.handle, kernel.GetCurrentProcess()):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def busy(self):
        info = self.Accounting()
        basic_accounting_information = 1
        if not self.kernel.QueryInformationJobObject(
            self.handle, basic_accounting_information, ctypes.byref(info), ctypes.sizeof(info), None
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return info.active_processes > 1  # The runner itself is in the job.

    @contextmanager
    def exclusive_handle(self, path, expected):
        import msvcrt

        # DELETE | FILE_READ_DATA (or FILE_LIST_DIRECTORY), no sharing.
        access = 0x10001
        if expected.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
            access |= 0x100  # FILE_WRITE_ATTRIBUTES for deleting a read-only file.
        # OPEN_EXISTING, BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
        handle = self.kernel.CreateFileW(str(path), access, 0, None, 3, 0x02200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error(), f"Cannot open exclusively: {path}")
        try:
            fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
        except OSError:
            self.kernel.CloseHandle(handle)
            raise
        try:
            actual = os.fstat(fd)
            if (not os.path.samestat(actual, expected)
                    or actual.st_file_attributes & REPARSE_POINT
                    or stat.S_IFMT(actual.st_mode) != stat.S_IFMT(expected.st_mode)
                    or (stat.S_ISREG(actual.st_mode)
                        and (actual.st_size, actual.st_mtime_ns)
                        != (expected.st_size, expected.st_mtime_ns))):
                raise OSError(f"Entry changed or is a reparse point: {path}")
            yield handle
        finally:
            os.close(fd)

    def snapshot(self, path):
        metadata = path.lstat()
        if (metadata.st_file_attributes & REPARSE_POINT
                or not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode))):
            raise OSError(f"Unexpected link or special entry: {path}")
        with self.exclusive_handle(path, metadata):
            pass
        children = []
        if stat.S_ISDIR(metadata.st_mode):
            children = [self.snapshot(child) for child in path.iterdir()]
        return path, metadata, children

    def remove_tree(self, tree):
        path, metadata, children = tree
        # Keep each ancestor open while deleting its verified descendants.
        with self.exclusive_handle(path, metadata) as handle:
            for child in children:
                self.remove_tree(child)
            # FileDispositionInfoEx, DELETE | FORCE_IMAGE_SECTION_CHECK.
            flags = 0x05
            if metadata.st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
                flags |= 0x10  # IGNORE_READONLY_ATTRIBUTE
            disposition = wintypes.DWORD(flags)
            if not self.kernel.SetFileInformationByHandle(
                handle, 21, ctypes.byref(disposition), ctypes.sizeof(disposition)
            ):
                raise ctypes.WinError(ctypes.get_last_error(), f"Cannot delete verified entry: {path}")

    def close(self):
        self.kernel.CloseHandle(self.handle)


def make_run_directory():
    candidates = [os.environ.get(name) for name in ("TMPDIR", "TEMP", "TMP")]
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(str(Path(local_app_data) / "Temp"))
        excluded = (REPO, Path(r"C:\ROOT").resolve())
    else:
        candidates.append("/tmp")
        excluded = (REPO,)
    for candidate in filter(None, candidates):
        try:
            base = Path(candidate).resolve(strict=True)
            if any(base.is_relative_to(path) for path in excluded):
                continue
            if any((path / ".obsidian").is_dir() for path in (base, *base.parents)):
                continue
            return Path(tempfile.mkdtemp(prefix="laew-run-", dir=base))
        except OSError:
            continue
    raise OSError("No writable temporary directory outside the repository and Obsidian vaults.")


def eval_arguments(args, work):
    parser = argparse.ArgumentParser(add_help=False)
    # Match the evaluators' argparse syntax, including abbreviations and '='.
    parser.add_argument("--output", action="append", default=[])
    options, remaining = parser.parse_known_args(args[1:])
    outputs = []
    for value in options.output:
        path = Path(value)
        if not value or ".." in path.parts or (path.anchor and not path.is_absolute()):
            raise OSError("--output must stay inside the run work directory")
        if os.name == "nt":
            is_reserved = getattr(os.path, "isreserved", lambda name: Path(name).is_reserved())
            if any(":" in part or part.endswith((" ", ".")) or is_reserved(part)
                   for part in path.parts if part != path.anchor):
                raise OSError("--output contains a reserved Windows path component")
        try:
            target = (work / path).resolve()
        except RuntimeError as error:
            raise OSError("Cannot resolve --output") from error
        if target == work or not target.is_relative_to(work):
            raise OSError("--output must stay inside the run work directory")
        outputs.append(f"--output={target}")
    return [args[0], *outputs, *remaining]


def prepare_command(mode, args, run, env):
    if mode == "pytest":
        # Insert our overrides after user options and before any end-of-options marker.
        split = args.index("--") if "--" in args else len(args)
        options = ["--basetemp", str(run / "pytest"), "-o", f"cache_dir={run / 'pytest-cache'}"]
        return ["pytest", *args[:split], *options, *args[split:]], REPO

    # Existing evaluators use relative fixture paths and some explicitly use
    # the working directory for SQLite/Chroma scratch space.
    work = run / "work"
    for path in ("tests/evaluation", "tests/rag", "manifests"):
        shutil.copytree(REPO / path, work / path, symlinks=True,
                        ignore=shutil.ignore_patterns("*.py", "__pycache__"))
    (work / "docs" / "reports").mkdir(parents=True)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(REPO), env.get("PYTHONPATH"))))
    return eval_arguments(args, work.resolve(strict=True)), work


def group_is_busy(process):
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return False
    return True


def finish(run, original, keep, process, job):
    try:
        if keep:
            print(f"Diagnostics kept: {run}", file=sys.stderr)
            return
        if job or process is not None:
            busy = job.busy if job else lambda: group_is_busy(process)
            deadline = time.monotonic() + 2
            while busy():
                if time.monotonic() >= deadline:
                    raise OSError("descendant processes are still running")
                time.sleep(0.1)
        if run.resolve(strict=True) != run or not os.path.samestat(original, run.lstat()):
            raise OSError("the run directory was replaced")
        if job:
            tree = job.snapshot(run)
            if not os.path.samestat(original, tree[1]):
                raise OSError("the run directory was replaced")
            job.remove_tree(tree)
        else:
            # A Unix descendant can leave its process group. Check open files too.
            result = subprocess.run(["lsof", "-nP", "+D", str(run)], capture_output=True, timeout=10)
            if result.returncode != 1 or result.stdout or result.stderr:
                raise OSError("lsof could not confirm that the run directory is unused")
            shutil.rmtree(run)
    except (OSError, RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print(f"Cleanup stopped: {error}. Check remaining diagnostics at {run}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-diagnostics", action="store_true")
    parser.add_argument("mode", choices=("pytest", "eval"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    args = options.args
    if options.mode == "eval" and (
        not args or not args[0].startswith("laew.eval.")
        or not all(part.isidentifier() for part in args[0].split("."))
    ):
        parser.error("eval requires a module name such as laew.eval.memory_sufficiency_eval")

    job = None
    try:
        if os.name == "nt":
            job = WindowsJob()
        run = make_run_directory()
        original = run.lstat()
        print(f"Run directory: {run}", file=sys.stderr, flush=True)
        process = None
        interrupted = False
        try:
            env = os.environ.copy()
            env.update(TEMP=str(run), TMP=str(run), TMPDIR=str(run),
                       PYTHONPYCACHEPREFIX=str(run / "pycache"))
            command, cwd = prepare_command(options.mode, args, run, env)
            process = subprocess.Popen(
                [sys.executable, "-m", *command], cwd=cwd, env=env,
                start_new_session=os.name != "nt",
            )
            code = process.wait()
            return code if code >= 0 else 128 - code
        except KeyboardInterrupt:
            interrupted = True
            if os.name != "nt" and process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
            return 130
        finally:
            # A Ctrl+C can arrive during launch before Popen returns a handle.
            finish(run, original, options.keep_diagnostics or interrupted, process, job)
    except OSError as error:
        print(f"Could not run in isolation: {error}", file=sys.stderr)
        return 2
    finally:
        if job:
            job.close()


if __name__ == "__main__":
    sys.exit(main())
