"""Reviewed, fenced rotation of verified standalone backup generations.

No scheduler or automatic invocation is installed by this module. The operator
must protect the backup destination and fence against non-cooperating writers.
"""
from datetime import datetime, timedelta, timezone
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re

from .archive import ArchiveError, _file, _uuid, verify_archive
from .fence import host_fence
from .restore import _expected, _identity


class RotationError(ValueError):
    """The reviewed retention decision is no longer safe to apply."""


class RotationPlanChanged(RotationError):
    """The approved rotation ledger no longer matches the verified state."""


def _stamp(path):
    info = _file(path)
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def _verify_generation(directory, key, profile):
    def inspect(_container, manifest):
        _identity(profile, manifest)
        _expected(profile, manifest)

    return verify_archive(directory, key, on_verified=inspect)


def plan_rotation(destination, *, pin, profile, now=None):
    """Return a deterministic ledger. Invalid or incomplete generations are skipped.

    Daily and weekly slots are the newest valid generation for each of the
    seven latest UTC dates and four latest ISO weeks, respectively. ``pin`` is
    the explicitly selected last-known-good backup UUID. Every valid generation
    is freshly verified; receipt timestamps are never accepted as byte proof.
    """
    directory = Path(destination)
    _file(directory, directory=True)
    pin = _uuid(pin)
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.utcoffset() != timezone.utc.utcoffset(now):
        raise RotationError('UTC clock required.')
    entries = sorted(p.name for p in islice(directory.iterdir(), 10001))
    if len(entries) > 10000:
        raise RotationError('Backup directory exceeds rotation limit.')
    ids, other = set(), []
    for name in entries:
        match = re.fullmatch(r'([0-9a-f-]{36})(?:\.zip|\.receipt\.json)', name)
        if match:
            try:
                ids.add(_uuid(match.group(1)))
                continue
            except ArchiveError:
                pass
        other.append(name)
    ledger = []
    for key in sorted(ids):
        row = {'backup_id': key, 'action': 'skip', 'reason': 'unverified'}
        try:
            archive, receipt_path = directory / (key + '.zip'), directory / (key + '.receipt.json')
            before = [_stamp(archive), _stamp(receipt_path)]
            receipt = _verify_generation(directory, key, profile)
            after = [_stamp(archive), _stamp(receipt_path)]
            if before != after:
                raise RotationError('Generation changed during verification.')
            stamp = datetime.fromisoformat(receipt['verified_at'])
            if stamp > now:
                raise RotationError('Generation timestamp is in the future.')
            row.update(reason='verified', verified_at=receipt['verified_at'],
                       archive_sha256=receipt['archive_sha256'], manifest_sha256=receipt['manifest_sha256'],
                       stamps=after)
        except (OSError, ValueError):
            pass
        ledger.append(row)
    valid = sorted((r for r in ledger if r['reason'] == 'verified'),
                   key=lambda r: (r['verified_at'], r['backup_id']), reverse=True)
    if not any(r['backup_id'] == pin for r in valid):
        raise RotationError('Pinned generation is missing or cannot be verified.')
    if not valid or now - datetime.fromisoformat(valid[0]['verified_at']) > timedelta(hours=24):
        raise RotationError('No freshly verified generation within the 24-hour recovery objective.')
    days, weeks = set(), set()
    for row in valid:
        dt = datetime.fromisoformat(row['verified_at'])
        day, week = dt.date().isoformat(), dt.isocalendar()[:2]
        daily = day not in days and len(days) < 7
        weekly = week not in weeks and len(weeks) < 4
        if daily: days.add(day)
        if weekly: weeks.add(week)
        if row['backup_id'] == pin:
            row['reason'] = 'pin'
        elif daily or weekly:
            row['reason'] = 'daily_weekly' if daily and weekly else ('daily' if daily else 'weekly')
        elif valid and row['verified_at'] < valid[0]['verified_at']:
            row.update(action='delete', reason='outside_retention')
        else:
            row['reason'] = 'no_strictly_newer_verified_generation'
    return {'version': 1, 'destination_ref': hashlib.sha256(os.path.normcase(str(directory)).encode('utf-8')).hexdigest(),
            'profile_id': profile['profile_id'], 'host_id': profile['host_id'], 'pin': pin,
            'ledger': ledger, 'other_entry_count': len(other),
            'other_entries_ref': hashlib.sha256(json.dumps(other, separators=(',', ':')).encode('ascii')).hexdigest()}


def apply_rotation(destination, fence_dir, reviewed, *, pin, profile, now=None):
    """Apply only the exact unchanged reviewed ledger while holding the host fence.

    The receipt is unlinked first: a crash can leave an orphan ZIP, which future
    plans skip. The newer verified generation and the explicit pin are never
    deleted. Caller must supply the same protected destination used for review.
    """
    directory = Path(destination)
    with host_fence(Path(fence_dir), mode='maintenance', timeout=0):
        current = plan_rotation(directory, pin=pin, profile=profile, now=now)
        if json.dumps(current, sort_keys=True) != json.dumps(reviewed, sort_keys=True):
            raise RotationPlanChanged('Reviewed rotation plan changed.')
        retained = [row for row in current['ledger'] if row['action'] == 'skip' and 'verified_at' in row]
        newest = max(retained, key=lambda row: (row['verified_at'], row['backup_id']))
        pinned = next(row for row in retained if row['backup_id'] == pin)
        removed = []
        for row in current['ledger']:
            if row['action'] != 'delete':
                continue
            for protected in (newest, pinned, row):
                key = protected['backup_id']
                paths = (directory / (key + '.zip'), directory / (key + '.receipt.json'))
                if [_stamp(p) for p in paths] != protected['stamps']:
                    raise RotationError('Generation changed before deletion.')
                receipt = _verify_generation(directory, key, profile)
                if (receipt['archive_sha256'], receipt['manifest_sha256']) != (
                        protected['archive_sha256'], protected['manifest_sha256']):
                    raise RotationError('Generation verification changed.')
                if [_stamp(p) for p in paths] != protected['stamps']:
                    raise RotationError('Generation changed during verification.')
            if (now or datetime.now(timezone.utc)) - datetime.fromisoformat(newest['verified_at']) > timedelta(hours=24):
                raise RotationError('No freshly verified generation within the 24-hour recovery objective.')
            key = row['backup_id']
            (directory / (key + '.receipt.json')).unlink()
            (directory / (key + '.zip')).unlink()
            removed.append(key)
        return {'removed': removed}
