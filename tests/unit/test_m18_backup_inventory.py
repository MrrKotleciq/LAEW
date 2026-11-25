from pathlib import Path
import hashlib
import pytest

from laew.backup.inventory import InventoryError, build_inventory, is_excluded
from laew.console.session_store import conversation_store_from_manifest, session_store_from_manifest
from laew.knowledge.integration import knowledge_storage_path
from laew.memory.integration import memory_collection_name, memory_storage_path


@pytest.fixture
def fixture_profile(tmp_path):
    workspace = tmp_path / 'workspace'
    install = workspace / 'install'
    launch = workspace / 'launch'
    for path in (install / 'manifests', install / 'runtime' / 'sessions',
                 launch / 'runtime' / 'sessions', workspace / 'vault', tmp_path / 'backup',
                 install / 'runtime' / 'memory', install / 'runtime' / 'knowledge'):
        path.mkdir(parents=True)
    manifest_path = install / 'manifests' / 'system.yaml'
    manifest_path.write_text('fixture')
    fence = tmp_path / 'installation.lock'
    fence.touch()
    config = tmp_path / 'settings.yaml'
    config.write_text('synthetic')
    (install / 'runtime' / 'memory' / 'memory.db').touch()
    (install / 'runtime' / 'knowledge' / 'curation.db').touch()
    profile = dict(schema_version=1, profile_id='fixture', host_id='host1',
                   manifest_path=manifest_path, launch_cwd=launch, workspace_root=workspace, vault=workspace / 'vault',
                   destination=tmp_path / 'backup', fence=fence, config_files={'settings': config},
                   memory_enabled=True, knowledge_enabled=True, memory_storage=None, knowledge_storage=None)
    return profile, {'memory': {'session': {'storage': 'runtime/sessions'}}}


def test_resolves_distinct_launch_and_manifest_roots_without_store_creation(fixture_profile, monkeypatch):
    profile, manifest = fixture_profile
    monkeypatch.chdir(profile['launch_cwd'])
    result = build_inventory(profile, manifest)
    sources = {s.logical_id: s.path for s in result.sources}
    assert sources['sessions_named'] == session_store_from_manifest(manifest).directory.resolve()
    assert sources['conversations'] == conversation_store_from_manifest(manifest, profile['manifest_path']).directory
    assert sources['memory_db'] == memory_storage_path(sources['conversations'])
    assert sources['curation_db'] == knowledge_storage_path(sources['conversations'])
    assert sources['config_settings'] == profile['config_files']['settings']


def test_override_and_disabled_store(fixture_profile, tmp_path):
    profile, manifest = fixture_profile
    override = tmp_path / 'override.db'
    override.touch()
    profile.update(memory_storage=override, knowledge_enabled=False)
    result = build_inventory(profile, manifest)
    sources = {s.logical_id: s.path for s in result.sources}
    assert sources['memory_db'] == override
    assert sources['curation_db'] == knowledge_storage_path(sources['conversations'])
    sources['curation_db'].unlink()
    assert 'curation_db' not in {s.logical_id for s in build_inventory(profile, manifest).sources}


def test_memory_namespace_matches_runtime_default_and_override(fixture_profile, tmp_path, monkeypatch):
    profile, manifest = fixture_profile
    default = build_inventory(profile, manifest)
    path = next(s.path for s in default.sources if s.logical_id == "memory_db")
    monkeypatch.setenv("LAEW_MEMORY_STORAGE", str(tmp_path / "unrelated-launcher"))
    assert memory_collection_name(None) == "laew_long_term_memory"
    assert default.memory_namespace_sha256 == hashlib.sha256(b"laew_long_term_memory").hexdigest()
    explicit = build_inventory(dict(profile, memory_storage=str(path)), manifest)
    expected = "laew_ltm_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
    assert memory_collection_name(str(path)) == expected
    assert explicit.memory_namespace_sha256 == hashlib.sha256(expected.encode()).hexdigest()
    assert explicit.memory_namespace_sha256 != default.memory_namespace_sha256
    moved = tmp_path / "restored.db"
    moved.touch()
    assert build_inventory(dict(profile, memory_storage=moved), manifest).memory_namespace_sha256 not in (
        default.memory_namespace_sha256, explicit.memory_namespace_sha256)
    path.unlink()
    assert build_inventory(dict(profile, memory_enabled=False), manifest).memory_namespace_sha256 is None


@pytest.mark.parametrize('key,value', [('schema_version', True), ('schema_version', 2),
    ('profile_id', '../bad'), ('host_id', 'HOST'), ('memory_enabled', 1),
    ('destination', 'relative'), ('config_files', []), ('vault', None)])
def test_rejects_invalid_profiles(fixture_profile, key, value):
    profile, manifest = fixture_profile
    profile[key] = value
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


def test_requires_explicit_override_and_rejects_disabled_override(fixture_profile):
    profile, manifest = fixture_profile
    del profile['memory_storage']
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)
    profile.update(memory_storage=profile['fence'], memory_enabled=False)
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


def test_rejects_overlap_and_secret_config(fixture_profile):
    profile, manifest = fixture_profile
    profile['destination'] = profile['vault']
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)
    profile['destination'] = profile['workspace_root'] / 'archive'
    profile['destination'].mkdir()
    with pytest.raises(InventoryError, match="workspace"):
        build_inventory(profile, manifest)
    profile['destination'] = profile['workspace_root'].parent / 'backup'
    profile['config_files'] = {'bad': profile['vault'] / '.env'}
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


def test_rejects_symlink_source(fixture_profile, tmp_path):
    profile, manifest = fixture_profile
    link = tmp_path / 'vault_link'
    try:
        link.symlink_to(profile['vault'], target_is_directory=True)
    except OSError:
        pytest.skip('symlink creation unavailable')
    profile['vault'] = link
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


def test_shared_session_root_is_allowed(fixture_profile):
    profile, manifest = fixture_profile
    profile['launch_cwd'] = profile['manifest_path'].parent.parent
    result = build_inventory(profile, manifest)
    assert result.sources[0].path == result.sources[1].path


def test_rejects_hardlinked_source(fixture_profile, tmp_path):
    import os
    profile, manifest = fixture_profile
    alias = tmp_path / 'config_alias'
    try:
        os.link(profile['config_files']['settings'], alias)
    except OSError:
        pytest.skip('hard link creation unavailable')
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


def test_rejects_mount_boundary(fixture_profile, monkeypatch):
    import laew.backup.inventory as inventory
    profile, manifest = fixture_profile
    original = inventory.os.path.ismount
    monkeypatch.setattr(inventory.os.path, 'ismount',
                        lambda path: Path(path) == profile['vault'] or original(path))
    with pytest.raises(InventoryError):
        build_inventory(profile, manifest)


@pytest.mark.parametrize('path', ['.env', 'sub/.ENV.local', '.obsidian/plugins/foo/config.json',
    '.obsidian/workspace.json', 'notes/token.txt', 'notes/a.log', 'models/model.bin'])
def test_default_exclusions(path):
    assert is_excluded(path)


def test_allowed_relative_path_and_escape():
    assert not is_excluded('notes/research.md')
    with pytest.raises(InventoryError):
        is_excluded('../outside')
