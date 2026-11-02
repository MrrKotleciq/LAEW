"""Host-local lock behavior across real operating-system processes."""

import os
import subprocess
import sys

import pytest

from laew.rag.process_lock import CollectionLock


def start_holder(key):
    program = (
        "from laew.rag.process_lock import CollectionLock\n"
        "import sys\n"
        "lock=CollectionLock(sys.argv[1]).acquire()\n"
        "lock.write_state({'state':'incomplete','generation':'crashed'})\n"
        "print('locked',flush=True)\n"
        "sys.stdin.readline()\n"
        "lock.release()\n"
    )
    return subprocess.Popen([sys.executable, "-c", program, key], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())


def test_process_lock_serializes_same_collection_and_recovers_from_crash(tmp_path, monkeypatch):
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path)); monkeypatch.setenv("TMP", str(tmp_path)); monkeypatch.setenv("TMPDIR", str(tmp_path))
    process = start_holder("same-collection")
    try:
        assert process.stdout.readline().strip() == "locked"
        with pytest.raises(TimeoutError):
            CollectionLock("same-collection", timeout=.1).acquire()
        other = CollectionLock("different-collection", timeout=.1).acquire()
        other.release()
        process.kill(); process.wait(timeout=5)
        recovered = CollectionLock("same-collection", timeout=2).acquire()
        try:
            assert recovered.read_state()["state"] == "incomplete"
            recovered.write_state({"state": "complete", "generation": "repaired"})
        finally:
            recovered.release()
        again = CollectionLock("same-collection", timeout=2).acquire()
        try:
            assert again.read_state()["generation"] == "repaired"
        finally:
            again.release()
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)


def test_lock_cancellation(tmp_path, monkeypatch):
    import threading
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    cancelled = threading.Event(); cancelled.set()
    with pytest.raises(RuntimeError, match="cancelled"):
        CollectionLock("cancelled", cancel=cancelled).acquire()


def test_two_processes_sync_same_collection_without_reembedding(tmp_path, monkeypatch):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("TEMP", str(tmp_path)); monkeypatch.setenv("TMP", str(tmp_path)); monkeypatch.setenv("TMPDIR", str(tmp_path))
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (project / "note.md").write_text("A project note.", encoding="utf-8")
    script = '''
import json, sys, time, chromadb
import laew.rag.vector_store as vector_store
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.sync import synchronize_scope
client=chromadb.PersistentClient(path=sys.argv[1])
vector_store._build_chroma_client=lambda *args: client
class Embed:
 model="same-model"; dimensions=3
 def __init__(self): self.calls=0
 def embed_batch(self, texts):
  self.calls += len(texts)
  print("embedding", flush=True)
  time.sleep(1)
  return [[1., 2., 3.] for _ in texts]
embed=Embed()
kb=KnowledgeBase(sys.argv[2],sys.argv[3],embed,vector_store_config={"enabled":True,"global_collection":"global_test"})
result=synchronize_scope(kb,"project",lock_timeout=15)
print(json.dumps({"calls":embed.calls,"result":result}), flush=True)
'''
    cmd = [sys.executable, "-c", script, str(tmp_path / "db"), str(project), str(vault)]
    first = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = None
    try:
        assert first.stdout.readline().strip() == "embedding"
        second = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out1, err1 = first.communicate(timeout=30)
        out2, err2 = second.communicate(timeout=30)
        assert first.returncode == 0, err1
        assert second.returncode == 0, err2
        import json
        assert json.loads(out1.strip())["calls"] == 1
        assert json.loads(out2.strip())["calls"] == 0
        assert json.loads(out2.strip())["result"]["project"]["unchanged"]["documents"] == 1
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.kill(); process.wait(timeout=5)


def test_freshness_is_invalidated_by_another_generation(tmp_path, monkeypatch):
    from laew.rag.sync import synchronize_scope, acquire_fresh_scopes, _process_lock, sync_status
    class KB:
        project_root = tmp_path / "project"
        _vector_store_config = {"enabled": True, "host": "test", "port": 1234}
        project_store = object()
        global_store = object()
        def ensure_store(self, scope): pass
        def synchronize(self, **kwargs): return {"project": {}}
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    kb = KB()
    synchronize_scope(kb, "project")
    locks, error = acquire_fresh_scopes(kb, ["project"])
    assert not error
    for lock in reversed(locks): lock.release()
    other = _process_lock(kb, "project").acquire()
    other.write_state({"state": "complete", "generation": "other-process"})
    other.release()
    assert sync_status(kb, "project")["state"] == "index freshness unknown"
    locks, error = acquire_fresh_scopes(kb, ["project"])
    assert not locks and "another process" in error
    synchronize_scope(kb, "project")
    locks, error = acquire_fresh_scopes(kb, ["project"])
    assert not error
    for lock in reversed(locks): lock.release()


def test_process_crash_after_real_upsert_blocks_and_recovers(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.rag.sync import synchronize_scope, acquire_fresh_scopes
    monkeypatch.setenv("TEMP", str(tmp_path)); monkeypatch.setenv("TMP", str(tmp_path)); monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    db_path = tmp_path / "db"
    client = chromadb.PersistentClient(path=str(db_path))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    monkeypatch.setattr("laew.rag.knowledge_base.embedding_model_identity", lambda _service: "crash-test-identity")
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    note = project / "note.md"; note.write_text("Old text. " * 20, encoding="utf-8")
    class Embed:
        model = "crash-test"; dimensions = 3
        def embed_batch(self, texts): return [[1., 2., 3.] for _ in texts]
    cfg = {"enabled": True, "global_collection": "crash_global_test"}
    kb = KnowledgeBase(str(project), str(vault), Embed(), chunk_size=40, chunk_overlap=5, vector_store_config=cfg)
    synchronize_scope(kb, "project")
    note.write_text("Updated content after crash. " * 5, encoding="utf-8")
    script = '''
import sys,time,chromadb
import laew.rag.vector_store as vector_store
import laew.rag.knowledge_base as knowledge_base
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.sync import synchronize_scope
client=chromadb.PersistentClient(path=sys.argv[1]); vector_store._build_chroma_client=lambda *args: client
knowledge_base.embedding_model_identity=lambda _service: "crash-test-identity"
class Embed:
 model="crash-test"; dimensions=3
 def embed_batch(self,texts): return [[1.,2.,3.] for _ in texts]
kb=KnowledgeBase(sys.argv[2],sys.argv[3],Embed(),chunk_size=40,chunk_overlap=5,vector_store_config={"enabled":True,"global_collection":"crash_global_test"})
real=kb.project_store.add_chunks
def partial(chunks):
 real(chunks[:1]); print("upserted",flush=True); time.sleep(60)
kb.project_store.add_chunks=partial
synchronize_scope(kb,"project")
'''
    process = subprocess.Popen([sys.executable, "-c", script, str(db_path), str(project), str(vault)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        first_line = process.stdout.readline().strip()
        if first_line != "upserted":
            assert False, process.stderr.read()
        process.kill(); process.wait(timeout=5)
        locks, error = acquire_fresh_scopes(kb, ["project"])
        assert not locks and error
        synchronize_scope(kb, "project")
        locks, error = acquire_fresh_scopes(kb, ["project"])
        assert not error
        for lock in reversed(locks): lock.release()
        records = kb.project_store.sync_records("project")
        assert records and all("Old text" not in record.text for record in records)
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=5)


def test_different_projects_sync_concurrently_in_separate_processes(tmp_path, monkeypatch):
    import concurrent.futures
    pytest.importorskip("chromadb")
    monkeypatch.setenv("TEMP", str(tmp_path)); monkeypatch.setenv("TMP", str(tmp_path)); monkeypatch.setenv("TMPDIR", str(tmp_path))
    a = tmp_path / "a"; a.mkdir()
    b = tmp_path / "b"; b.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (a / "note.md").write_text("Project A", encoding="utf-8")
    (b / "note.md").write_text("Project B", encoding="utf-8")
    script = '''
import sys,chromadb
import laew.rag.vector_store as vs
from laew.rag.knowledge_base import KnowledgeBase
from laew.rag.sync import synchronize_scope
client=chromadb.PersistentClient(path=sys.argv[1]); vs._build_chroma_client=lambda *args: client
class Embed:
 model="parallel-model"; dimensions=3
 def embed_batch(self,texts):
  print("embedding",flush=True); sys.stdin.readline(); return [[1.,2.,3.] for _ in texts]
kb=KnowledgeBase(sys.argv[2],sys.argv[3],Embed(),vector_store_config={"enabled":True,"global_collection":"parallel_global_test"})
synchronize_scope(kb,"project",lock_timeout=15)
'''
    commands = [[sys.executable, "-c", script, str(tmp_path / "db"), str(project), str(vault)] for project in (a, b)]
    processes = [subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for command in commands]
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        futures = [executor.submit(process.stdout.readline) for process in processes]
        for future in futures:
            assert future.result(timeout=20).strip() == "embedding"
        for process in processes:
            process.stdin.write("continue\n"); process.stdin.flush()
        for process in processes:
            _, error = process.communicate(timeout=20)
            assert process.returncode == 0, error
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill(); process.wait(timeout=5)
        executor.shutdown(wait=True)
