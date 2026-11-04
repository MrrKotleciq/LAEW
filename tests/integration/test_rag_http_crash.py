"""Crash recovery against a disposable Chroma HTTP server."""

import json
import concurrent.futures
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests


@pytest.mark.integration
def test_partial_http_upsert_crash_recovery(tmp_path, monkeypatch):
    pytest.importorskip("chromadb")
    from laew.rag.knowledge_base import KnowledgeBase
    from laew.rag.sync import synchronize_scope, acquire_fresh_scopes, _process_lock

    for key in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(key, str(tmp_path))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    monkeypatch.setattr("laew.rag.knowledge_base.embedding_model_identity", lambda _: "http-crash-test")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if port in (8000, 8080, 8081, 8765):
        pytest.skip("Reserved service port selected")
    # Invoke the installed package rather than assuming a console script beside Python.
    executable = [sys.executable, "-c", "import sys; from chromadb.cli.cli import app; sys.argv[0]='chroma'; app()"]
    server = subprocess.Popen([*executable, "run", "--host", "127.0.0.1", "--port", str(port),
                               "--path", str(tmp_path / "db")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    child = None
    try:
        for _ in range(150):
            if server.poll() is not None:
                pytest.fail("Disposable Chroma server exited during startup")
            try:
                if requests.get(f"http://127.0.0.1:{port}/api/v2/heartbeat", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(.2)
        else:
            pytest.fail("Disposable Chroma server did not start")
        project = tmp_path / "project"; project.mkdir()
        vault = tmp_path / "vault"; vault.mkdir()
        note = project / "note.md"; note.write_text("Old text. " * 20, encoding="utf-8")
        class Embed:
            model = "crash-test"; dimensions = 3
            def __init__(self): self.calls = 0
            def embed_batch(self, texts):
                self.calls += len(texts)
                return [[1., 2., 3.] for _ in texts]
            def embed(self, text): return [1., 2., 3.]
        embed = Embed()
        config = {"enabled": True, "host": "127.0.0.1", "port": port, "global_collection": "http_crash_global"}
        kb = KnowledgeBase(str(project), str(vault), embed, chunk_size=40, chunk_overlap=5, vector_store_config=config)
        synchronize_scope(kb, "project")
        note.write_text("Updated content after crash. " * 5, encoding="utf-8")
        script = r'''
import json,sys
from laew.rag.knowledge_base import KnowledgeBase
import laew.rag.knowledge_base as module
from laew.rag.sync import synchronize_scope
module.embedding_model_identity=lambda _: "http-crash-test"
class Embed:
 model="crash-test"; dimensions=3
 def embed_batch(self,texts): return [[1.,2.,3.] for _ in texts]
kb=KnowledgeBase(sys.argv[1],sys.argv[2],Embed(),chunk_size=40,chunk_overlap=5,vector_store_config=json.loads(sys.argv[3]))
real=kb.project_store.add_chunks
def partial(chunks):
 real(chunks[:1]); print("upserted",flush=True); sys.stdin.readline()
kb.project_store.add_chunks=partial
synchronize_scope(kb,"project")
'''
        child = subprocess.Popen([sys.executable, "-c", script, str(project), str(vault), json.dumps(config)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(child.stdout.readline)
            try:
                signal = future.result(timeout=30).strip()
            except concurrent.futures.TimeoutError:
                child.kill(); child.wait(timeout=10)
                raise AssertionError("Synchronizer did not confirm its partial HTTP upsert")
        assert signal == "upserted", child.stderr.read() if child.poll() is not None else "No upsert signal"
        child.kill(); child.wait(timeout=10)
        records = kb.project_store.sync_records("project")
        assert any("Updated" in record.text for record in records)
        assert any("Old text" in record.text for record in records)
        lock = _process_lock(kb, "project", timeout=2).acquire()
        try: assert lock.read_state()["state"] == "incomplete"
        finally: lock.release()
        locks, error = acquire_fresh_scopes(kb, ["project"])
        assert not locks and error
        synchronize_scope(kb, "project")
        records = kb.project_store.sync_records("project")
        assert records and all("Old text" not in record.text for record in records)
        assert all("Updated" in record.text for record in records)
        expected = kb._load_file(note, "project", project, embed=False)
        assert {(r.chunk_id, r.text) for r in records} == {(r.chunk_id, r.text) for r in expected}
        calls = embed.calls
        synchronize_scope(kb, "project")
        assert embed.calls == calls
        locks, error = acquire_fresh_scopes(kb, ["project"])
        assert not error
        for lock in reversed(locks): lock.release()
        assert kb.project_store.search([1., 2., 3.], top_k=1, source_filter="project")
    finally:
        if child is not None and child.poll() is None:
            child.kill(); child.wait(timeout=10)
        server.terminate()
        try: server.wait(timeout=10)
        except subprocess.TimeoutExpired: server.kill(); server.wait(timeout=10)
