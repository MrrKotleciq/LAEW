"""Trusted manifest path resolution for the M17 global knowledge vault."""

from pathlib import Path

import pytest

from laew.rag.config import resolve_knowledge_root, resolve_project_root
from laew.security.path_resolver import PathResolver, PathResolverError


def test_legacy_knowledge_path_resolves_to_shared_vault(tmp_path):
    project = tmp_path / "Projects" / "LAEW"
    project.mkdir(parents=True)
    vault = tmp_path / "Knowledge"
    manifest = {"memory": {"second_brain": {"path": "knowledge"}}}

    assert resolve_knowledge_root(
        manifest,
        project_root=project,
        projects_root=project.parent,
        knowledge_root=vault,
    ) == vault.resolve()


@pytest.mark.parametrize("configured", ["@knowledge/Research", "Research"])
def test_knowledge_alias_and_relative_subdir_stay_in_trusted_vault(tmp_path, configured):
    project = tmp_path / "Projects" / "LAEW"
    project.mkdir(parents=True)
    vault = tmp_path / "Knowledge"
    manifest = {"memory": {"second_brain": {"path": configured}}}

    assert resolve_knowledge_root(
        manifest,
        project_root=project,
        projects_root=project.parent,
        knowledge_root=vault,
    ) == (vault / "Research").resolve()


@pytest.mark.parametrize("configured", ["@knowledge/../../outside", "../outside"])
def test_knowledge_path_traversal_is_rejected(tmp_path, configured):
    project = tmp_path / "Projects" / "LAEW"
    project.mkdir(parents=True)
    manifest = {"memory": {"second_brain": {"path": configured}}}

    with pytest.raises(PathResolverError):
        resolve_knowledge_root(
            manifest,
            project_root=project,
            projects_root=project.parent,
            knowledge_root=tmp_path / "Knowledge",
        )


def test_absolute_knowledge_path_must_be_inside_configured_vault(tmp_path):
    project = tmp_path / "Projects" / "LAEW"
    project.mkdir(parents=True)
    outside = tmp_path / "secret-notes"
    manifest = {"memory": {"second_brain": {"path": str(outside)}}}

    with pytest.raises(ValueError, match="inside @knowledge"):
        resolve_knowledge_root(
            manifest,
            project_root=project,
            projects_root=project.parent,
            knowledge_root=tmp_path / "Knowledge",
        )


def test_project_root_anchors_relative_manifest_root(tmp_path):
    project = tmp_path / "LAEW"
    manifest = {"workspace": {"root": "LAEW"}}

    assert resolve_project_root(manifest, base_dir=tmp_path) == project.resolve()


def test_default_aliases_match_nested_project_and_sibling_global_vault(tmp_path):
    """A project-local Knowledge folder remains under @project; global stays sibling."""
    project = tmp_path / "Projects" / "LAEW"
    local = project / "Knowledge"
    global_vault = tmp_path / "Knowledge"
    local.mkdir(parents=True)
    global_vault.mkdir()

    resolver = PathResolver(project_root=project, projects_root=project.parent)
    assert resolver.resolve("@project/Knowledge") == local.resolve()
    assert resolver.resolve("@knowledge") == global_vault.resolve()
    assert resolve_knowledge_root(
        {"memory": {"second_brain": {"path": "@knowledge"}}},
        project_root=project,
        projects_root=project.parent,
    ) == global_vault.resolve()
