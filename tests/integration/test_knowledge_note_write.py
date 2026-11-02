"""Knowledge edits require a one-time broker grant and preserve note integrity."""

import hashlib
import pytest

from laew.security.path_resolver import PathResolver
from laew.security.permissions import PermissionBroker
from laew.tools.filesystem import FilesystemTool
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool


def test_approved_create_update_and_denial(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (vault / "topics").mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=1)
    content = "---\ntype: docs\nscope: global\nstatus: active\n---\n# Notatka\n[[Inna]]\n"
    args = {"file_path": "@knowledge/topics/note.md", "content": content, "expected_sha256": ""}
    assert not tool.call("write_knowledge_note", **args).success
    assert not broker.call(tool, "write_knowledge_note", args, None).success
    def approve(event):
        if event["type"] == "approval":
            assert not event["allow_session"]
            assert broker.decide(event["id"], "allow", "s")
    assert broker.call(tool, "write_knowledge_note", args, approve, "s").success
    path = vault / "topics/note.md"
    assert path.read_text(encoding="utf-8") == content
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    args.update(file_path=str(path), content=content + "Nowa treść.\n", expected_sha256=digest)
    assert broker.call(tool, "write_knowledge_note", args, approve, "s").success
    assert not broker.call(tool, "write_knowledge_note", args, approve, "s").success
    args.update(content=content.replace("[[Inna]]", ""), expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert not broker.call(tool, "write_knowledge_note", args, approve, "s").success
    assert not broker.call(tool, "write_knowledge_note", {**args, "file_path": "@knowledge/.obsidian/a.md"}, approve, "s").success
    assert not broker.call(tool, "write_knowledge_note", {**args, "file_path": str(project / "escape.md")}, approve, "s").success
    restricted = PermissionBroker(project, "restricted", timeout=.01)
    assert not restricted.call(tool, "write_knowledge_note", args, approve, "s").success


def test_explicit_denial_and_timeout(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=.01)
    args = {"file_path": "@knowledge/a.md", "content": "---\ntype: docs\nscope: global\n---\n# A\n", "expected_sha256": ""}
    def deny(event):
        if event["type"] == "approval": broker.decide(event["id"], "deny", "s")
    assert not broker.call(tool, "write_knowledge_note", args, deny, "s").success
    assert not broker.call(tool, "write_knowledge_note", args, lambda event: None, "s").success
    assert not (vault / "a.md").exists()


def test_write_sync_and_retrieve_in_isolated_chroma(tmp_path, monkeypatch):
    chromadb = pytest.importorskip("chromadb")
    client = chromadb.PersistentClient(path=str(tmp_path / "isolated-db"))
    monkeypatch.setattr("laew.rag.vector_store._build_chroma_client", lambda *args: client)

    class Embedding:
        model = "isolated-knowledge-write"
        dimensions = 2
        def embed(self, text):
            return [1.0, 0.0] if "unikatowy-znacznik" in text else [0.0, 1.0]
        def embed_batch(self, texts):
            return [self.embed(text) for text in texts]

    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    (vault / "profile").mkdir()
    (vault / "inbox").mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=1)
    def approve(event):
        if event["type"] == "approval":
            assert broker.decide(event["id"], "allow", "s")
    content = "---\ntype: docs\nscope: global\n---\n# Test\nunikatowy-znacznik fikcyjny\n"
    for path in ("@knowledge/profile/test.md", "@knowledge/inbox/test.md"):
        assert broker.call(tool, "write_knowledge_note", {"file_path": path, "content": content,
                           "expected_sha256": ""}, approve, "s").success
    rag = build_rag_tool({"rag": {"vector_store": {"enabled": True,
                         "global_collection": "isolated_write_test"}}}, project_root=project,
                         knowledge_root=vault, embedding_service=Embedding())
    synchronize_scope(rag._pipeline.knowledge_base, "global")
    result = rag.call("query", query="unikatowy-znacznik", scope="global")
    assert result.success
    assert "@knowledge/profile/test.md" in result.data["sources"]
    assert "@knowledge/inbox/test.md" not in result.data["sources"]


def test_rejects_invalid_metadata_and_hidden_paths(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=1)
    def approve(event):
        if event["type"] == "approval": broker.decide(event["id"], "allow", "s")
    def write(path, content):
        return broker.call(tool, "write_knowledge_note", {"file_path": path, "content": content,
                           "expected_sha256": ""}, approve, "s")
    assert not write("@knowledge/a.md", "---\ntype: [\n---\nsecret fixture").success
    assert not write("@knowledge/a.md", "---\ntype: docs\nscope: project\n---\n").success
    assert not write("@knowledge/.smart-env/a.md", "fixture").success


def test_rejects_linked_paths(tmp_path):
    project = tmp_path / "project"; project.mkdir()
    vault = tmp_path / "vault"; vault.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    tool = FilesystemTool(PathResolver(project_root=project, knowledge_root=vault))
    broker = PermissionBroker(project, "auto", timeout=1)
    try:
        (vault / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks requires platform privileges")
    result = broker.call(tool, "write_knowledge_note", {"file_path": "@knowledge/linked/a.md",
                         "content": "---\ntype: docs\nscope: global\n---\n",
                         "expected_sha256": ""}, None)
    assert not result.success
    assert not (outside / "a.md").exists()
