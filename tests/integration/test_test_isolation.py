"""Regression tests for the offline pytest storage boundary."""

import os
from pathlib import Path
import re
import subprocess
import sys
import time

import pytest
import requests
import yaml


def test_storage_probe():
    if not os.environ.get('LAEW_ISOLATION_PROBE'):
        pytest.skip('subprocess-only probe')
    from laew.memory.store import MemoryStore
    path = Path(os.environ['LAEW_MEMORY_STORAGE'])
    MemoryStore(path)
    assert path.exists()
    if os.environ['LAEW_ISOLATION_PROBE'] == 'fail':
        pytest.fail('intentional failure to check teardown')


def test_explicit_storage_paths_are_confined(tmp_path):
    from laew.console.session_store import SessionStore
    from laew.knowledge.store import KnowledgeStore
    from laew.memory.store import MemoryStore

    outside = Path(__file__).resolve().parents[2] / 'runtime' / 'must-not-be-created'
    for constructor in (SessionStore, KnowledgeStore, MemoryStore):
        with pytest.raises(AssertionError, match='pytest temporary storage'):
            constructor(outside)
    with pytest.raises(AssertionError, match='pytest temporary storage'):
        SessionStore(directory=outside)
    assert SessionStore(directory=tmp_path).directory == tmp_path
    assert not outside.exists()


def test_storage_environment_reaches_child_process(tmp_path):
    script = ('import os; from pathlib import Path; '
              'from laew.memory.store import MemoryStore; '
              'p=Path(os.environ["LAEW_MEMORY_STORAGE"]); '
              'MemoryStore(p); print(p)')
    child = subprocess.run([sys.executable, '-c', script], check=True,
                           capture_output=True, text=True)
    assert Path(child.stdout.strip()) == Path(os.environ['LAEW_MEMORY_STORAGE'])
    assert Path(child.stdout.strip()).exists()


def test_workbench_cli_subprocess_writes_to_fixture_manifest(tmp_path):
    from laew.manifest import load_manifest

    template = Path(__file__).resolve().parents[2] / "manifests" / "SYSTEM_MANIFEST.yaml"
    settings = load_manifest(template)
    sessions = tmp_path / "sessions"
    settings["memory"]["session"]["storage"] = str(sessions)
    settings["memory"]["second_brain"]["path"] = "@knowledge"
    settings["rag"]["vector_store"]["enabled"] = False
    settings.pop("telemetry", None)
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump(settings), encoding="utf-8")
    workspace = Path(os.environ["LAEW_WORKSPACE_ROOT"])
    (workspace / "Projects").mkdir()
    (workspace / "Knowledge").mkdir()
    log = tmp_path / "workbench.log"
    command = [sys.executable, "-u", "-m", "laew.cli", "ui", "--manifest", str(manifest),
               "--no-browser", "--port", "0"]
    with log.open("wb") as output, requests.Session() as client:
        client.trust_env = False
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 15
            while True:
                text = log.read_text(encoding="utf-8", errors="replace")
                endpoint = re.search(r"LAEW UI listening on (http://127\.0\.0\.1:\d+)", text)
                if endpoint:
                    break
                assert child.poll() is None and time.monotonic() < deadline, text
                time.sleep(0.05)
            response = client.post(endpoint[1] + "/api/conversations",
                                   json={"scope_type": "general", "project_id": None}, timeout=5)
            response.raise_for_status()
            assert (sessions / f"conversation-{response.json()['id']}.json").is_file()
            assert Path(os.environ["LAEW_MEMORY_STORAGE"]).is_file()
            assert Path(os.environ["LAEW_KNOWLEDGE_STORAGE"]).is_file()
        finally:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)


def test_concurrent_direct_pytest_runs_clean_up_after_failure(tmp_path):
    env = os.environ.copy()
    env['LAEW_ISOLATION_PROBE'] = 'fail'
    runs = [tmp_path / 'first', tmp_path / 'second']
    processes = [subprocess.Popen(
        [sys.executable, '-m', 'pytest', '-q', __file__ + '::test_storage_probe',
         '--basetemp', str(base)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True) for base in runs]
    for process in processes:
        stdout, stderr = process.communicate(timeout=90)
        assert process.returncode == 1, (stdout, stderr)
        assert 'intentional failure to check teardown' in stdout
    for base in runs:
        assert not list(base.rglob('laew-storage-*'))


def test_concurrent_direct_pytest_cannot_share_an_explicit_base(tmp_path):
    base = tmp_path / "shared"
    env = {**os.environ, "LAEW_ISOLATION_PROBE": "pass"}
    command = [sys.executable, "-m", "pytest", "-q", f"{__file__}::test_storage_probe",
               "--basetemp", str(base)]
    processes = [subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) for _ in range(2)]
    results = [process.communicate(timeout=90) for process in processes]
    assert sorted(process.returncode for process in processes) == [0, 4], results
    assert any("--basetemp must name a new directory" in err for _, err in results)
    assert not list(base.rglob("laew-storage-*"))


@pytest.mark.parametrize('source', ['argument', 'environment', 'ini'])
def test_existing_basetemp_is_rejected_before_pytest_removes_it(tmp_path, source):
    existing = tmp_path / 'existing'
    existing.mkdir()
    sentinel = existing / 'sentinel'
    sentinel.write_text('preserve', encoding='utf-8')
    env = os.environ.copy()
    env.pop('PYTEST_ADDOPTS', None)
    args = [sys.executable, '-m', 'pytest', '--collect-only', '-q', __file__]
    option = f'--basetemp="{existing}"'
    if source == 'argument':
        args.extend(['--basetemp', str(existing)])
    elif source == 'environment':
        env['PYTEST_ADDOPTS'] = option
    else:
        ini = tmp_path / 'pytest.ini'
        ini.write_text(f'[pytest]\naddopts = {option}\n', encoding='utf-8')
        args.extend(['-c', str(ini)])
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert '--basetemp must name a new directory' in result.stderr
    assert sentinel.read_text(encoding='utf-8') == 'preserve'


def test_operational_pytest_debug_temproot_is_rejected():
    env = {**os.environ, "PYTEST_DEBUG_TEMPROOT": str(Path(__file__).resolve().parents[2] / "runtime")}
    result = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", __file__],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 4
    assert "pytest temporary storage must be outside the repository" in result.stderr


@pytest.mark.parametrize("keep", [False, True])
def test_validation_failure_cleanup(tmp_path, keep):
    script = """
import os
import sys
from pathlib import Path
from scripts._validation_workspace import validation_workspace

with validation_workspace(keep=sys.argv[1] == 'keep') as workspace:
    storage = Path(os.environ['LAEW_MEMORY_STORAGE'])
    assert storage.is_relative_to(workspace)
    assert 'LAEW_PROTECTED_PROFILE' not in os.environ
    assert 'LAEW_INSTALLATION_FENCE' not in os.environ
    assert 'LAEW_MANAGED_WRITER_GATE' not in os.environ
    assert 'LAEW_BACKUP_WORKBENCH_VIEW' not in os.environ
    print(workspace, flush=True)
    storage.parent.mkdir(parents=True)
    storage.write_text('synthetic', encoding='utf-8')
    raise SystemExit(7)
"""
    env = {**os.environ, **dict.fromkeys(("TEMP", "TMP", "TMPDIR"), str(tmp_path)),
           "LAEW_MEMORY_STORAGE": str(tmp_path / "unrelated.db"),
           "LAEW_PROTECTED_PROFILE": "unrelated", "LAEW_INSTALLATION_FENCE": "unrelated",
           "LAEW_MANAGED_WRITER_GATE": "unrelated", "LAEW_BACKUP_WORKBENCH_VIEW": "unrelated"}
    result = subprocess.run([sys.executable, "-c", script, "keep" if keep else "clean"],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 7, result.stderr
    workspace = Path(result.stdout.strip())
    assert workspace.parent == tmp_path
    assert workspace.exists() == keep, result.stderr
    assert not (tmp_path / "unrelated.db").exists()
