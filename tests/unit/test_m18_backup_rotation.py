from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import pytest

from laew.backup.archive import _json, seal_archive
from laew.backup.fence import FENCE_FILENAME
from laew.backup.rotation import RotationError, apply_rotation, plan_rotation


@pytest.fixture
def copies(tmp_path):
    media, locks = tmp_path / 'media', tmp_path / 'locks'
    media.mkdir(); locks.mkdir(mode=0o700); (locks / FENCE_FILENAME).touch()
    base = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
    ids = []
    capture = dict(directories=['conversations', 'vault'], shared_session_root=True,
                   manifest_sha256='1' * 64, package_python_sha256='2' * 64)
    for days in range(50):
        key = str(uuid4())
        seal_archive(media, {}, backup_id=key, cut_id=str(uuid4()), profile_id='fixture', host_id='host',
                     capture=capture)
        path = media / (key + '.receipt.json')
        receipt = json.loads(path.read_bytes())
        receipt['verified_at'] = (base - timedelta(days=days)).isoformat()
        path.write_bytes(_json(receipt))
        ids.append(key)
    profile = dict(profile_id='fixture', host_id='host', config_files={}, memory_enabled=False, knowledge_enabled=False)
    options = dict(pin=ids[-1], profile=profile, now=base)
    return media, locks, ids, options


def test_rotation_plan_and_apply_protects_pin_and_daily_weekly(copies):
    media, locks, ids, options = copies
    plan = plan_rotation(media, **options)
    assert plan == plan_rotation(media, **options)
    rows = {r['backup_id']: r for r in plan['ledger']}
    assert rows[ids[-1]]['reason'] == 'pin'
    assert all(rows[key]['action'] == 'skip' for key in ids[:7])
    assert any(r['reason'] == 'weekly' for r in rows.values())
    candidates = [r['backup_id'] for r in plan['ledger'] if r['action'] == 'delete']
    assert candidates and ids[0] not in candidates and ids[-1] not in candidates
    assert apply_rotation(media, locks, plan, **options)['removed'] == candidates
    assert (media / (ids[-1] + '.zip')).exists()
    assert (media / (ids[0] + '.receipt.json')).exists()
    assert all(not (media / (key + '.zip')).exists() for key in candidates)


def test_tampered_and_missing_generation_skipped_and_plan_replay_refused(copies):
    media, locks, ids, options = copies
    (media / (ids[20] + '.zip')).write_bytes(b'tampered')
    (media / (ids[21] + '.receipt.json')).unlink()
    plan = plan_rotation(media, **options)
    rows = {r['backup_id']: r for r in plan['ledger']}
    assert rows[ids[20]]['reason'] == rows[ids[21]]['reason'] == 'unverified'
    candidate = next(r['backup_id'] for r in plan['ledger'] if r['action'] == 'delete')
    (media / (candidate + '.zip')).write_bytes(b'changed')
    with pytest.raises(RotationError): apply_rotation(media, locks, plan, **options)
    assert (media / (candidate + '.receipt.json')).exists()
    assert (media / (ids[20] + '.zip')).read_bytes() == b'tampered'


def test_invalid_pin_and_future_clock_fail_closed(copies):
    media, locks, ids, options = copies
    (media / (ids[-1] + '.receipt.json')).unlink()
    with pytest.raises(RotationError): plan_rotation(media, **options)
    with pytest.raises(RotationError): plan_rotation(media, **(options | {'now': datetime(2020, 1, 1)}))


def test_hardlinked_generation_is_skipped(copies):
    import os
    media, locks, ids, options = copies
    source = media / (ids[25] + '.zip')
    try:
        os.link(source, media / 'external-link')
    except OSError as exc:
        pytest.skip(f'Hardlink creation unavailable: {type(exc).__name__}')
    plan = plan_rotation(media, **options)
    row = next(r for r in plan['ledger'] if r['backup_id'] == ids[25])
    assert row['reason'] == 'unverified' and row['action'] == 'skip'
    assert plan['other_entry_count'] >= 1
    assert len(plan['other_entries_ref']) == 64
    assert 'external-link' not in str(plan)


def test_crash_after_receipt_deletion_leaves_orphan_and_pin(copies, monkeypatch):
    from pathlib import Path
    media, locks, ids, options = copies
    plan = plan_rotation(media, **options)
    candidate = next(r['backup_id'] for r in plan['ledger'] if r['action'] == 'delete')
    real_unlink = Path.unlink
    def interrupted(path, *args, **kwargs):
        if path.name == candidate + '.zip':
            raise OSError('simulated interruption')
        return real_unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'unlink', interrupted)
        with pytest.raises(OSError): apply_rotation(media, locks, plan, **options)
    assert (media / (candidate + '.zip')).exists()
    assert not (media / (candidate + '.receipt.json')).exists()
    assert (media / (ids[-1] + '.zip')).exists()
    revised = plan_rotation(media, **options)
    row = next(r for r in revised['ledger'] if r['backup_id'] == candidate)
    assert row['reason'] == 'unverified' and row['action'] == 'skip'


def test_stale_newest_and_clock_advancement_block_apply(copies):
    media, locks, ids, options = copies
    plan = plan_rotation(media, **options)
    assert str(media) not in json.dumps(plan)
    assert len(plan['destination_ref']) == 64
    stale = options | {'now': options['now'] + timedelta(hours=24, microseconds=1)}
    with pytest.raises(RotationError, match='24-hour'):
        plan_rotation(media, **stale)
    with pytest.raises(RotationError, match='24-hour'):
        apply_rotation(media, locks, plan, **stale)
    assert all((media / (key + '.zip')).exists() for key in ids)


def test_legacy_archive_cannot_be_freshness_proof_or_pin(copies):
    media, _, ids, options = copies
    legacy = str(uuid4())
    seal_archive(media, {}, backup_id=legacy, cut_id=str(uuid4()), profile_id='fixture', host_id='host')
    receipt_path = media / (legacy + '.receipt.json')
    receipt = json.loads(receipt_path.read_bytes())
    receipt['verified_at'] = (options['now'] + timedelta(days=1)).isoformat()
    receipt_path.write_bytes(_json(receipt))
    with pytest.raises(RotationError, match='24-hour'):
        plan_rotation(media, **(options | {'now': options['now'] + timedelta(days=1, seconds=1)}))
    with pytest.raises(RotationError, match='Pinned generation'):
        plan_rotation(media, **(options | {'pin': legacy}))
    assert (media / (ids[0] + '.zip')).exists()
