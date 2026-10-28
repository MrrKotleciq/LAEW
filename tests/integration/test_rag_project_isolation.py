"""Isolation and migration use a temporary Chroma instance only."""

import pytest

from laew.rag.identity import project_collection_name
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.sync import freshness_error, synchronize_scope


class Embedding:
    model = "isolation-test"
    dimensions = 3

    def embed_batch(self, texts):
        return [[1.0, float(len(text)), 1.0] for text in texts]


def test_windows_path_identity():
    assert project_collection_name(r"C:\ROOT\Projects\LAEW") == project_collection_name(r"c:/root/projects/other/../laew/")
    assert project_collection_name(r"D:\Engineering\LAEW") != project_collection_name(r"C:\ROOT\Projects\LAEW")


def test_isolated_project_sync_and_shared_global(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path / "db"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    a = tmp_path / "a" / "same"
    b = tmp_path / "b" / "same"
    vault = tmp_path / "vault"
    for path in (a, b, vault):
        path.mkdir(parents=True)
    (a / "README.md").write_text("alpha project", encoding="utf-8")
    (b / "README.md").write_text("beta project", encoding="utf-8")
    (vault / "global.md").write_text("shared knowledge", encoding="utf-8")
    config = {"enabled": True, "global_collection": "test_shared_global"}
    first = KnowledgeBase(str(a), str(vault), Embedding(), vector_store_config=config)
    second = KnowledgeBase(str(b), str(vault), Embedding(), vector_store_config=config)
    assert first.project_store.collection_name != second.project_store.collection_name
    assert freshness_error(first, "project")
    synchronize_scope(first, "project")
    synchronize_scope(second, "project")
    synchronize_scope(first, "global")
    assert freshness_error(first, "project") is None
    assert freshness_error(second, "global") is None
    assert first.project_store.sync_records("project")[0].text == "alpha project"
    assert second.project_store.sync_records("project")[0].text == "beta project"
    (a / "README.md").unlink()
    synchronize_scope(first, "project")
    assert first.project_store.count() == 0
    assert second.project_store.sync_records("project")[0].text == "beta project"
    restarted = KnowledgeBase(str(b), str(vault), Embedding(), vector_store_config=config)
    assert restarted.project_store.collection_name == second.project_store.collection_name
    assert restarted.global_store.count() == 1


def test_migration_copies_vectors_and_is_idempotent(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    from laew.rag.migration import migrate_legacy_project
    client = chromadb.PersistentClient(path=str(tmp_path / "db"))
    monkeypatch.setattr("laew.rag.migration._build_chroma_client", lambda *args: client)
    project = tmp_path / "project"
    project.mkdir()
    source = client.create_collection("laew_project", metadata={"hnsw:space": "cosine", "embedding_model_id": "test-model"})
    source.add(ids=["project:README.md:0:0"], embeddings=[[0.2, 0.8]],
               metadatas=[{"source": "project", "file_path": "README.md", "text": "hello"}])
    with pytest.raises(ValueError, match="ownership"):
        migrate_legacy_project({}, str(project), confirmed_owner=str(tmp_path))
    result = migrate_legacy_project({}, str(project), confirmed_owner=str(project))
    assert result["records"] == result["copied"] == 1
    assert migrate_legacy_project({}, str(project), confirmed_owner=str(project))["copied"] == 0
    assert source.count() == 1


def test_failed_scope_blocks_retrieval_and_retry_repairs_it(tmp_path, monkeypatch):
    from laew.rag.knowledge_base import KnowledgeScope
    from laew.rag.pipeline import RAGPipeline
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(); vault.mkdir()
    (project / "README.md").write_text("project note", encoding="utf-8")
    (vault / "note.md").write_text("global note", encoding="utf-8")
    embedding = Embedding()
    embedding.embed = lambda text: [1.0, 2.0, 1.0]
    kb = KnowledgeBase(str(project), str(vault), embedding)
    pipeline = RAGPipeline(kb, embedding)
    pipeline.require_freshness = True
    synchronize_scope(kb, "project")
    synchronize_scope(kb, "global")
    original = kb.global_store.add_chunks
    monkeypatch.setattr(kb.global_store, "add_chunks", lambda chunks: (_ for _ in ()).throw(RuntimeError("write failure")))
    with pytest.raises(RuntimeError):
        synchronize_scope(kb, "global", force=True)
    assert "synchronization failed" in pipeline.retrieve("global", KnowledgeScope.GLOBAL).error
    assert pipeline.retrieve("project", KnowledgeScope.PROJECT).error is None
    monkeypatch.setattr(kb.global_store, "add_chunks", original)
    synchronize_scope(kb, "global")
    assert pipeline.retrieve("global", KnowledgeScope.GLOBAL).error is None


def test_scope_sync_prevents_concurrent_writes(tmp_path, monkeypatch):
    import threading
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(); vault.mkdir()
    kb = KnowledgeBase(str(project), str(vault), Embedding())
    entered, release = threading.Event(), threading.Event()
    original = kb.synchronize
    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(kb, "synchronize", slow)
    worker = threading.Thread(target=synchronize_scope, args=(kb, "project"))
    worker.start()
    assert entered.wait(5)
    try:
        with pytest.raises(RuntimeError, match="already in progress"):
            synchronize_scope(kb, "project")
        assert "progress" in freshness_error(kb, "project")
    finally:
        release.set()
        worker.join()
    assert freshness_error(kb, "project") is None


def test_scheduler_runs_at_start_and_periodically_and_stops(tmp_path):
    import threading
    from laew.rag.sync import SyncScheduler
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(); vault.mkdir()
    kb = KnowledgeBase(str(project), str(vault), Embedding())
    global_runs = []
    periodic_done = threading.Event()
    original = kb.synchronize
    def record(*args, **kwargs):
        if kwargs.get("scope") == "global":
            global_runs.append(1)
            if len(global_runs) >= 2:
                periodic_done.set()
        return original(*args, **kwargs)
    kb.synchronize = record
    scheduler = SyncScheduler(lambda root: kb, interval=0.1)
    scheduler.start(project)
    try:
        assert periodic_done.wait(5)
    finally:
        scheduler.close()
    assert len(global_runs) >= 2
    assert freshness_error(kb, "global") is None
    assert freshness_error(kb, "project") is None


def test_partial_write_is_blocked_and_retry_repairs(tmp_path, monkeypatch):
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(); vault.mkdir()
    note = project / "README.md"
    note.write_text("old " * 40, encoding="utf-8")
    kb = KnowledgeBase(str(project), str(vault), Embedding(), chunk_size=30, chunk_overlap=5)
    synchronize_scope(kb, "project")
    note.write_text("new " * 8, encoding="utf-8")
    real_add = kb.project_store.add_chunks
    def partial(chunks):
        real_add(chunks[:1])
        raise RuntimeError("interrupted write")
    monkeypatch.setattr(kb.project_store, "add_chunks", partial)
    with pytest.raises(RuntimeError):
        synchronize_scope(kb, "project")
    assert "synchronization failed" in freshness_error(kb, "project")
    monkeypatch.setattr(kb.project_store, "add_chunks", real_add)
    synchronize_scope(kb, "project")
    assert freshness_error(kb, "project") is None
    assert all("old" not in chunk.text for chunk in kb.project_store.sync_records("project"))
