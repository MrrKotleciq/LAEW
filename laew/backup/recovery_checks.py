"""Read-only semantic checks for an already verified, private restore staging tree.

This does not start workers, contact services, or rebuild derived indexes. Missing
historical conversation references are reported, not fabricated or repaired.
"""
from contextlib import closing
import hashlib
import math
from pathlib import Path
import sqlite3
import time

from .archive import ArchiveLimits, _validate_capture, validate_member_name
from .capture import _CONVERSATION, _DBS, _SESSIONS, _curation, _json, _validate_database, _validate_session


class RecoveryValidationError(ValueError):
    """The staged archive cannot be safely validated for activation."""


def validate_recovery(staged_root, manifest, *, project_roots=(), timeout=5.0):
    """Check staged sessions, database structure and publication state without mutation.

    ``manifest`` is the sealed, already authenticated archive manifest; paths
    are archive logical names beneath the private staging root. Project IDs are
    derived from explicitly approved roots, never inferred from archive data.
    """
    try:
        if not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError('Invalid validation deadline.')
        from laew.rag.identity import canonical_project_path
        project_ids = {hashlib.sha256(canonical_project_path(Path(p)).encode("utf-8")).hexdigest()[:16]
                       for p in project_roots}
        root = Path(staged_root)
        rows = manifest['members']
        names = [row['name'] for row in rows]
        _validate_capture(manifest['capture'], names, ArchiveLimits())
        deadline = time.monotonic() + timeout
        staged = {}
        tree = {}
        for name in manifest['capture']['directories'] + names:
            validate_member_name(name + '/entry' if name in manifest['capture']['directories'] else name)
            path = root.joinpath(*name.split('/'))
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Linked staging member.')
            info = path.lstat()
            if name in manifest['capture']['directories']:
                if not path.is_dir():
                    raise ValueError('Invalid staging directory.')
                tree[path] = (None, None, info.st_mode)
            else:
                if not path.is_file():
                    raise ValueError('Invalid staging file.')
                staged[name] = path
                if name.startswith('vault/'):
                    tree[path] = (None, None, info.st_mode)
        vault = root / 'vault'
        sessions = {}
        named = 0
        for name, path in staged.items():
            if name.split('/', 1)[0] not in _SESSIONS:
                continue
            _validate_session(path)
            match = _CONVERSATION.fullmatch(path.stem)
            if match:
                doc = _json(path.read_bytes())
                project = doc['project_id']
                if project is not None and project not in project_ids:
                    raise ValueError('Project identity does not match restore target.')
                if doc['id'] in sessions:
                    raise ValueError('Duplicate conversation identity.')
                sessions[doc['id']] = doc
            else:
                named += 1
        missing = 0
        databases = 0
        blocked_jobs = 0
        for key, filename in _DBS.items():
            path = staged.get(key + '/' + filename)
            if path is None:
                continue
            databases += 1
            with closing(sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
                db.execute('PRAGMA query_only=ON')
                db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
                _validate_database(db, key)
                tables = ('memories', 'memory_proposals', 'memory_project_settings') if key == 'memory_db' else ('knowledge_proposals',)
                for table in tables:
                    for (project,) in db.execute(f'SELECT DISTINCT project_id FROM {table} WHERE project_id IS NOT NULL'):
                        if project not in project_ids:
                            raise ValueError('Project identity does not match restore target.')
                prefix = 'extraction' if key == 'memory_db' else 'knowledge'
                for cid, sequence in db.execute(f'SELECT conversation_id,sequence FROM {prefix}_checkpoints'):
                    if cid not in sessions:
                        missing += 1
                    elif type(sequence) is not int or sequence < -1 or sequence >= len(sessions[cid]['events']):
                        raise ValueError('Invalid conversation checkpoint.')
                for cid, start, end, status in db.execute(f'SELECT conversation_id,start_sequence,end_sequence,status FROM {prefix}_jobs'):
                    if status not in {'pending', 'running', 'completed'}:
                        raise ValueError('Unsupported job status.')
                    if type(start) is not int or type(end) is not int or start < -1 or end < 0 or end <= start:
                        raise ValueError('Invalid job sequence.')
                    if cid not in sessions:
                        if status in {'pending', 'running'}:
                            blocked_jobs += 1
                        else:
                            missing += 1
                    elif end >= len(sessions[cid]['events']):
                        raise ValueError('Job exceeds conversation sequence.')
                if key == 'curation_db':
                    for project, raw in db.execute('SELECT project_id,payload FROM knowledge_proposals'):
                        payload = _json(raw)
                        if not isinstance(payload, dict):
                            raise ValueError('Invalid curation payload.')
                        if 'conversation_id' not in payload and 'sources' not in payload and 'source_event_ids' not in payload:
                            continue
                        cid, ids, sources = payload.get('conversation_id'), payload.get('source_event_ids'), payload.get('sources')
                        if (not isinstance(cid, str) or not isinstance(ids, list) or not ids or len(ids) > 20
                                or not all(isinstance(eid, str) for eid in ids) or len(set(ids)) != len(ids)
                                or not isinstance(sources, list) or len(sources) != len(ids)):
                            raise ValueError('Invalid curation references.')
                        for eid, source in zip(ids, sources):
                            if not isinstance(source, dict) or source.get('conversation_id') != cid or source.get('event_id') != eid:
                                raise ValueError('Inconsistent curation references.')
                        if cid not in sessions:
                            missing += 1
                            continue
                        conversation = sessions[cid]
                        if conversation['project_id'] != project:
                            raise ValueError('Curation source scope mismatch.')
                        by_id = {event['id']: event for event in conversation['events']}
                        for eid, source in zip(ids, sources):
                            event = by_id.get(eid)
                            if (event is None or event['kind'] not in {'user', 'assistant'} or event.get('generated')
                                    or source.get('role') != event['kind']
                                    or source.get('source_scope') != ('project' if project else 'general')):
                                raise ValueError('Invalid curation source event.')
                if key == 'memory_db':
                    for cid, eid in db.execute('SELECT conversation_id,event_id FROM memory_sources WHERE conversation_id IS NOT NULL'):
                        if cid not in sessions:
                            missing += 1
                        elif eid is not None and eid not in {event['id'] for event in sessions[cid]['events']}:
                            missing += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Validation deadline exceeded.')
        _curation(staged, vault, tree, remaining)
        return {'status': 'validated', 'named_sessions': named, 'conversations': len(sessions),
                'databases': databases, 'missing_historical_references': missing,
                'blocked_missing_jobs': blocked_jobs,
                'index_rebuild_verified': False}
    except Exception as exc:
        raise RecoveryValidationError('Staged semantic validation failed.') from exc
