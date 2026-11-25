import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from laew.backup.archive import seal_archive
from laew.backup.replication import ReplicationConfig, ReplicationError, replicate_verified, test_connection as connection_test


class MemorySFTP:
    def __init__(self, *, overwrite=False, corrupt=False):
        self.files = {}
        self.published = []
        self.overwrite = overwrite
        self.corrupt = corrupt

    def list_directory(self, directory):
        assert directory == '/backup'

    def put(self, local, remote):
        self.files[remote] = local.read_bytes()

    def get(self, remote, local):
        data = self.files[remote]
        local.write_bytes(data + (b'corrupt' if self.corrupt and remote.endswith('.zip') else b''))

    def link(self, old, new):
        if new in self.files and not self.overwrite:
            raise ReplicationError('collision')
        self.files[new] = self.files[old]
        self.published.append(new)


@pytest.fixture
def generation(tmp_path, monkeypatch):
    if os.name == 'nt':
        from tests.integration.test_m18_worker_wheel import _private_directory
        # The sandbox injects its own trustee into disposable test ACLs.
        # Real Windows ACL enforcement is covered by the existing backup tests.
        monkeypatch.setattr('laew.security.windows_security.assert_private_owned_path', lambda *_: None)
    else:
        def _private_directory(path):
            path.mkdir(mode=0o700)
    media, staging, releases = (tmp_path / n for n in ('media', 'staging', 'releases'))
    for path in (media, staging, releases):
        _private_directory(path)
    source = tmp_path / 'sample.md'
    source.write_text('fixture', encoding='utf-8')
    backup_id = str(uuid4())
    receipt = seal_archive(media, {'vault/sample.md': source}, backup_id=backup_id, cut_id=str(uuid4()),
                           profile_id='fixture', host_id='host', capture={
                               'directories': ['conversations', 'vault'], 'shared_session_root': True,
                               'manifest_sha256': 'a' * 64, 'package_python_sha256': 'b' * 64})
    release = releases / ('backup-release-' + backup_id + '.json')
    release.write_text(json.dumps({'schema_version': 1, 'backup_id': backup_id,
                                  'archive_sha256': receipt['archive_sha256'],
                                  'release_proof_sha256': 'c' * 64, 'core_release': 'fixture',
                                  'core_package_python_sha256': 'd' * 64,
                                  'worker_package_python_sha256': 'b' * 64,
                                  'profile_sha256': 'e' * 64, 'manifest_sha256': 'a' * 64}), encoding='utf-8')
    if os.name != 'nt':
        release.chmod(0o600)
    # Values are syntactically valid; fake transport performs no network I/O.
    base = Path('C:/fixture') if os.name == 'nt' else Path('/fixture')
    config = ReplicationConfig('example.test', 22, 'backup', '/backup', base / 'sftp',
                               base / 'known', base / 'identity', str(base / 'agent'), hardlink_qualified=True)
    return config, dict(destination=media, backup_id=backup_id, release_record=release, staging_directory=staging)


def test_publish_after_verified_readback_and_connection_is_read_only(generation):
    config, args = generation
    transport = MemorySFTP()
    assert connection_test(config, transport=transport) == {'state': 'connected'}
    assert not transport.files
    assert replicate_verified(config, transport=transport, **args)['state'] == 'verified'
    assert transport.published[-1].endswith('.commit.json')
    assert transport.published[-2].endswith('.json')
    assert len(transport.published) == 5  # one capability probe plus four objects


@pytest.mark.parametrize('failure', ['corrupt', 'overwrite', 'release'])
def test_failure_never_publishes_commit_marker(generation, failure):
    config, args = generation
    transport = MemorySFTP(overwrite=failure == 'overwrite', corrupt=failure == 'corrupt')
    if failure == 'release':
        data = json.loads(args['release_record'].read_text())
        data['archive_sha256'] = 'f' * 64
        args['release_record'].write_text(json.dumps(data))
    with pytest.raises(ReplicationError):
        replicate_verified(config, transport=transport, **args)
    assert not any(name.endswith('.commit.json') for name in transport.published)


@pytest.mark.parametrize('directory', ['/backup/../escape', '/backup space', '/x\nput bad', 'relative'])
def test_invalid_remote_path_rejected(generation, directory):
    config, _ = generation
    with pytest.raises(ReplicationError):
        ReplicationConfig(**(vars(config) | {'remote_directory': directory})).validate()
