"""Non-code projects use ordinary workspace discovery and scoped RAG."""

import json
from types import SimpleNamespace

import pytest

from laew.project_config import load_project_settings, save_project_settings
from laew.rag.identity import project_collection_name
from laew.rag.sync import synchronize_scope
from laew.runtime import build_rag_tool
from laew.web import WorkspaceService


class TopicEmbedding:
    """Deterministic topic vectors; these tests do not measure model quality."""

    model = "academic-fixture"
    dimensions = 4

    def __init__(self):
        self.calls = 0

    def embed(self, text):
        return [float(word in text.lower()) for word in ("pid", "matrix", "logic", "shared")]

    def embed_batch(self, texts):
        self.calls += len(texts)
        return [self.embed(text) for text in texts]


@pytest.mark.parametrize("patterns", [None, [], "docs/*.md", [1], ["../private.md"],
                                    ["/private.md"], ["C:/private.md"], ["docs\\a.md"],
                                    ["docs/./a.md"], ["docs//a.md"], ["resources/*.pdf"]])
def test_invalid_sources_fail_before_settings_write(tmp_path, patterns):
    with pytest.raises(ValueError, match="rag_source_allowlist"):
        save_project_settings(tmp_path, {"rag_source_allowlist": patterns})
    assert not (tmp_path / ".laew-project.json").exists()
    (tmp_path / ".laew-project.json").write_text(
        json.dumps({"rag_source_allowlist": patterns}), encoding="utf-8")
    with pytest.raises(ValueError, match="rag_source_allowlist"):
        load_project_settings(tmp_path)


def test_academic_hierarchy_sync_scope_and_workspace(tmp_path):
    projects = tmp_path / "Projects"
    study = projects / "Studia"
    other = projects / "Other"
    vault = tmp_path / "Knowledge"
    for root in (study, other, vault):
        root.mkdir(parents=True)
    save_project_settings(study, {"documentation_language": "pl",
                                 "rag_source_allowlist": ["README.md", "docs/*.md"]})
    # Clearly fictional topics and markers only in this isolated fixture.
    paths = ["docs/semestr-01/control/note.md", "docs/semestr-01/algebra/note.md",
             "docs/semestr-02/digital/note.md"]
    for path, topic in zip(paths, ("pid", "matrix", "logic")):
        file = study / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("---\nname: Fictional fixture\ntype: docs\nscope: project\n"
                        "semester: 1\nsubject: fixture\ntags: [fixture]\n---\n"
                        f"# Fictional {topic}\n{topic} fixture only. "
                        "[[docs/semestr-01/algebra/note]]\n", encoding="utf-8")
    for path in ("templates/note.md", "resources/attachment.md", ".obsidian/private.md"):
        file = study / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("pid excluded fixture", encoding="utf-8")
    (study / "docs/handout.pdf").write_bytes(b"fixture, not a real PDF")
    (other / "README.md").write_text("pid OTHER-ONLY", encoding="utf-8")
    (vault / "shared.md").write_text("# Shared\nshared knowledge", encoding="utf-8")
    manifest = {"rag": {"project_sources": {"allowlist": ["README.md"]},
                        "vector_store": {"enabled": False}}}
    from laew.console.commands.rag import _manifest_rag_config

    console_manifest = {**manifest, "workspace": {"root": str(study)}}
    cfg = _manifest_rag_config(console_manifest, SimpleNamespace(manifest_path=tmp_path / "manifest.yaml"))
    assert cfg["project_source_allowlist"] == ["README.md", "docs/*.md"]
    embedding = TopicEmbedding()
    tool = build_rag_tool(manifest, project_root=study, knowledge_root=vault,
                          embedding_service=embedding)
    kb = tool._pipeline.knowledge_base
    synchronize_scope(kb, "project")
    synchronize_scope(kb, "global")
    records = kb.project_store.sync_records("project")
    assert {r.file_path.replace("\\", "/") for r in records} == set(paths)
    assert len({r.chunk_id for r in records}) == len(records)
    assert all("semester:" not in r.text and "semester" not in r.metadata for r in records)
    assert all(r.metadata["tags"] == ["fixture"] and r.metadata["backlinks"] for r in records)
    for path, topic in zip(paths, ("pid", "matrix", "logic")):
        result = tool.call("query", query=topic, scope="project")
        assert result.success and result.data["sources"] == ["@project/" + path]
        assert "OTHER-ONLY" not in result.data["context"]
    hybrid = tool.call("query", query="pid shared", scope="hybrid")
    assert hybrid.success
    assert set(hybrid.data["sources"]) == {"@project/" + paths[0], "@knowledge/shared.md"}
    previous_calls = embedding.calls
    unchanged = synchronize_scope(kb, "project")
    assert embedding.calls == previous_calls
    assert unchanged["project"]["unchanged"]["documents"] == 3
    (study / paths[0]).write_text("# Updated pid\npid UPDATED-FIXTURE", encoding="utf-8")
    synchronize_scope(kb, "project")
    assert "UPDATED-FIXTURE" in tool.call("query", query="pid", scope="project").data["context"]
    (study / paths[0]).unlink()
    synchronize_scope(kb, "project")
    assert not tool.call("query", query="pid", scope="project").data["sources"]
    other_tool = build_rag_tool(manifest, project_root=other, knowledge_root=vault,
                                embedding_service=TopicEmbedding())
    assert other_tool._pipeline.knowledge_base.project_source_allowlist == ("README.md",)
    synchronize_scope(other_tool._pipeline.knowledge_base, "project")
    assert "UPDATED-FIXTURE" not in other_tool.call("query", query="pid", scope="project").data["context"]
    assert project_collection_name(study) != project_collection_name(other)
    service = WorkspaceService(tmp_path / "manifest.yaml", other, projects, tmp_path)
    try:
        project = next(p for p in service.list_projects()["projects"] if p["name"] == "Studia")
        assert service.select_project(project["id"])[0] == 200
        assert service.project_settings()[1]["documentation_language"] == "pl"
        assert not (study / ".git").exists()
    finally:
        service.close()
