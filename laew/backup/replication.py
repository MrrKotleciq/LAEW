"""Fixture-only, receipt-last SFTP replication of independently verified archives.

The selected server must implement OpenSSH's hardlink extension atomically and
refuse an existing link name. This property is qualified separately per server;
ordinary SFTP rename is deliberately not used. Nothing here deletes remote data.
The caller owns policy admission, executable/identity trust and scheduling.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from uuid import uuid4

from .archive import _digest, _uuid, verify_archive
from .restore import _private


class ReplicationError(ValueError):
    """Replication could not be safely completed."""


def _check(value, message="Invalid replication configuration."):
    if not value:
        raise ReplicationError(message)


def _safe(value, pattern, maximum=240):
    return type(value) is str and len(value) <= maximum and re.fullmatch(pattern, value) is not None


@dataclass(frozen=True)
class ReplicationConfig:
    host: str
    port: int
    user: str
    remote_directory: str
    executable: Path
    known_hosts: Path
    public_identity: Path
    agent: str
    timeout: int = 60
    hardlink_qualified: bool = False

    def validate(self):
        _check(_safe(self.host, r"[A-Za-z0-9][A-Za-z0-9.-]*") and
               _safe(self.user, r"[A-Za-z_][A-Za-z0-9_.-]*") and
               type(self.port) is int and 1 <= self.port <= 65535 and
               type(self.timeout) is int and 1 <= self.timeout <= 300)
        _check(_safe(self.remote_directory, r"/[A-Za-z0-9_./-]*") and
               all(p not in (".", "..") for p in self.remote_directory.split("/") if p) and
               "//" not in self.remote_directory)
        for path in (self.executable, self.known_hosts, self.public_identity):
            _check(isinstance(path, Path) and path.is_absolute() and '..' not in path.parts)
            _check(_safe(str(path), r"[A-Za-z0-9_./:\\-]+", 512))
        _check(_safe(self.agent, r"[A-Za-z0-9_./:\\-]+", 512))
        _check(type(self.hardlink_qualified) is bool)


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


class OpenSSHTransport:
    """Explicit OpenSSH batch transport; caller verifies executable and custody.

    ``trust`` is a protected platform callback which must verify the complete
    executable, pin, public identity, agent endpoint and effective launch token.
    There is no default trust decision or ambient SSH agent/config fallback.
    """
    def __init__(self, config, *, trust):
        config.validate()
        _check(callable(trust) and trust(config) is True, "Transport trust is unverified.")
        self.config = config
        self._trust = trust
        self._deadline = time.monotonic() + config.timeout

    def run(self, lines):
        c = self.config
        _check(self._trust(c) is True, 'Transport trust changed.')
        remaining = self._deadline - time.monotonic()
        _check(remaining > 0, 'SFTP budget expired.')
        # Local and remote paths admitted by this module exclude SFTP quoting,
        # globbing, newlines and leading option characters.
        ssh = c.executable.with_name('ssh.exe' if os.name == 'nt' else 'ssh')
        args = [str(c.executable), '-S', str(ssh), '-F', 'none', '-b', '-', '-P', str(c.port),
                '-oBatchMode=yes', '-oStrictHostKeyChecking=yes',
                '-oUserKnownHostsFile=' + str(c.known_hosts), '-oGlobalKnownHostsFile=none',
                '-oIdentityAgent=' + c.agent, '-oIdentitiesOnly=yes',
                '-oForwardAgent=no', '-oClearAllForwardings=yes',
                '-oProxyCommand=none', '-oProxyJump=none', '-oPermitLocalCommand=no',
                '-oConnectTimeout=' + str(min(c.timeout, 30)), '-i', str(c.public_identity),
                c.user + '@' + c.host]
        env = {'PATH': os.defpath}
        if os.name == 'nt':
            env['SystemRoot'] = os.environ.get('SystemRoot', r'C:\Windows')
        try:
            result = subprocess.run(args, input=('\n'.join(lines) + '\n').encode(),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=remaining, env=env, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReplicationError('SFTP operation failed.') from exc
        _check(result.returncode == 0, 'SFTP operation failed.')

    def list_directory(self, directory):
        self.run(['ls ' + directory])

    def put(self, local, remote):
        self.run(['put ' + Path(local).as_posix() + ' ' + remote])

    def get(self, remote, local):
        self.run(['get ' + remote + ' ' + Path(local).as_posix()])

    def link(self, old, new):
        self.run(['ln ' + old + ' ' + new])


def test_connection(config, *, transport):
    """Check pinned authentication and directory visibility, without writes."""
    config.validate()
    _check(not isinstance(transport, OpenSSHTransport) or transport.config == config)
    transport.list_directory(config.remote_directory)
    return {'state': 'connected'}


def replicate_verified(config, *, destination, backup_id, release_record, staging_directory, transport,
                       expected_host=None, expected_profile=None):
    """Verify a local generation, replicate, read back and publish a marker last.

    ``staging_directory`` is a pre-provisioned private local directory. Unique
    remote staging and probe files are intentionally retained on all outcomes.
    A collision or interrupted attempt fails closed and never overwrites.
    """
    config.validate()
    _check(not isinstance(transport, OpenSSHTransport) or transport.config == config)
    _check(config.hardlink_qualified, 'Server no-clobber capability is unqualified.')
    backup_id = _uuid(backup_id)
    destination, release_record, staging_directory = map(Path, (destination, release_record, staging_directory))
    _private(destination)
    _private(staging_directory)
    from laew.operator_cli import _bounded_file, _unique_object
    raw = _bounded_file(release_record, 65536, private=True)
    release = json.loads(raw, object_pairs_hook=_unique_object)
    keys = {'schema_version', 'backup_id', 'archive_sha256', 'release_proof_sha256', 'core_release',
            'core_package_python_sha256', 'worker_package_python_sha256', 'profile_sha256', 'manifest_sha256'}
    _check(type(release) is dict and set(release) == keys and type(release['schema_version']) is int
           and release['schema_version'] == 1 and release['backup_id'] == backup_id and
           all(_digest(release[k]) for k in keys if k.endswith('_sha256')))
    capture = {}
    def observe(_archive, manifest):
        capture.update(manifest.get('capture', {}))
    receipt = verify_archive(destination, backup_id, on_verified=observe)
    _check((expected_host is None or receipt['host_id'] == expected_host) and
           (expected_profile is None or receipt['profile_id'] == expected_profile), 'Foreign backup generation.')
    _check(release['archive_sha256'] == receipt['archive_sha256'] and
           release['manifest_sha256'] == capture.get('manifest_sha256') and
           release['worker_package_python_sha256'] == capture.get('package_python_sha256'),
           'Release record does not match the verified archive.')
    # Copy to a private local snapshot and reverify before any network transfer.
    with tempfile.TemporaryDirectory(prefix='rep-', dir=staging_directory) as tmp:
        root = Path(tmp)
        _private(root)
        _check(_safe(str(root), r'[A-Za-z0-9_./:\\#!{}-]+', 512), 'Unsafe staging path.')
        names = [backup_id + '.zip', backup_id + '.receipt.json', 'backup-release-' + backup_id + '.json']
        for name in names[:2]:
            shutil.copyfile(destination / name, root / name)
        (root / names[2]).write_bytes(raw)
        _check(verify_archive(root, backup_id) == receipt, 'Local generation changed during staging.')
        hashes = {name: _hash(root / name) for name in names}
        marker = backup_id + '.commit.json'
        (root / marker).write_text(json.dumps({'schema_version': 1, 'backup_id': backup_id,
                                              'sha256': hashes}, sort_keys=True, separators=(',', ':')),
                                   encoding='ascii')
        hashes[marker] = _hash(root / marker)
        base = config.remote_directory.rstrip('/') + '/'
        nonce = uuid4().hex
        # Verify the server's hardlink extension rejects a collision and leaves
        # the first link unchanged. Probe artifacts are intentionally retained.
        first, second, probe = (base + '.laew-' + nonce + suffix for suffix in ('-a', '-b', '-probe'))
        probe_a, probe_b = root / 'probe-a', root / 'probe-b'
        probe_a.write_bytes(b'laew-first')
        probe_b.write_bytes(b'laew-second')
        transport.put(probe_a, first)
        transport.put(probe_b, second)
        transport.link(first, probe)
        try:
            transport.link(second, probe)
        except ReplicationError:
            pass
        else:
            raise ReplicationError('Server permits overwriting a hardlink destination.')
        probe_readback = root / 'probe-readback'
        transport.get(probe, probe_readback)
        _check(probe_readback.read_bytes() == b'laew-first', 'Server changed a published name.')
        for name in names + [marker]:
            staged = base + '.laew-' + nonce + '-' + name
            transport.put(root / name, staged)
            readback = root / ('readback-' + name)
            transport.get(staged, readback)
            _check(_hash(readback) == hashes[name], 'Remote readback differs.')
            try:
                transport.link(staged, base + name)
            except ReplicationError:
                # A retry may encounter a prior immutable promotion. Only the
                # exact bytes are acceptable, including for the commit marker.
                pass
            final_readback = root / ('final-' + name)
            transport.get(base + name, final_readback)
            _check(_hash(final_readback) == hashes[name], 'Published remote object differs.')
        return {'state': 'verified', 'backup_id': backup_id}
