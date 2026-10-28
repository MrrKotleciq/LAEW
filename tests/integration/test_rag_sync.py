"""Deterministic synchronization tests using isolated stores."""
import pytest

from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.vector_store import DocumentChunk


class FakeEmbedding:
    dimensions = 3
    model = "sync-test"

    def __init__(self):
        self.calls = 0
        self.fail = False

    def embed_batch(self, texts):
        self.calls += len(texts)
        if self.fail:
            raise RuntimeError("embedding unavailable")
        return [[1.0, float(len(text)), 1.0] for text in texts]


def make_base(tmp_path, embedding):
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(exist_ok=True)
    vault.mkdir(exist_ok=True)
    return KnowledgeBase(str(project), str(vault), embedding, chunk_size=40, chunk_overlap=5)


@pytest.mark.parametrize("scope", ["project", "global"])
def test_sync_add_update_shrink_delete_and_unchanged(tmp_path, scope):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    root = kb.project_root if scope == "project" else kb.knowledge_root
    store = kb.project_store if scope == "project" else kb.global_store
    other = kb.global_store if scope == "project" else kb.project_store
    other.add_chunk(DocumentChunk(chunk_id="other", text="untouched", embedding=[1, 0, 0], source="other"))
    note = root / "note.md"
    note.write_text("The verification code is AURORA-7429. " * 4, encoding="utf-8")
    first = kb.synchronize()
    assert first[scope]["added"]["documents"] == 1
    assert store.count() > 1
    calls = embedding.calls
    kb.synchronize()
    assert embedding.calls == calls
    note.write_text("The verification code is NEBULA-9381.", encoding="utf-8")
    kb.synchronize()
    records = store.sync_records(scope)
    assert len(records) == 1 and "NEBULA-9381" in records[0].text
    assert all("AURORA-7429" not in r.text for r in records)
    assert len({r.chunk_id for r in records}) == len(records)
    assert other.get_chunk("other").text == "untouched"
    note.unlink()
    result = kb.synchronize()
    assert result[scope]["removed"]["documents"] == 1
    assert store.count() == 0


def test_sync_failures_and_missing_roots_do_not_delete(tmp_path):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    note = kb.knowledge_root / "note.md"
    note.write_text("AURORA-7429", encoding="utf-8")
    kb.synchronize()
    note.write_text("NEBULA-9381", encoding="utf-8")
    embedding.fail = True
    with pytest.raises(RuntimeError):
        kb.synchronize()
    assert kb.global_store.sync_records("global")[0].text == "AURORA-7429"
    note.unlink()
    kb.knowledge_root.rmdir()
    with pytest.raises(FileNotFoundError):
        kb.synchronize()
    assert kb.global_store.count() == 1


def test_sync_legacy_record_is_replaced(tmp_path):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    note = kb.knowledge_root / "note.md"
    note.write_text("NEBULA-9381", encoding="utf-8")
    kb.global_store.add_chunk(DocumentChunk(chunk_id="global:note.md:0:0", text="AURORA-7429", embedding=[1, 1, 1], source="global", file_path="note.md"))
    kb.synchronize()
    assert kb.global_store.count() == 1
    assert kb.global_store.sync_records("global")[0].text == "NEBULA-9381"


def test_unchanged_legacy_records_do_not_reembed(tmp_path):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    note = kb.knowledge_root / "note.md"
    note.write_text("Existing note", encoding="utf-8")
    legacy = kb._load_file(note, "global", kb.knowledge_root)
    kb.global_store.add_chunks(legacy)
    calls = embedding.calls
    result = kb.synchronize()
    assert embedding.calls == calls
    assert result["global"]["unchanged"]["documents"] == 1


def test_persistent_sync_survives_restart(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    embedding = FakeEmbedding()
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir(); vault.mkdir()
    note = vault / "note.md"
    note.write_text("AURORA-7429", encoding="utf-8")
    config = {"enabled": True, "project_collection": "test_project_sync", "global_collection": "test_global_sync"}
    kb = KnowledgeBase(str(project), str(vault), embedding, vector_store_config=config)
    kb.synchronize()
    calls = embedding.calls
    restarted = KnowledgeBase(str(project), str(vault), embedding, vector_store_config=config)
    restarted.synchronize()
    assert embedding.calls == calls
    note.write_text("NEBULA-9381", encoding="utf-8")
    restarted.synchronize()
    again = KnowledgeBase(str(project), str(vault), embedding, vector_store_config=config)
    records = again.global_store.sync_records("global")
    assert len(records) == 1 and records[0].text == "NEBULA-9381"


def test_scan_or_write_failure_never_deletes_existing_chunks(tmp_path, monkeypatch):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    note = kb.knowledge_root / "note.md"
    note.write_text("AURORA-7429", encoding="utf-8")
    kb.synchronize()
    note.write_text("NEBULA-9381", encoding="utf-8")
    with monkeypatch.context() as patcher:
        patcher.setattr("laew.rag.knowledge_base.os.walk", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("scan failed")))
        with pytest.raises(PermissionError):
            kb.synchronize()
    assert kb.global_store.sync_records("global")[0].text == "AURORA-7429"
    with monkeypatch.context() as patcher:
        patcher.setattr(kb.global_store, "add_chunks", lambda chunks: (_ for _ in ()).throw(RuntimeError("write failed")))
        with pytest.raises(RuntimeError, match="write failed"):
            kb.synchronize()
    assert kb.global_store.sync_records("global")[0].text == "AURORA-7429"


def test_metadata_changes_are_synchronized(tmp_path):
    kb = make_base(tmp_path, FakeEmbedding())
    note = kb.knowledge_root / "note.md"
    note.write_text("---\ntags: [first]\n---\nText", encoding="utf-8")
    kb.synchronize()
    note.write_text("---\ntags: [second]\n---\nText", encoding="utf-8")
    kb.synchronize()
    assert kb.global_store.sync_records("global")[0].metadata["tags"] == ["second"]


def test_missing_chunk_is_repaired(tmp_path):
    embedding = FakeEmbedding()
    kb = make_base(tmp_path, embedding)
    (kb.knowledge_root / "note.md").write_text("Multiple chunks. " * 12, encoding="utf-8")
    kb.synchronize()
    original = kb.global_store.sync_records("global")
    assert len(original) > 1
    kb.global_store.delete_chunk(original[0].chunk_id)
    kb.synchronize()
    assert {r.chunk_id for r in kb.global_store.sync_records("global")} == {r.chunk_id for r in original}
