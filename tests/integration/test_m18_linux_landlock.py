import os
from pathlib import Path
import sys

import pytest

from laew.security.linux_landlock import run_restricted


def test_unsupported_platform_fails_closed(monkeypatch, tmp_path):
    monkeypatch.setattr("laew.security.linux_landlock.sys.platform", "win32")
    marker = tmp_path / "must-not-exist"
    result = run_restricted(["arbitrary"], project=tmp_path, scratch=tmp_path, cwd=tmp_path,
                            readonly_roots=[], private_roots=[], env={})
    assert result.state == "unsupported"
    assert not marker.exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux kernel fixture required")
def test_linux_fixture_reads_project_and_denies_private(tmp_path):
    project, scratch, private = (tmp_path / name for name in ("project", "scratch", "private"))
    for path in (project, scratch, private):
        path.mkdir()
    (project / "public").write_text("allowed")
    (private / "secret").write_text("blocked")
    executable = Path(sys.executable).resolve()
    root = Path("/usr")
    if root not in executable.parents:
        pytest.skip("fixture Python is outside /usr")
    script = ("import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text()); "
              "p=pathlib.Path(sys.argv[2]); "
              "exec('try:\\n p.read_text()\\nexcept PermissionError:\\n print(\\\"denied\\\")\\nelse:\\n raise SystemExit(4)')")
    result = run_restricted([str(executable), "-c", script, str(project / "public"), str(private / "secret")],
                            project=project, scratch=scratch, cwd=project, readonly_roots=[root],
                            private_roots=[private], env={})
    if result.state == "unsupported":
        pytest.skip("Landlock ABI 9 is unavailable")
    assert result.state == "completed"
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [b"allowed", b"denied"]
