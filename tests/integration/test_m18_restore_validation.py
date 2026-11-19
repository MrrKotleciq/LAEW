import hashlib
import sqlite3
from pathlib import Path

import pytest

from laew.backup.recovery_checks import RecoveryValidationError, validate_recovery
from laew.console.session_store import SessionStore, make_chat_payload
from laew.knowledge.store import SCHEMA as KNOWLEDGE_SCHEMA
from laew.memory.store import SCHEMA as MEMORY_SCHEMA
from laew.rag.identity import canonical_project_path


def fixture(tmp_path):
    for name in ('vault', 'conversations', 'memory_db', 'curation_db'):
        (tmp_path / name).mkdir()
    project = tmp_path / 'project'
    project.mkdir()
    project_id = hashlib.sha256(canonical_project_path(project).encode()).hexdigest()[:16]
    store = SessionStore(tmp_path / 'conversations')
    doc = store.create_conversation('project', project_id)
    store.save('legacy', make_chat_payload('manifest.yaml', []))
    for key, schema, version in (('memory_db/memory.db', MEMORY_SCHEMA, 2), ('curation_db/curation.db', KNOWLEDGE_SCHEMA, 0)):
        with sqlite3.connect(tmp_path / key) as db:
            db.executescript(schema)
            db.execute(f'PRAGMA user_version={version}')
    def manifest():
        files = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*')
                       if p.is_file() and '.locks' not in p.parts and not p.is_relative_to(project))
        return {'members': [{'name': name} for name in files], 'capture': {
            'directories': ['conversations', 'vault'], 'shared_session_root': True,
            'manifest_sha256': '0' * 64, 'package_python_sha256': '0' * 64}}
    return project, doc, manifest


def snapshots(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_valid_recovery_is_readonly_and_requires_matching_project(tmp_path):
    project, doc, manifest = fixture(tmp_path)
    before = snapshots(tmp_path)
    result = validate_recovery(tmp_path, manifest(), project_roots=(project,))
    assert result == {'status': 'validated', 'named_sessions': 1, 'conversations': 1,
                      'databases': 2, 'missing_historical_references': 0, 'index_rebuild_verified': False}
    assert snapshots(tmp_path) == before
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest())


def test_jobs_and_missing_historical_references_preserve_lease(tmp_path):
    project, doc, manifest = fixture(tmp_path)
    dbpath = tmp_path / 'memory_db/memory.db'
    with sqlite3.connect(dbpath) as db:
        db.execute("INSERT INTO extraction_jobs(id,conversation_id,start_sequence,end_sequence,model_json,status,lease_until,lease_token,created_at) VALUES('a','missing',-1,1,'{}','running',99,'token',1)")
    before = snapshots(tmp_path)
    result = validate_recovery(tmp_path, manifest(), project_roots=(project,))
    assert result['missing_historical_references'] == 1
    assert snapshots(tmp_path) == before


def test_foreign_project_in_database_and_bad_schema_rejected(tmp_path):
    project, _, manifest = fixture(tmp_path)
    dbpath = tmp_path / 'memory_db/memory.db'
    with sqlite3.connect(dbpath) as db:
        db.execute("INSERT INTO memory_project_settings VALUES('foreign','{}')")
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest(), project_roots=(project,))
    with sqlite3.connect(dbpath) as db:
        db.execute('DELETE FROM memory_project_settings')
        db.execute('DROP TABLE memory_project_settings')
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest(), project_roots=(project,))


def test_curation_rejects_ambiguous_publication_without_writing(tmp_path):
    project, _, manifest = fixture(tmp_path)
    dbpath = tmp_path / 'curation_db/curation.db'
    with sqlite3.connect(dbpath) as db:
        db.execute("INSERT INTO knowledge_proposals VALUES('id',NULL,'approved',2,'key',?,1,1)",
                   ('{"target":"@knowledge/a.md","approved_version":1,"base_content":"",'
                    '"base_sha256":"","content":"expected","index_status":"not_written"}',))
    (tmp_path / 'vault/a.md').write_text('different')
    before = snapshots(tmp_path)
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest(), project_roots=(project,))
    assert snapshots(tmp_path) == before


def test_corrupt_sqlite_and_session_are_rejected(tmp_path):
    project, doc, manifest = fixture(tmp_path)
    db = tmp_path / 'memory_db/memory.db'
    db.write_bytes(b'not sqlite')
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest(), project_roots=(project,))


def test_corrupt_session_is_rejected(tmp_path):
    project, doc, manifest = fixture(tmp_path)
    session = tmp_path / 'conversations' / f"conversation-{doc['id']}.json"
    session.write_text('{bad')
    with pytest.raises(RecoveryValidationError):
        validate_recovery(tmp_path, manifest(), project_roots=(project,))
