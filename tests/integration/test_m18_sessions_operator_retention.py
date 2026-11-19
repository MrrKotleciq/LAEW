"""End-to-end operator retention and isolated recovery, synthetic data only."""
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import yaml

from laew.backup.archive import verify_archive
from laew.console.session_store import SessionStore
from laew.operator_cli import dispatch
from laew.retention import MARKS_FILENAME


def test_operator_capture_review_apply_and_restore(tmp_path, capsys):
    install, vault, media, recovery, control = (
        tmp_path / name for name in ('install', 'vault', 'media', 'recovery', 'control')
    )
    for directory in (install, vault, media, recovery, control):
        directory.mkdir(mode=0o777 if os.name == 'nt' else 0o700)
    if os.name == 'nt':
        from laew.security.windows_security import get_current_user_sid
        sid = get_current_user_sid()
        for directory in (media, recovery, control):
            subprocess.run(['icacls', str(directory), '/inheritance:r', '/grant:r',
                            f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F',
                            '*S-1-5-32-544:(OI)(CI)F'], check=True, capture_output=True)
    sessions = install / 'runtime' / 'sessions'
    sessions.mkdir(parents=True)
    manifests = install / 'manifests'
    manifests.mkdir()
    manifest = {'version': '1', 'system_name': 'fixture', 'stage': 'test',
                'workspace': {'root': '.', 'allowed_paths': [], 'restricted_paths': [], 'ignored_patterns': []},
                'models': {'roles': {name: {} for name in ('primary', 'embedding', 'reviewer')}},
                'tools': {'categories': {'filesystem': {'policy': 'read_only_by_default'},
                                         'git': {'policy': 'inspection_first'},
                                         'terminal': {'policy': 'safe_command_allowlist', 'allowlist': []},
                                         'web': {'policy': 'read_only'}}},
                'memory': {'session': {'storage': 'runtime/sessions'}, 'second_brain': {}},
                'rag': {'pipeline': {}}}
    manifest_path = manifests / 'system.yaml'
    manifest_path.write_text(yaml.safe_dump(manifest), encoding='utf-8')
    fence = tmp_path / 'installation.lock'
    fence.touch()
    profile = {'schema_version': 1, 'profile_id': 'fixture', 'host_id': 'host1',
               'manifest_path': str(manifest_path), 'launch_cwd': str(install), 'workspace_root': str(install),
               'vault': str(vault), 'destination': str(media), 'fence': str(fence), 'config_files': {},
               'memory_enabled': False, 'knowledge_enabled': False, 'memory_storage': None, 'knowledge_storage': None}
    profile_path = tmp_path / 'profile.json'
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    doc = SessionStore(sessions).create_conversation('general', None)
    stamp = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
    doc.update(created_at=stamp, updated_at=stamp)
    session_path = sessions / ('conversation-' + doc['id'] + '.json')
    session_path.write_text(json.dumps(doc), encoding='utf-8')
    exact = session_path.read_bytes()
    backup_id = str(uuid4())
    acknowledgement = {'schema_version': 1, 'profile_id': 'fixture', 'host_id': 'host1',
                       'backup_id': backup_id, 'cut_id': str(uuid4()), 'roster': ['fixture'],
                       'stopped': ['fixture'], 'inventory_complete': True, 'restart_inhibited': True,
                       'valid_until': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()}
    ack_path = tmp_path / 'ack.json'
    ack_path.write_text(json.dumps(acknowledgement), encoding='utf-8')
    def call(args):
        code = dispatch(args + ['--json'])
        captured = capsys.readouterr()
        assert captured.err == ''
        return code, json.loads(captured.out)
    code, created = call(['backup', 'create', '--profile', str(profile_path), '--acknowledgement', str(ack_path), '--apply'])
    assert code == 0 and created['data']['receipt']['backup_id'] == backup_id
    mark = {'member': 'conversations/' + session_path.name, 'sha256': hashlib.sha256(exact).hexdigest(),
            'archived_at': stamp, 'pinned': False, 'inactive': True}
    marks_path = media / MARKS_FILENAME
    marks_path.write_text(json.dumps({'schema_version': 1, 'profile_id': 'fixture', 'host_id': 'host1',
                                      'revision': str(uuid4()), 'marks': [mark]}), encoding='utf-8')
    if os.name == 'posix':
        marks_path.chmod(0o600)
    common = ['--scope', 'sessions', '--profile', str(profile_path), '--backup-id', backup_id]
    code, plan = call(['retention', 'plan'] + common)
    assert code == 0 and plan['data']['ledger'][0]['reason'] == 'eligible'
    plan_path = tmp_path / 'reviewed.json'
    plan_path.write_text(json.dumps(plan), encoding='utf-8')
    apply = ['retention', 'apply'] + common + ['--plan', str(plan_path), '--apply']
    assert call(apply)[0] == 2 and session_path.exists()
    proof_path = control / 'retention-proof.json'
    proof = dict(acknowledgement, cut_id=str(uuid4()), review_sha256='0' * 64)
    apply += ['--acknowledgement', str(proof_path)]
    proof_path.write_text(json.dumps(proof), encoding='utf-8')
    if os.name == 'posix':
        proof_path.chmod(0o600)
    code, refused = call(apply)
    assert code == 1 and refused['error_code'] == 'writer_acknowledgement_unverified' and session_path.exists()
    proof.update(review_sha256=plan['data']['review_sha256'],
                 valid_until=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())
    proof_path.write_text(json.dumps(proof), encoding='utf-8')
    code, refused = call(apply)
    assert code == 1 and refused['error_code'] == 'writer_acknowledgement_unverified' and session_path.exists()
    proof['valid_until'] = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    proof_path.write_text(json.dumps(proof), encoding='utf-8')
    code, applied = call(apply)
    assert code == 0 and applied['data']['removed'] == 1 and not session_path.exists()
    assert verify_archive(media, backup_id)['backup_id'] == backup_id
    target = recovery / 'restored'
    code, result = call(['restore', '--profile', str(profile_path), '--id', backup_id, '--target', str(target), '--apply'])
    assert code == 0
    assert (target / 'conversations' / session_path.name).read_bytes() == exact
    assert SessionStore(target / 'conversations').load_conversation(doc['id']) == doc
