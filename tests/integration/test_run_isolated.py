import os
import subprocess

import pytest

from scripts.run_isolated import eval_arguments


MODULE = "laew.eval.memory_sufficiency_eval"


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
