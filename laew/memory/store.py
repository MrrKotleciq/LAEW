"""Transactional SQLite source of truth for long-term memory."""
import contextlib
import hashlib
import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from .categories import CATEGORIES, normalize_category

DEFAULTS = {"recall_enabled": True, "max_memories": 5, "token_budget": 400,
            "extraction_mode": "review", "interval_completed_turns": 5,
            "semantic_enabled": True, "fallback_to_fts": True, "extraction_model": None}


def identifier():
    return str(uuid.uuid4())


def validate_record(content, scope, project_id, category):
    if not isinstance(content, str) or not 1 <= len(content.strip()) <= 2000:
        raise ValueError("Memory content must contain 1–2000 characters.")
    normalize_category(category)
    if not ((scope == "user" and project_id is None) or
            (scope == "project" and isinstance(project_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project_id))):
        raise ValueError("Invalid memory scope.")
    # Reject recognizable credentials before either proposals or records are stored.
    if re.search(r"(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{20,}|Bearer\s+\S+|-----BEGIN .*PRIVATE KEY)", content):
        raise ValueError("Memory cannot contain credentials.")
    return content.strip()


def fingerprint(content):
    return hashlib.sha256(" ".join(content.casefold().split()).encode()).hexdigest()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS memories (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL CHECK(scope IN ('user','project')),
 project_id TEXT, category TEXT NOT NULL, content TEXT NOT NULL, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('active','deleted','superseded')),
 version INTEGER NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL,
 CHECK ((scope='user' AND project_id IS NULL) OR (scope='project' AND project_id IS NOT NULL)));
CREATE UNIQUE INDEX IF NOT EXISTS memory_unique_active ON memories(scope, COALESCE(project_id,''),fingerprint) WHERE status='active';
CREATE INDEX IF NOT EXISTS memory_scope ON memories(scope,project_id,status);
CREATE TABLE IF NOT EXISTS memory_sources (
 id TEXT PRIMARY KEY, memory_id TEXT REFERENCES memories(id), proposal_id TEXT,
 conversation_id TEXT, event_id TEXT, origin TEXT NOT NULL, created_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS memory_revisions (
 id TEXT PRIMARY KEY, memory_id TEXT NOT NULL REFERENCES memories(id), version INTEGER NOT NULL,
 content TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, created_at REAL NOT NULL,
 UNIQUE(memory_id,version));
CREATE TABLE IF NOT EXISTS memory_proposals (
 id TEXT PRIMARY KEY, scope TEXT NOT NULL, project_id TEXT, category TEXT NOT NULL,
 content TEXT NOT NULL, operation TEXT NOT NULL, target_id TEXT REFERENCES memories(id),
 target_version INTEGER, status TEXT NOT NULL DEFAULT 'pending', dedup_key TEXT UNIQUE,
 created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS extraction_checkpoints (
 conversation_id TEXT PRIMARY KEY, sequence INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS extraction_jobs (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, start_sequence INTEGER NOT NULL,
 end_sequence INTEGER NOT NULL, model_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 lease_until REAL NOT NULL DEFAULT 0, lease_token TEXT, attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT, retry_at REAL NOT NULL DEFAULT 0, created_at REAL NOT NULL,
 UNIQUE(conversation_id,start_sequence,end_sequence));
CREATE TABLE IF NOT EXISTS memory_index_outbox (
 id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id TEXT NOT NULL REFERENCES memories(id),
 version INTEGER NOT NULL, completed_at REAL, error TEXT, UNIQUE(memory_id,version));
CREATE TABLE IF NOT EXISTS memory_settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS memory_project_settings (project_id TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(id UNINDEXED,content,tokenize='unicode61');
'''


class MemoryStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1, 2):
                raise ValueError('Unsupported memory database schema version.')
            db.executescript(SCHEMA)
            db.execute('PRAGMA user_version=2')

    @contextlib.contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON')
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

    def settings(self, project_id=None):
        with self.connection() as db:
            row = db.execute('SELECT value FROM memory_settings WHERE id=1').fetchone()
        result={**DEFAULTS, **(json.loads(row[0]) if row else {})}
        if project_id is not None: result.update(self.project_settings(project_id))
        return result

    def project_settings(self, project_id):
        with self.connection() as db:
            row=db.execute('SELECT value FROM memory_project_settings WHERE project_id=?',(project_id,)).fetchone()
            return json.loads(row[0]) if row else {}

    def save_project_settings(self, project_id, overrides):
        validate_record('settings','project',project_id,'fact')
        if not isinstance(overrides,dict) or set(overrides)-set(DEFAULTS): raise ValueError('Unknown memory override.')
        self.validate_settings(self.settings() | overrides)
        with self.transaction() as db:
            db.execute('INSERT INTO memory_project_settings VALUES(?,?) ON CONFLICT(project_id) DO UPDATE SET value=excluded.value',(project_id,json.dumps(overrides)))
        return self.settings(project_id)

    @staticmethod
    def validate_settings(value):
        for key in ('recall_enabled','semantic_enabled','fallback_to_fts'):
            if type(value[key]) is not bool: raise ValueError('Invalid boolean setting.')
        for key,lower,upper in [('max_memories',1,20),('token_budget',100,2000),('interval_completed_turns',2,20)]:
            if type(value[key]) is not int or not lower<=value[key]<=upper: raise ValueError('Invalid memory limit.')
        if value['extraction_mode'] not in ('off','review','auto'): raise ValueError('Invalid extraction mode.')
        model=value['extraction_model']
        if model is not None:
            if (not isinstance(model,dict) or set(model)-{'provider','model','account_id'} or
                model.get('provider') not in ('manifest','ollama','llama.cpp','gemini','openai-api','chatgpt') or
                not isinstance(model.get('model'),str) or not 1<=len(model['model'].strip())<=200 or
                (model.get('account_id') is not None and not isinstance(model['account_id'],str))):
                raise ValueError('An extraction model requires a supported provider and explicit model ID.')
        return value

    def save_settings(self, updates):
        if not isinstance(updates, dict) or set(updates) - set(DEFAULTS):
            raise ValueError('Unknown memory settings.')
        with self.transaction() as db:
            row = db.execute('SELECT value FROM memory_settings WHERE id=1').fetchone()
            value = {**DEFAULTS, **(json.loads(row[0]) if row else {}), **updates}
            self.validate_settings(value)
            db.execute('INSERT INTO memory_settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value', (json.dumps(value),))
        return value

    @staticmethod
    def _write(db, content, scope, project_id, category, *, memory_id=None, expected_version=None, reason='Manual edit'):
        category = normalize_category(category)
        content = validate_record(content,scope,project_id,category)
        now = time.time()
        if memory_id:
            if type(expected_version) is not int or expected_version<1: raise ValueError('A positive expected memory version is required.')
            row = db.execute('SELECT * FROM memories WHERE id=? AND status="active"',(memory_id,)).fetchone()
            if not row or row['version'] != expected_version: raise ValueError('Memory changed; reload before editing.')
            if (row['scope'],row['project_id']) != (scope,project_id): raise ValueError('Memory scope is immutable.')
            version = row['version']+1
            db.execute('UPDATE memories SET content=?,category=?,fingerprint=?,version=?,updated_at=? WHERE id=?',
                       (content,category,fingerprint(content),version,now,memory_id))
        else:
            existing = db.execute("SELECT id FROM memories WHERE scope=? AND project_id IS ? AND fingerprint=? AND status='active'",(scope,project_id,fingerprint(content))).fetchone()
            if existing: return existing[0]
            memory_id,version=identifier(),1
            db.execute('INSERT INTO memories VALUES(?,?,?,?,?,?,\'active\',?,?,?)',
                       (memory_id,scope,project_id,category,content,fingerprint(content),version,now,now))
        db.execute('INSERT INTO memory_revisions VALUES(?,?,?,?,?,?,?)',(identifier(),memory_id,version,content,'active',reason,now))
        db.execute('DELETE FROM memory_fts WHERE id=?',(memory_id,))
        db.execute('INSERT INTO memory_fts VALUES(?,?)',(memory_id,content))
        db.execute('INSERT INTO memory_index_outbox(memory_id,version) VALUES(?,?)',(memory_id,version))
        return memory_id

    def remember(self, content, scope='user', project_id=None, category='fact', source=None):
        with self.transaction() as db:
            key=self._write(db,content,scope,project_id,category)
            if source:
                db.execute('INSERT INTO memory_sources VALUES(?,?,?,?,?,?,?)',(identifier(),key,None,source.get('conversation_id'),source.get('event_id'),source.get('origin','manual'),time.time()))
        return self.get(key)

    def get(self, key):
        with self.connection() as db:
            row=db.execute('SELECT * FROM memories WHERE id=?',(key,)).fetchone()
            if not row: raise ValueError('Memory not found.')
            value=dict(row)
            value['sources']=[dict(x) for x in db.execute('SELECT * FROM memory_sources WHERE memory_id=?',(key,))]
            value['revisions']=[dict(x) for x in db.execute('SELECT * FROM memory_revisions WHERE memory_id=? ORDER BY version',(key,))]
            return value

    def list_memories(self, project_id=None, scope=None, status='active'):
        with self.connection() as db:
            rows=db.execute("SELECT * FROM memories WHERE status=? AND (scope='user' OR (scope='project' AND project_id IS ?)) ORDER BY updated_at DESC LIMIT 200",(status,project_id))
            return [dict(row) | {'sources':[dict(source) for source in db.execute('SELECT * FROM memory_sources WHERE memory_id=?',(row['id'],))]} for row in rows if scope is None or row['scope']==scope]

    def update(self, key, content, version, category=None):
        with self.transaction() as db:
            row=db.execute('SELECT * FROM memories WHERE id=?',(key,)).fetchone()
            if not row: raise ValueError('Memory not found.')
            self._write(db,content,row['scope'],row['project_id'],row['category'] if category is None else category,memory_id=key,expected_version=version)
        return self.get(key)

    def delete(self, key, version):
        if type(version) is not int or version<1: raise ValueError('A positive expected memory version is required.')
        with self.transaction() as db:
            row=db.execute('SELECT * FROM memories WHERE id=?',(key,)).fetchone()
            if not row or row['version']!=version: raise ValueError('Memory changed; reload before deleting.')
            if row['status']=='deleted': return
            now=time.time()
            db.execute("UPDATE memories SET status='deleted',version=version+1,updated_at=? WHERE id=?",(now,key))
            db.execute('DELETE FROM memory_fts WHERE id=?',(key,))
            db.execute('INSERT INTO memory_revisions VALUES(?,?,?,?,?,?,?)',(identifier(),key,version+1,row['content'],'deleted','Deleted by user',now))
            db.execute('INSERT INTO memory_index_outbox(memory_id,version) VALUES(?,?)',(key,version+1))

    def fts(self, query, project_id, limit=20):
        words=re.findall(r'[^\W_]+',query,flags=re.UNICODE)[:32]
        if not words: return []
        match=' OR '.join('"'+word+'"' for word in words)
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT m.* FROM memory_fts f JOIN memories m ON m.id=f.id WHERE memory_fts MATCH ? AND m.status='active' AND (m.scope='user' OR (m.scope='project' AND m.project_id IS ?)) ORDER BY bm25(memory_fts) LIMIT ?",(match,project_id,limit))]
