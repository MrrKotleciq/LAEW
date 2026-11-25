import os
import subprocess
import sys

import pytest

from scripts import run_isolated
from scripts.run_isolated import eval_arguments


MODULE = "laew.eval.memory_sufficiency_eval"


def test_child_environment_replaces_inherited_storage_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv('LAEW_MEMORY_STORAGE', 'operational-memory')
    monkeypatch.setenv('LAEW_KNOWLEDGE_STORAGE', 'operational-knowledge')
    env = run_isolated.run_environment(tmp_path)
    assert env['LAEW_MEMORY_STORAGE'] == str(tmp_path / 'storage' / 'memory.db')
    assert env['LAEW_KNOWLEDGE_STORAGE'] == str(tmp_path / 'storage' / 'curation.db')
    assert env['TEMP'] == env['TMP'] == env['TMPDIR'] == str(tmp_path)


def test_full_offline_suite_stops_before_pytest_when_loopback_is_blocked(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_isolated.py", "pytest-offline"])

    def blocked():
        raise PermissionError("simulated loopback restriction")

    monkeypatch.setattr(run_isolated, "check_loopback", blocked)
    monkeypatch.setattr(run_isolated, "make_run_directory", lambda: pytest.fail("Started a test run"))

    assert run_isolated.main() == 2
    diagnostic = capsys.readouterr().err
    assert "Offline suite not started" in diagnostic
    assert "127.0.0.1" in diagnostic
    assert "simulated loopback restriction" in diagnostic


def test_eval_output_inside_work(tmp_path):
    target = tmp_path / "reports" / "memory.json"
    expected = [MODULE, f"--output={target}", "--dataset", "data.json"]
    assert eval_arguments([MODULE, "--output", "reports/memory.json", "--dataset", "data.json"],
                          tmp_path) == expected
    assert eval_arguments([MODULE, "--dataset", "data.json", f"--out={target}"],
                          tmp_path) == expected


@pytest.mark.parametrize("path", ["../report.json", "reports/../report.json"])
def test_eval_output_rejects_traversal(tmp_path, path):
    with pytest.raises(OSError, match="inside the run work directory"):
        eval_arguments([MODULE, "--output", path], tmp_path)


def test_eval_output_rejects_absolute_escape(tmp_path):
    outside = tmp_path.parent / "outside.json"
    with pytest.raises(OSError, match="inside the run work directory"):
        eval_arguments([MODULE, f"--out={outside}", "--output", "valid.json"], tmp_path)


def test_eval_output_rejects_link_escape(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = work / "link"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(OSError, match="inside the run work directory"):
            eval_arguments([MODULE, "--output", "link/report.json"], work)
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
