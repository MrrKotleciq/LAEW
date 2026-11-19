"""Offline capture/restore drill using synthetic data and disposable index."""
from datetime import datetime, timedelta, timezone
import os
import shutil
import sqlite3
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest

from laew.backup.capture import WriterAcknowledgement, capture_backup
from laew.backup.fence import FENCE_FILENAME
from laew.backup.inventory import Inventory, Source, manifest_content_digest
from laew.backup.recovery_checks import validate_recovery
from laew.backup.restore import restore_backup
from laew.console.session_store import SessionStore, make_chat_payload
from laew.knowledge.store import KnowledgeStore
from laew.memory.service import MemoryService
from laew.memory.store import MemoryStore


@pytest.mark.parametrize("with_rag", [False, True], ids=["canonical-and-memory", "with-local-chroma"])
def test_offline_capture_restore_and_memory_rebuild(tmp_path, monkeypatch, with_rag, record_property):
    from time import perf_counter

    def measure(name, start):
        seconds = round(perf_counter() - start, 4)
        record_property(name, seconds)
        print(f"m18_fixture {name}={seconds}")

    if with_rag:
        chromadb = pytest.importorskip("chromadb")
    install, media, recovery = (tmp_path / p for p in ('install', 'media', 'recovery'))
    for p in (install, media, recovery):
        p.mkdir() if os.name == "nt" else p.mkdir(mode=0o700)
    if os.name == 'nt':
        from laew.security.windows_security import get_current_user_sid
        subprocess.run(['icacls', str(recovery), '/inheritance:r', '/grant:r',
                        f'*{get_current_user_sid()}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F',
                        '*S-1-5-32-544:(OI)(CI)F'], check=True, capture_output=True)
    sessions, vault, locks = (install / p for p in ('sessions', 'vault', 'locks'))
    for p in (sessions, vault, locks): p.mkdir()
    (vault / 'note.md').write_text('Restored source', encoding='utf-8')
    fence = locks / FENCE_FILENAME
    fence.touch()
    manifest = install / 'manifest.yaml'
    manifest.write_text('fixture: true\n', encoding='utf-8')
    chat = SessionStore(sessions)
    chat.save('named', make_chat_payload('manifest.yaml', []))
    conversation = chat.create_conversation('general', None)
    cid = conversation['id']
    chat.append_conversation_event(cid, {'id': 'run-event', 'kind': 'run', 'status': 'running',
                                         'run_id': 'interrupted', 'content': ''})
    memory = MemoryStore(install / 'memory' / 'memory.db')
    knowledge = KnowledgeStore(install / 'curation' / 'curation.db')
    for i in range(105): memory.remember(f'fixture fact number {i:03d}')
    changed = memory.remember('old content before update')
    memory.update(changed['id'], 'new current content', 1)
    deleted = memory.remember('deleted content')
    memory.delete(deleted['id'], 1)
    sources = (Source('sessions_named', sessions, 'directory'), Source('conversations', sessions, 'directory'),
               Source('vault', vault, 'directory'), Source('memory_db', memory.path, 'sqlite'),
               Source('curation_db', knowledge.path, 'sqlite'))
    inventory = Inventory('fixture', 'host', media, fence, sources, manifest_path=manifest,
                          manifest_content_digest=manifest_content_digest({'fixture': True}))
    backup_id, cut_id = str(uuid4()), str(uuid4())
    roster = frozenset({'workbench'})
    proof = WriterAcknowledgement('fixture', 'host', backup_id, cut_id, roster, roster, True, True,
                                  datetime.now(timezone.utc) + timedelta(minutes=10))
    started = perf_counter()
    capture_backup(inventory, backup_id=backup_id, cut_id=cut_id, writers=proof)
    measure("capture_seconds", started)
    profile = dict(schema_version=1, profile_id='fixture', host_id='host', manifest_path=manifest,
                   launch_cwd=install, workspace_root=install, vault=vault, destination=media,
                   fence=fence, config_files={}, memory_enabled=True, knowledge_enabled=True,
                   memory_storage=memory.path, knowledge_storage=knowledge.path)
    target = recovery / 'restored'
    validation = []
    started = perf_counter()
    restore_backup(profile, backup_id, target=target,
                   validate_staged=lambda stage, sealed: validation.append(validate_recovery(stage, sealed)))
    measure("canonical_restore_seconds", started)
    archive_bytes = (media / (backup_id + '.zip')).stat().st_size
    canonical_bytes = sum(path.stat().st_size for path in target.rglob('*') if path.is_file())
    record_property('archive_bytes', archive_bytes)
    record_property('canonical_bytes', canonical_bytes)
    print(f'm18_fixture archive_bytes={archive_bytes} canonical_bytes={canonical_bytes}')
    assert validation[0]['named_sessions'] == 1 and validation[0]['conversations'] == 1
    original = (target / 'conversations' / f'conversation-{cid}.json').read_bytes()
    assert SessionStore(target / 'conversations').load('named')['kind'] == 'chat'
    copy = recovery / 'working'
    shutil.copytree(target, copy)
    restored = SessionStore(copy / 'conversations')
    with restored.conversation_run(cid): restored.recover_interrupted_runs(cid)
    assert restored.load_conversation(cid)['events'][-1]['status'] == 'failed'
    assert (target / 'conversations' / f'conversation-{cid}.json').read_bytes() == original

    # A deterministic in-memory Chroma-compatible collection; no network or model.
    class Collection:
        def __init__(self): self.rows = {}
        def upsert(self, *, ids, documents, embeddings, metadatas):
            for key, text, meta in zip(ids, documents, metadatas): self.rows[key] = (text, meta)
    collection = Collection()
    index = SimpleNamespace(_collection=collection,
                            delete_ids=lambda ids: [collection.rows.pop(key, None) for key in ids])
    service = MemoryService(MemoryStore(copy / 'memory_db/memory.db'), index_factory=lambda: index,
                            embedding_factory=lambda: SimpleNamespace(embed=lambda text: [1.0, 0.0]))
    batch_counts = []
    started = perf_counter()
    while True:
        outcome = service.sync_index()
        assert 'error' not in outcome
        batch_counts.append(outcome['processed'])
        if not outcome['processed']: break
    assert batch_counts[0] == 100 and len(batch_counts) >= 3
    assert len(collection.rows) == 106
    assert collection.rows[changed['id']][0] == 'new current content'
    assert deleted['id'] not in collection.rows
    with sqlite3.connect(copy / 'memory_db/memory.db') as db:
        assert db.execute('SELECT COUNT(*) FROM memory_index_outbox WHERE completed_at IS NULL').fetchone() == (0,)
    measure("memory_fixture_rebuild_seconds", started)
    if not with_rag:
        return

    # Recover an independently backed-up project into a separate disposable root.
    import zipfile
    from chromadb.config import Settings
    from laew.rag import vector_store
    from laew.rag.knowledge_base import KnowledgeBase, KnowledgeScope
    from laew.rag.pipeline import RAGPipeline
    from laew.rag.sync import synchronize_scope
    from laew.rag.vector_store import ChromaVectorStore

    project_archive = recovery / 'project-backup.zip'
    with zipfile.ZipFile(project_archive, 'w') as archive:
        archive.writestr('design.md', '# Project design\nUnique fixture project information.')
    project = recovery / 'project-restored'
    project.mkdir()
    with zipfile.ZipFile(project_archive) as archive:
        assert archive.namelist() == ['design.md']
        (project / 'design.md').write_bytes(archive.read('design.md'))
    client = chromadb.PersistentClient(path=str(recovery / 'chroma'),
                                     settings=Settings(anonymized_telemetry=False))
    monkeypatch.setattr(vector_store, '_build_chroma_client', lambda *args: client)
    class Embedding:
        dimensions = 2
        def embed(self, text): return [1.0, 0.0]
        def embed_batch(self, texts): return [self.embed(text) for text in texts]
    embedding = Embedding()
    kb = KnowledgeBase(str(project), str(target / 'vault'), embedding)
    kb._project_store = ChromaVectorStore(collection_name='restore_project_fixture', source='project')
    kb._global_store = ChromaVectorStore(collection_name='restore_global_fixture', source='global')
    started = perf_counter()
    synchronize_scope(kb, 'project')
    synchronize_scope(kb, 'global')
    pipeline = RAGPipeline(kb, embedding)
    project_result = pipeline.retrieve('fixture', KnowledgeScope.PROJECT)
    global_result = pipeline.retrieve('fixture', KnowledgeScope.GLOBAL)
    hybrid_result = pipeline.retrieve('fixture', KnowledgeScope.HYBRID)
    assert not project_result.error and not global_result.error and not hybrid_result.error
    assert {row['source'] for row in project_result.source_metadata()} == {'@project/design.md'}
    assert {row['source'] for row in global_result.source_metadata()} == {'@knowledge/note.md'}
    assert {row['source'] for row in hybrid_result.source_metadata()} == {
        '@project/design.md', '@knowledge/note.md'}
    assert kb.project_store._collection.count() and kb.global_store._collection.count()
    measure("rag_fixture_rebuild_and_retrieval_seconds", started)
