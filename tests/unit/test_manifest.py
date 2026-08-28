from pathlib import Path

import pytest

from laew.manifest import ManifestError, load_manifest


MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "manifests"
    / "SYSTEM_MANIFEST.yaml"
)


def test_load_manifest():
    manifest = load_manifest(MANIFEST_PATH)

    assert isinstance(manifest, dict)
    assert manifest["version"] == "1.0"
    assert manifest["system_name"] == "LAEW"


def test_missing_manifest():
    missing_path = MANIFEST_PATH.parent / "does-not-exist.yaml"

    with pytest.raises(ManifestError):
        load_manifest(missing_path)


def test_missing_required_key(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="missing required"):
        load_manifest(manifest_path)


def test_invalid_mapping_type(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace: []
models: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="workspace"):
        load_manifest(manifest_path)

def test_workspace_requires_expected_fields(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
models: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="workspace"):
        load_manifest(manifest_path)


def test_workspace_fields_must_have_correct_types(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: 123
  allowed_paths: "docs"
  restricted_paths: []
  ignored_patterns: []
models: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="workspace.root"):
        load_manifest(manifest_path)

def test_models_requires_roles(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="models.roles"):
        load_manifest(manifest_path)


def test_models_roles_require_primary_embedding_reviewer(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="models.roles"):
        load_manifest(manifest_path)


def test_models_roles_must_be_mappings(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: []
    embedding: {}
    reviewer: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="models.roles.primary"):
        load_manifest(manifest_path)

def test_tools_requires_categories(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="tools.categories"):
        load_manifest(manifest_path)


def test_tools_categories_require_expected_tools(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="tools.categories"):
        load_manifest(manifest_path)


def test_tools_categories_must_be_mappings(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: []
    git: {}
    terminal: {}
    web: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="tools.categories.filesystem"):
        load_manifest(manifest_path)

def test_memory_requires_session_and_second_brain(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
    git: {}
    terminal: {}
    web: {}
memory: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="memory"):
        load_manifest(manifest_path)


def test_memory_requires_second_brain_configuration(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
    git: {}
    terminal: {}
    web: {}
memory:
  session: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="memory.second_brain"):
        load_manifest(manifest_path)


def test_rag_requires_pipeline(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
    git: {}
    terminal: {}
    web: {}
memory:
  session: {}
  second_brain: {}
rag: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="rag.pipeline"):
        load_manifest(manifest_path)


def test_rag_pipeline_must_be_mapping(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
    git: {}
    terminal: {}
    web: {}
memory:
  session: {}
  second_brain: {}
rag:
  pipeline: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="rag.pipeline"):
        load_manifest(manifest_path)

def test_tool_category_requires_policy(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem: {}
    git: {}
    terminal: {}
    web: {}
memory:
  session: {}
  second_brain: {}
rag:
  pipeline: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="policy"):
        load_manifest(manifest_path)


def test_tool_category_policy_must_be_string(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem:
      policy: []
    git:
      policy: "inspection_first"
    terminal:
      policy: "safe_command_allowlist"
    web:
      policy: "read_only"
memory:
  session: {}
  second_brain: {}
rag:
  pipeline: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ManifestError,
        match="tools.categories.filesystem.policy",
    ):
        load_manifest(manifest_path)


def test_tool_category_policy_values_must_be_known(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem:
      policy: "invalid_policy"
    git:
      policy: "inspection_first"
    terminal:
      policy: "safe_command_allowlist"
    web:
      policy: "read_only"
memory:
  session: {}
  second_brain: {}
rag:
  pipeline: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ManifestError,
        match="invalid policy",
    ):
        load_manifest(manifest_path)


def test_terminal_allowlist_must_be_list(tmp_path):
    manifest_path = tmp_path / "manifest.yaml"

    manifest_path.write_text(
        """
version: "1.0"
system_name: "LAEW"
stage: "foundation"
workspace:
  root: "."
  allowed_paths: []
  restricted_paths: []
  ignored_patterns: []
models:
  roles:
    primary: {}
    embedding: {}
    reviewer: {}
tools:
  categories:
    filesystem:
      policy: "read_only_by_default"
    git:
      policy: "inspection_first"
    terminal:
      policy: "safe_command_allowlist"
      allowlist: "ls"
    web:
      policy: "read_only"
memory:
  session: {}
  second_brain: {}
rag:
  pipeline: {}
""",
        encoding="utf-8",
    )

    with pytest.raises(
        ManifestError,
        match="terminal.allowlist",
    ):
        load_manifest(manifest_path)