"""Pin existing path resolution with disposable, non-writing fixtures."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from laew.console.session_store import conversation_store_from_manifest, session_store_from_manifest
from laew.knowledge.integration import build_knowledge
from laew.manifest import load_manifest
from laew.memory.integration import build_memory
from laew.rag.config import manifest_base_dir, resolve_knowledge_root, resolve_project_root
from laew.settings import settings_path
from laew.web import resolve_workspace_root


@pytest.fixture
def fixture_manifest(tmp_path):
    shipped = Path(__file__).resolve().parents[2] / "manifests" / "SYSTEM_MANIFEST.yaml"
    manifest = load_manifest(shipped)
    manifest["workspace"]["root"] = "."
    manifest["memory"]["session"]["storage"] = "runtime/sessions"
    manifest["memory"]["second_brain"]["path"] = "@knowledge"
    path = tmp_path / "installation" / "manifests" / "SYSTEM_MANIFEST.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return path


def test_named_sessions_follow_launch_directory_while_conversations_follow_absolute_manifest(
    tmp_path, monkeypatch, fixture_manifest
):
    manifest = load_manifest(fixture_manifest)
    installation = fixture_manifest.parent.parent
    for launcher in (tmp_path / "console", tmp_path / "workbench"):
        launcher.mkdir()
        monkeypatch.chdir(launcher)
        base = manifest_base_dir(fixture_manifest)
        assert resolve_project_root(manifest, base_dir=base) == installation
        named = session_store_from_manifest(manifest).directory.resolve()
        conversations = conversation_store_from_manifest(manifest, fixture_manifest).directory
        assert named == launcher / "runtime" / "sessions"
        assert conversations == installation / "runtime" / "sessions"
        assert settings_path(manifest, fixture_manifest) == conversations.parent / "settings.json"
        assert not named.exists()
        assert not conversations.exists()


@pytest.mark.parametrize("vault_name", ["Knowledge", "KNOWLEDGE"])
def test_explicit_vault_mapping_and_sqlite_overrides(tmp_path, monkeypatch, fixture_manifest, vault_name):
    workspace = tmp_path / "workspace"
    projects = workspace / "Projects"
    vault = workspace / vault_name
    launcher = tmp_path / "launcher"
    for root in (projects, vault, launcher):
        root.mkdir(parents=True)
    monkeypatch.chdir(launcher)
    monkeypatch.setenv("LAEW_WORKSPACE_ROOT", str(workspace))
    manifest = load_manifest(fixture_manifest)
    conversations = conversation_store_from_manifest(manifest, fixture_manifest)
    assert resolve_workspace_root() == workspace
    assert resolve_knowledge_root(
        manifest, project_root=None, projects_root=projects, knowledge_root=vault
    ) == vault

    # Capture factory paths before either constructor can create or migrate a database.
    monkeypatch.setattr("laew.memory.integration.MemoryStore", lambda path: SimpleNamespace(path=path))
    monkeypatch.setattr("laew.knowledge.service.KnowledgeCurationService", lambda path, *args, **kwargs: path)

    def database_paths():
        return (
            build_memory(manifest, fixture_manifest).store.path.resolve(),
            build_knowledge(
                manifest, conversations, projects_root=projects, knowledge_root=vault,
                broker_factory=None, sync_callback=None,
            ).resolve(),
        )

    monkeypatch.delenv("LAEW_MEMORY_STORAGE")
    monkeypatch.delenv("LAEW_KNOWLEDGE_STORAGE")
    runtime = conversations.directory.parent
    assert database_paths() == (runtime / "memory" / "memory.db", runtime / "knowledge" / "curation.db")

    curation_override = tmp_path / "overrides" / "curation.db"
    monkeypatch.setenv("LAEW_MEMORY_STORAGE", "overrides/memory.db")
    monkeypatch.setenv("LAEW_KNOWLEDGE_STORAGE", str(curation_override))
    assert database_paths() == (launcher / "overrides" / "memory.db", curation_override)
    assert not runtime.exists()
    assert not (launcher / "overrides").exists()
    assert not curation_override.parent.exists()
