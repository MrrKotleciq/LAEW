"""Tests for LAEW PathResolver (ADR-010 multi-root workspace)."""

from pathlib import Path

import pytest

from laew.security import PathResolver, PathResolverError


@pytest.fixture
def tmp_roots(tmp_path):
    """Create temporary directory structure for testing."""
    project_root = tmp_path / "projects" / "test-project"
    projects_root = tmp_path / "projects"
    knowledge_root = tmp_path / "KNOWLEDGE"

    project_root.mkdir(parents=True)
    projects_root.mkdir(parents=True, exist_ok=True)
    knowledge_root.mkdir(parents=True)

    # Create some test files
    (project_root / "README.md").write_text("# Test Project")
    (project_root / "docs").mkdir()
    (project_root / "docs" / "architecture.md").write_text("# Architecture")
    (knowledge_root / "AI").mkdir()
    (knowledge_root / "AI" / "RAG.md").write_text("# RAG Notes")

    return {
        "project": project_root,
        "projects": projects_root,
        "knowledge": knowledge_root,
    }


@pytest.fixture
def resolver(tmp_roots):
    """Create PathResolver with test roots."""
    return PathResolver(
        project_root=tmp_roots["project"],
        projects_root=tmp_roots["projects"],
        knowledge_root=tmp_roots["knowledge"],
    )


def test_resolver_initialization(resolver, tmp_roots):
    """Test that resolver initializes with correct roots."""
    assert resolver.project_root == tmp_roots["project"]
    assert resolver.projects_root == tmp_roots["projects"]
    assert resolver.knowledge_root == tmp_roots["knowledge"]


def test_resolve_project_alias(resolver, tmp_roots):
    """Test resolving @project alias."""
    resolved = resolver.resolve("@project/README.md")
    expected = tmp_roots["project"] / "README.md"
    assert resolved == expected


def test_resolve_knowledge_alias(resolver, tmp_roots):
    """Test resolving @knowledge alias."""
    resolved = resolver.resolve("@knowledge/AI/RAG.md")
    expected = tmp_roots["knowledge"] / "AI" / "RAG.md"
    assert resolved == expected


def test_resolve_projects_alias(resolver, tmp_roots):
    """Test resolving @projects alias."""
    resolved = resolver.resolve("@projects/test-project/README.md")
    expected = tmp_roots["projects"] / "test-project" / "README.md"
    assert resolved == expected


def test_resolve_unprefixed_defaults_to_project(resolver, tmp_roots):
    """Test that unprefixed paths default to @project."""
    resolved = resolver.resolve("docs/architecture.md")
    expected = tmp_roots["project"] / "docs" / "architecture.md"
    assert resolved == expected


def test_resolve_unknown_alias_raises_error(resolver):
    """Test that unknown alias raises PathResolverError."""
    with pytest.raises(PathResolverError, match="Unknown path alias"):
        resolver.resolve("@unknown/file.txt")


def test_path_traversal_escaping_root_blocked(resolver):
    """Test that path traversal escaping root boundary is blocked."""
    with pytest.raises(PathResolverError, match="Path traversal violation"):
        resolver.resolve("@project/../../../etc/passwd")


def test_path_traversal_within_root_allowed(resolver, tmp_roots):
    """Test that path traversal within root is allowed."""
    resolved = resolver.resolve("@project/docs/../README.md")
    expected = tmp_roots["project"] / "README.md"
    assert resolved == expected


def test_restricted_path_git_blocked(resolver, tmp_roots):
    """Test that .git directory access is blocked."""
    (tmp_roots["project"] / ".git").mkdir()
    with pytest.raises(PathResolverError, match="restricted path"):
        resolver.resolve("@project/.git/config")


def test_restricted_path_secrets_blocked(resolver, tmp_roots):
    """Test that secrets directory access is blocked."""
    (tmp_roots["project"] / "secrets").mkdir()
    with pytest.raises(PathResolverError, match="restricted path"):
        resolver.resolve("@project/secrets/api-key.txt")


def test_ignored_pattern_env_blocked(resolver, tmp_roots):
    """Test that .env files are blocked."""
    (tmp_roots["project"] / ".env").write_text("SECRET=value")
    with pytest.raises(PathResolverError, match="ignored pattern"):
        resolver.resolve("@project/.env")


def test_ignored_pattern_gguf_blocked(resolver, tmp_roots):
    """Test that .gguf model files are blocked."""
    (tmp_roots["project"] / "model.gguf").write_text("binary data")
    with pytest.raises(PathResolverError, match="ignored pattern"):
        resolver.resolve("@project/model.gguf")


def test_is_within_root_project(resolver, tmp_roots):
    """Test is_within_root for @project."""
    path = tmp_roots["project"] / "docs" / "file.md"
    assert resolver.is_within_root(path, "@project") is True
    assert resolver.is_within_root(path, "@knowledge") is False


def test_is_within_root_knowledge(resolver, tmp_roots):
    """Test is_within_root for @knowledge."""
    path = tmp_roots["knowledge"] / "AI" / "notes.md"
    assert resolver.is_within_root(path, "@knowledge") is True
    assert resolver.is_within_root(path, "@project") is False


def test_get_alias_for_path_project(resolver, tmp_roots):
    """Test get_alias_for_path returns @project."""
    path = tmp_roots["project"] / "README.md"
    assert resolver.get_alias_for_path(path) == "@project"


def test_get_alias_for_path_knowledge(resolver, tmp_roots):
    """Test get_alias_for_path returns @knowledge."""
    path = tmp_roots["knowledge"] / "AI" / "RAG.md"
    assert resolver.get_alias_for_path(path) == "@knowledge"


def test_get_alias_for_path_outside_all_roots(resolver, tmp_path):
    """Test get_alias_for_path returns None for unmapped paths."""
    path = tmp_path / "outside" / "file.txt"
    assert resolver.get_alias_for_path(path) is None


def test_default_initialization_uses_cwd():
    """Test that default initialization uses current working directory."""
    resolver = PathResolver()
    assert resolver.project_root == Path.cwd().resolve()
    assert resolver.projects_root == Path.cwd().parent.resolve()
