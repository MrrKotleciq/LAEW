"""Protected-profile integration with disposable paths and mocked identities.

The AppContainer kernel boundary has separate native integration tests.
"""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from laew.security import protected_profile as protected
from laew.security import windows_security
from laew.tools.git import GitTool
from laew.tools.terminal import TerminalTool

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows path and profile contract')


@pytest.fixture
def setup_profile(tmp_path, monkeypatch):
    protected._active = None
    installation = tmp_path / 'protected_install'
    security = installation / 'laew' / 'security'
    security.mkdir(parents=True)
    manifest = installation / 'manifests' / 'system.yaml'
    manifest.parent.mkdir()
    manifest.write_text('fixture')
    bin_dir = installation / 'bin'
    bin_dir.mkdir()
    python = bin_dir / 'python.exe'
    git = bin_dir / 'git.exe'
    python.touch()
    git.touch()
    private_parent = tmp_path / 'private'
    private_parent.mkdir()
    telemetry = private_parent / 'telemetry'
    telemetry.mkdir()
    backup = private_parent / 'backup'
    backup.mkdir()
    project = tmp_path / 'project'
    scratch = tmp_path / 'scratch'
    legacy = tmp_path / 'legacy'
    for path in (project, scratch, legacy):
        path.mkdir()
    config = installation / 'profile.json'
    settings = {'schema_version': 1, 'legacy_installation': str(legacy), 'manifest': str(manifest),
                'telemetry_root': str(telemetry), 'backup_roots': [str(backup)],
                'projects': [{'root': str(project), 'appcontainer': 'fixture-profile', 'scratch': str(scratch)}],
                'executables': {'python': str(python), 'git': str(git)}}
    config.write_text(json.dumps(settings))
    monkeypatch.setattr(protected, '__file__', str(security / 'protected_profile.py'))
    monkeypatch.setenv('LAEW_PROTECTED_PROFILE', str(config))
    monkeypatch.setenv('SECRET_CANARY', 'must-not-be-in-child')
    monkeypatch.setattr(windows_security, 'get_current_user_sid', lambda: 'S-1-5-21-100')
    monkeypatch.setattr(windows_security, 'get_path_owner_sid', lambda path: 'S-1-5-21-200')
    monkeypatch.setattr(windows_security, 'assert_private_owned_path', lambda *a: None)
    monkeypatch.setattr(windows_security, 'assert_trusted_owned_path', lambda *a: None)
    monkeypatch.setattr('laew.manifest.load_manifest', lambda *a: {'telemetry': {'enabled': True, 'root': str(telemetry)}})
    yield SimpleNamespace(**locals())
    protected._active = None


def test_read_only_resolver_checks_profile_without_starting_process(setup_profile, monkeypatch):
    start = MagicMock(side_effect=AssertionError('unexpected process'))
    monkeypatch.setattr('laew.security.windows_appcontainer.run_appcontainer', start)
    assert protected.read_telemetry_root() == setup_profile.telemetry
    start.assert_not_called()
    assert protected._active is None


def test_legacy_owner_must_be_distinct(setup_profile, monkeypatch):
    monkeypatch.setattr(windows_security, 'get_path_owner_sid', lambda path: 'S-1-5-21-100')
    with pytest.raises(protected.ProtectedProfileError):
        protected.read_telemetry_root()


@pytest.mark.parametrize('which', ['legacy', 'project', 'scratch'])
def test_required_roots_are_disjoint(setup_profile, which):
    f = setup_profile
    if which == 'legacy':
        f.settings['legacy_installation'] = str(f.installation)
    elif which == 'project':
        f.settings['projects'][0]['root'] = str(f.telemetry)
    else:
        f.settings['projects'][0]['scratch'] = str(f.backup)
    f.config.write_text(json.dumps(f.settings))
    with pytest.raises(protected.ProtectedProfileError):
        protected.read_telemetry_root()


def test_invalid_configured_profile_never_falls_back_to_legacy(setup_profile, monkeypatch):
    monkeypatch.setenv('LAEW_PROTECTED_PROFILE', str(setup_profile.tmp_path / 'missing'))
    legacy_run = MagicMock(side_effect=AssertionError('legacy subprocess started'))
    monkeypatch.setattr(subprocess, 'run', legacy_run)
    assert protected.activate_runtime_protection() is None
    tool = TerminalTool(workspace_root=setup_profile.project, allowlist={'git'})
    result = tool.execute('run_command', command='git status')
    assert not result.success
    with pytest.raises(protected.ProtectedProfileError):
        GitTool(setup_profile.project)._run_git(['status'])
    legacy_run.assert_not_called()


def test_unconfigured_legacy_tools_keep_existing_runner(tmp_path, monkeypatch):
    monkeypatch.delenv('LAEW_PROTECTED_PROFILE', raising=False)
    protected._active = None
    run = MagicMock(return_value=subprocess.CompletedProcess([], 0, 'fixture', ''))
    monkeypatch.setattr(subprocess, 'run', run)
    tool = TerminalTool(workspace_root=tmp_path, allowlist={'git'})
    assert tool.execute('run_command', command='git status').success
    GitTool(tmp_path)._run_git(['status'])
    assert run.call_count == 2


def test_failed_isolation_probe_never_falls_back(setup_profile, monkeypatch):
    from laew.security.windows_appcontainer import IsolationUnavailable
    launch = MagicMock(side_effect=IsolationUnavailable('fixture failure'))
    legacy_run = MagicMock(side_effect=AssertionError('legacy subprocess started'))
    monkeypatch.setattr('laew.security.windows_appcontainer.run_appcontainer', launch)
    monkeypatch.setattr(subprocess, 'run', legacy_run)
    assert protected.activate_runtime_protection() is None
    assert protected._active is None
    result = TerminalTool(workspace_root=setup_profile.project, allowlist={'git'}).execute(
        'run_command', command='git status')
    assert not result.success
    legacy_run.assert_not_called()


def test_protected_tools_use_allowlisted_executable_and_restricted_environment(setup_profile, monkeypatch):
    f = setup_profile
    calls = []
    def appcontainer(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, 'fixture', '')
    monkeypatch.setattr('laew.security.windows_appcontainer.run_appcontainer', appcontainer)
    legacy = MagicMock(side_effect=AssertionError('legacy subprocess started'))
    monkeypatch.setattr(subprocess, 'run', legacy)
    assert protected.activate_runtime_protection() is not None
    calls.clear()
    tool = TerminalTool(workspace_root=f.project, allowlist={'git'})
    result = tool.execute('run_command', command='git status')
    assert result.success
    git_result = GitTool(f.project)._run_git(['status'])
    assert git_result.returncode == 0
    assert len(calls) == 2
    for argv, options in calls:
        assert argv == [str(f.git), 'status']
        assert options['profile_name'] == 'fixture-profile'
        assert options['cwd'] == f.project
        assert options['env']['TEMP'] == str(f.scratch)
        assert options['env']['HOME'] == str(f.scratch)
        assert 'SECRET_CANARY' not in options['env']
    with pytest.raises(protected.ProtectedProfileError):
        protected.run_project_process(['unknown'], cwd=f.project, timeout=1)
    with pytest.raises(protected.ProtectedProfileError):
        protected.run_project_process(['git'], cwd=f.tmp_path, timeout=1)
    legacy.assert_not_called()


def test_probe_environment_is_accepted_by_native_launcher_validation(setup_profile, monkeypatch):
    from laew.security import windows_appcontainer as native
    profile = protected._load()
    class LaunchReached(Exception): pass
    def stop_before_process():
        raise LaunchReached()
    monkeypatch.setattr(native, '_pipes', stop_before_process)
    with pytest.raises(LaunchReached):
        native.run_appcontainer([str(setup_profile.python), '-c', 'pass'],
            profile_name='fixture-profile', cwd=setup_profile.project,
            env=protected._environment(profile.projects[0], profile.executables), timeout=1)
