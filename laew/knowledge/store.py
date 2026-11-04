"""Small transactional store for proposals, jobs and curation settings."""
import contextlib
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS knowledge_proposals (
 id TEXT PRIMARY KEY, project_id TEXT, status TEXT NOT NULL,
 version INTEGER NOT NULL, dedup_key TEXT UNIQUE NOT NULL,
 payload TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_settings (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_checkpoints (conversation_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge_jobs (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, start_sequence INTEGER NOT NULL,
 end_sequence INTEGER NOT NULL, selection TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 lease_until REAL NOT NULL DEFAULT 0, lease_token TEXT, retry_at REAL NOT NULL DEFAULT 0,
 attempts INTEGER NOT NULL DEFAULT 0, error TEXT, created_at REAL NOT NULL,
 UNIQUE(conversation_id,start_sequence,end_sequence));
'''


class KnowledgeStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript(SCHEMA)

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA busy_timeout=10000')
            db.execute('PRAGMA journal_mode=WAL')
            yield db
        finally:
            db.close()

    @contextlib.contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
