"""Global non-knowledge folders are excluded across ingestion and reconciliation."""

import json
import os
import subprocess
import sys

import pytest

from laew.rag.config import manifest_global_exclusions
from laew.rag.knowledge_base import KnowledgeBase
from laew.runtime import build_rag_tool
from laew.console.commands.rag import _manifest_rag_config
from types import SimpleNamespace


class Embedding:
    model = "vault-selection-test"
    dimensions = 3

    def __init__(self):
        self.calls = 0

    def embed(self, text):
        return [1.0, 2.0, 3.0]

    def embed_batch(self, texts):
        self.calls += len(texts)
        return [self.embed(text) for text in texts]


def write(root, relative, text="isolated fixture"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paths(kb):
    return {r.file_path.replace("\\", "/") for r in kb.global_store.sync_records("global")}


def test_initial_and_incremental_global_selection(tmp_path):
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    expected = {"README.md", "topics/ai/note.md", "research/draft.md", "decisions/policy.md", "profile/preferences.md"}
    for path in expected:
        write(vault, path)
    for path in ("inbox/raw.md", "inbox/nested/raw.md", "templates/note.md",
                 "Templates/legacy.md", "assets/attachment.md", "backups/copy.md",
                 "temp/scratch.md", ".obsidian/settings.md", ".smart-env/cache.md",
                 "topics/cache.tmp.md", "copy.bak.md"):
        write(vault, path)
    write(project, "inbox/project-note.md")
    embedding = Embedding()
    kb = KnowledgeBase(str(project), str(vault), embedding)
    kb.load_vault()
    assert paths(kb) == expected
    kb.load_project()
    assert kb.project_store.count() == 1  # global exclusions do not constrain project layout
    write(vault, "inbox/later.md")
    kb.synchronize(scope="global")
    assert paths(kb) == expected
    note = vault / "inbox/raw.md"
    note.rename(vault / "topics/promoted.md")
    changes = kb.synchronize(scope="global")
    assert changes["global"]["added"]["documents"] == 1
    assert "topics/promoted.md" in paths(kb)
    (vault / "topics/promoted.md").rename(vault / "inbox/returned.md")
    changes = kb.synchronize(scope="global")
    assert changes["global"]["removed"]["documents"] == 1
    assert paths(kb) == expected
    old = write(vault, "topics/legacy.md")
    kb.synchronize(scope="global")
    (vault / "topics/moved").mkdir()
    old.rename(vault / "topics/moved/legacy.md")
    kb.synchronize(scope="global")
    assert "topics/legacy.md" not in paths(kb)
    assert "topics/moved/legacy.md" in paths(kb)
    calls = embedding.calls
    kb.synchronize(scope="global")
    assert embedding.calls == calls


def test_persistent_restart_and_previously_indexed_template_cleanup(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    write(vault, "topics/active.md")
    for key in ("TEMP", "TMP", "TMPDIR"):
        monkeypatch.setenv(key, str(tmp_path))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    client = chromadb.PersistentClient(path=str(tmp_path / "db"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)
    cfg = {"enabled": True, "host": "test-vault", "port": 1,
           "global_collection": "isolated_vault_selection"}
    kb = KnowledgeBase(str(project), str(vault), Embedding(), vector_store_config=cfg)
    kb.synchronize(scope="global")
    # Simulate a legacy indexed template without changing the new default policy.
    template = write(vault, "templates/old.md")
    kb.global_store.add_chunks(kb._load_file(template, "global", vault))
    (vault / "topics/active.md").rename(vault / "inbox-temp.md")
    (vault / "inbox").mkdir()
    (vault / "inbox-temp.md").rename(vault / "inbox/active.md")
    script = '''
import json,sys,chromadb
import laew.rag.vector_store as store
import laew.rag.knowledge_base as knowledge
from laew.rag.knowledge_base import KnowledgeBase
class Embedding:
 model="vault-selection-test"; dimensions=3
 def embed_batch(self,texts): return [[1.,2.,3.] for _ in texts]
client=chromadb.PersistentClient(path=sys.argv[1])
store._build_chroma_client=lambda *args: client
knowledge.embedding_model_identity=lambda _: sys.argv[5]
kb=KnowledgeBase(sys.argv[2],sys.argv[3],Embedding(),vector_store_config=json.loads(sys.argv[4]))
result=kb.synchronize(scope="global")
assert kb.global_store.count()==0, kb.global_store.sync_records("global")
print("excluded-after-restart")
'''
    # The subprocess fixture represents the same model despite a different Python module name.
    process = subprocess.run([sys.executable, "-c", script, str(tmp_path / "db"), str(project), str(vault), json.dumps(cfg), kb.embedding_model_id],
                             capture_output=True, text=True, timeout=40,
                             **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
    assert process.returncode == 0, process.stderr
    assert "excluded-after-restart" in process.stdout
    assert kb.global_store.count() == 0


def test_custom_exclusions_reach_runtime_and_console(tmp_path):
    project, vault = tmp_path / "project", tmp_path / "vault"
    project.mkdir()
    vault.mkdir()
    for path in ("private/raw.md", "research/visible.md", "inbox/raw.md"):
        write(vault, path)
    manifest = {"workspace": {"root": str(project)}, "rag": {
        "global_sources": {"exclude_patterns": ["private/**"]}, "vector_store": {"enabled": False}}}
    tool = build_rag_tool(manifest, project_root=project, knowledge_root=vault, embedding_service=Embedding())
    kb = tool._pipeline.knowledge_base
    kb.load_vault()
    assert paths(kb) == {"research/visible.md"}
    cfg = _manifest_rag_config(manifest, SimpleNamespace(manifest_path=tmp_path / "manifest.yaml"))
    assert "private/**" in cfg["global_source_exclusions"]
    assert "inbox/**" in cfg["global_source_exclusions"]


@pytest.mark.parametrize("value", ["inbox/**", [None], ["../outside/**"], ["/outside/**"], ["C:/outside/**"], ["a\\b/**"]])
def test_invalid_global_exclusion_configuration_fails(value):
    with pytest.raises(ValueError, match="exclusions"):
        manifest_global_exclusions({"rag": {"global_sources": {"exclude_patterns": value}}})
