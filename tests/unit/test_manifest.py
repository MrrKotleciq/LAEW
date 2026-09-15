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


# --------------------------------------------------------------------------- #
# Provider timeout + type validation (Milestone 11: Phase 1c)
# --------------------------------------------------------------------------- #

_VALID_MANIFEST_YAML = (
    'version: "1.0"\n'
    'system_name: "LAEW"\n'
    'stage: "foundation"\n'
    "workspace:\n"
    '  root: "."\n'
    "  allowed_paths: []\n"
    "  restricted_paths: []\n"
    "  ignored_patterns: []\n"
    "models:\n"
    "  roles:\n"
    "    primary: {}\n"
    "    embedding: {}\n"
    "    reviewer: {}\n"
    "tools:\n"
    "  categories:\n"
    "    filesystem:\n"
    '      policy: "read_only_by_default"\n'
    "    git:\n"
    '      policy: "inspection_first"\n'
    "    terminal:\n"
    '      policy: "safe_command_allowlist"\n'
    '      allowlist:\n'
    '        - "ls"\n'
    '        - "git status"\n'
    '        - "git diff"\n'
    "    web:\n"
    '      policy: "read_only"\n'
    "memory:\n"
    "  session: {}\n"
    "  second_brain: {}\n"
    "rag:\n"
    "  pipeline: {}\n"
)


def _manifest_with_agent(providers_yaml: str) -> str:
    """Build a full manifest YAML with a custom agent.llm.providers block."""
    return (
        _VALID_MANIFEST_YAML
        + "agent:\n  llm:\n    providers:\n"
        + providers_yaml
        + "    retry:\n"
        "      max_attempts: 3\n"
        "      backoff_base_ms: 1000\n"
        "      max_backoff_ms: 5000\n"
    )


def test_provider_timeout_positive_int_accepted(tmp_path):
    """A provider with a positive-integer timeout is accepted."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "ollama"\n'
        '        type: "ollama"\n'
        "        timeout: 300\n"
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    manifest = load_manifest(manifest_path)
    provider = manifest["agent"]["llm"]["providers"][0]
    assert provider["timeout"] == 300


def test_provider_timeout_zero_rejected(tmp_path):
    """A provider with timeout=0 is rejected (must be positive)."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "ollama"\n'
        '        type: "ollama"\n'
        "        timeout: 0\n"
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    with pytest.raises(ManifestError, match="timeout"):
        load_manifest(manifest_path)


def test_provider_timeout_negative_rejected(tmp_path):
    """A provider with a negative timeout is rejected."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "ollama"\n'
        '        type: "ollama"\n'
        "        timeout: -10\n"
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    with pytest.raises(ManifestError, match="timeout"):
        load_manifest(manifest_path)


def test_provider_timeout_non_int_rejected(tmp_path):
    """A provider with a non-integer timeout is rejected."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "ollama"\n'
        '        type: "ollama"\n'
        '        timeout: "long"\n'
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    with pytest.raises(ManifestError, match="timeout"):
        load_manifest(manifest_path)


def test_provider_missing_type_rejected(tmp_path):
    """A provider entry without a 'type' field is rejected."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "unnamed"\n'
        '        model: "llama3.1"\n'
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    with pytest.raises(ManifestError, match="type"):
        load_manifest(manifest_path)


def test_provider_type_must_be_nonempty(tmp_path):
    """A provider entry with an empty 'type' is rejected."""
    manifest_path = tmp_path / "manifest.yaml"
    providers = (
        '      - name: "empty"\n'
        '        type: ""\n'
    )
    manifest_path.write_text(_manifest_with_agent(providers), encoding="utf-8")
    with pytest.raises(ManifestError, match="type"):
        load_manifest(manifest_path)