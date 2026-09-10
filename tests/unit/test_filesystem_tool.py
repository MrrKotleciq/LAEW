"""Tests for LAEW FilesystemTool (CONTRACT.md v1.1)."""

from pathlib import Path

import pytest

from laew.security import PathResolver
from laew.tools.base import ErrorCode
from laew.tools.filesystem import FilesystemTool


@pytest.fixture
def tmp_project(tmp_path):
    """Create temporary project structure."""
    project = tmp_path / "projects" / "test-project"
    project.mkdir(parents=True)

    # Create files
    (project / "README.md").write_text("# Test Project\n\nThis is a test.")
    (project / "src").mkdir()
    (project / "src" / "main.py").write_text("def main():\n    print('hello')\n")
    (project / "src" / "utils.py").write_text("def helper():\n    return 42\n")
    (project / "docs").mkdir()
    (project / "docs" / "guide.md").write_text("# Guide\n\nUser guide.")

    return project


@pytest.fixture
def resolver(tmp_project):
    """Create PathResolver with test project."""
    return PathResolver(project_root=tmp_project)


@pytest.fixture
def tool(resolver):
    """Create FilesystemTool with resolver."""
    return FilesystemTool(resolver=resolver)


# === view_file tests ===

def test_view_file_success(tool, tmp_project):
    """Test viewing an existing file."""
    result = tool.view_file("@project/README.md")

    assert result.success
    assert "# Test Project" in result.data["content"]
    assert result.data["total_lines"] == 3
    assert result.data["size_bytes"] > 0


def test_view_file_with_line_range(tool, tmp_project):
    """Test viewing file with line range."""
    result = tool.view_file("@project/README.md", start_line=1, end_line=2)

    assert result.success
    assert "# Test Project" in result.data["content"]
    assert "This is a test." not in result.data["content"]


def test_view_file_not_found(tool):
    """Test viewing non-existent file."""
    result = tool.view_file("@project/nonexistent.txt")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_FILE_NOT_FOUND


def test_view_file_directory(tool, tmp_project):
    """Test viewing a directory path."""
    result = tool.view_file("@project/src")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_FILE_NOT_FOUND


def test_view_file_binary_detection(tool, tmp_project):
    """Test binary file detection."""
    binary_file = tmp_project / "binary.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x04")

    result = tool.view_file("@project/binary.bin")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_BINARY_FILE


def test_view_file_path_traversal_blocked(tool):
    """Test that path traversal is blocked."""
    result = tool.view_file("@project/../../../etc/passwd")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_PATH_DENIED


# === list_dir tests ===

def test_list_dir_success(tool, tmp_project):
    """Test listing directory contents."""
    result = tool.list_dir("@project")

    assert result.success
    entries = result.data["entries"]
    names = [e["name"] for e in entries]
    assert "README.md" in names
    assert "src" in names
    assert "docs" in names


def test_list_dir_not_found(tool):
    """Test listing non-existent directory."""
    result = tool.list_dir("@project/nonexistent")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_DIR_NOT_FOUND


def test_list_dir_file_path(tool, tmp_project):
    """Test listing with file path instead of directory."""
    result = tool.list_dir("@project/README.md")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_DIR_NOT_FOUND


# === find_by_name tests ===

def test_find_by_name_success(tool, tmp_project):
    """Test finding files by pattern."""
    result = tool.find_by_name("*.md", search_directory="@project")

    assert result.success
    matches = result.data["matches"]
    assert any("README.md" in m for m in matches)
    assert any("guide.md" in m for m in matches)
    assert result.data["match_count"] >= 2


def test_find_by_name_type_file(tool, tmp_project):
    """Test finding only files."""
    result = tool.find_by_name("src", search_directory="@project", entry_type="file")

    assert result.success
    # 'src' is a directory, so should not match when type='file'
    assert result.data["match_count"] == 0


def test_find_by_name_type_directory(tool, tmp_project):
    """Test finding only directories."""
    result = tool.find_by_name("src", search_directory="@project", entry_type="directory")

    assert result.success
    assert result.data["match_count"] == 1


# === grep_search tests ===

def test_grep_search_success(tool, tmp_project):
    """Test searching file contents."""
    result = tool.grep_search("test", search_path="@project")

    assert result.success
    results = result.data["results"]
    assert len(results) >= 1
    assert any("README.md" in r["file"] for r in results)


def test_grep_search_case_insensitive(tool, tmp_project):
    """Test case-insensitive search."""
    result = tool.grep_search("TEST", search_path="@project", case_insensitive=True)

    assert result.success
    assert len(result.data["results"]) >= 1


def test_grep_search_case_sensitive(tool, tmp_project):
    """Test case-sensitive search."""
    result = tool.grep_search("TEST", search_path="@project", case_insensitive=False)

    assert result.success
    # "TEST" should not match "test" with case-sensitive search
    assert len(result.data["results"]) == 0


def test_grep_search_regex(tool, tmp_project):
    """Test regex search."""
    result = tool.grep_search(r"def \w+\(\):", search_path="@project", is_regex=True)

    assert result.success
    results = result.data["results"]
    assert any("main.py" in r["file"] for r in results)
    assert any("utils.py" in r["file"] for r in results)


def test_grep_search_invalid_regex(tool):
    """Test invalid regex pattern."""
    result = tool.grep_search("[invalid(", search_path="@project", is_regex=True)

    assert not result.success
    assert result.error_code == ErrorCode.ERR_INVALID_INPUT


# === write_file tests ===

def test_write_file_requires_approval(tool, tmp_project):
    """Test that write_file requires approval."""
    result = tool.write_file("@project/new.txt", "content")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_write_file_with_approval(tool, tmp_project):
    """Test writing file with approval."""
    tool.approve()
    result = tool.write_file("@project/new.txt", "new content")

    assert result.success
    assert result.data["status"] == "created"

    # Verify file was written
    assert (tmp_project / "new.txt").exists()
    assert (tmp_project / "new.txt").read_text() == "new content"


def test_write_file_overwrite_requires_flag(tool, tmp_project):
    """Test that overwriting requires overwrite flag."""
    tool.approve()
    result = tool.write_file("@project/README.md", "new content")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_FILE_EXISTS


def test_write_file_overwrite_with_flag(tool, tmp_project):
    """Test overwriting with flag."""
    tool.approve()
    result = tool.write_file("@project/README.md", "new content", overwrite=True)

    assert result.success
    assert result.data["status"] == "overwritten"


def test_write_file_outside_project_blocked(tool, tmp_project, tmp_path):
    """Test that writing outside @project is blocked."""
    knowledge = tmp_path / "KNOWLEDGE"
    knowledge.mkdir(parents=True)
    tool.resolver = PathResolver(project_root=tmp_project, knowledge_root=knowledge)

    tool.approve()
    result = tool.write_file("@knowledge/test.txt", "content")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_MUTATION_FORBIDDEN


# === replace_file_content tests ===

def test_replace_file_content_requires_approval(tool, tmp_project):
    """Test that replace requires approval."""
    result = tool.replace_file_content(
        "@project/README.md",
        start_line=1,
        end_line=1,
        target_content="# Test Project\n",
        replacement_content="# New Title\n"
    )

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_replace_file_content_success(tool, tmp_project):
    """Test successful content replacement."""
    tool.approve()
    result = tool.replace_file_content(
        "@project/README.md",
        start_line=1,
        end_line=1,
        target_content="# Test Project\n",
        replacement_content="# New Title\n"
    )

    assert result.success
    assert result.data["status"] == "success"

    # Verify replacement
    content = (tmp_project / "README.md").read_text()
    assert "# New Title" in content


def test_replace_file_content_target_mismatch(tool, tmp_project):
    """Test that mismatched target content fails."""
    tool.approve()
    result = tool.replace_file_content(
        "@project/README.md",
        start_line=1,
        end_line=1,
        target_content="wrong content",
        replacement_content="new content"
    )

    assert not result.success
    assert result.error_code == ErrorCode.ERR_TARGET_NOT_FOUND


# === delete_file tests ===

def test_delete_file_requires_approval(tool, tmp_project):
    """Test that delete requires approval."""
    result = tool.delete_file("@project/README.md")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_delete_file_success(tool, tmp_project):
    """Test successful file deletion."""
    tool.approve()
    result = tool.delete_file("@project/README.md")

    assert result.success
    assert result.data["status"] == "deleted"
    assert not (tmp_project / "README.md").exists()


def test_delete_file_not_found(tool, tmp_project):
    """Test deleting non-existent file."""
    tool.approve()
    result = tool.delete_file("@project/nonexistent.txt")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_FILE_NOT_FOUND


# === Write operation parameter validation (H2) ===

def test_validate_write_file_missing_content():
    """validate() must reject write_file without content."""
    # NOTE: default PathResolver points at the repo root; this validation is
    # parameter-only and never resolves a path, so no fixture is required.
    tool = FilesystemTool()
    is_valid, error = tool.validate("write_file", file_path="@project/file.txt")
    assert is_valid is False
    assert "content" in error


def test_validate_write_file_missing_file_path():
    """validate() must reject write_file without file_path."""
    tool = FilesystemTool()
    is_valid, error = tool.validate("write_file", content="data")
    assert is_valid is False
    assert "path" in error


def test_validate_replace_missing_replacement_content():
    """validate() must reject replace_file_content without all params."""
    tool = FilesystemTool()
    is_valid, error = tool.validate(
        "replace_file_content",
        file_path="@project/README.md",
        start_line=1,
        end_line=1,
        target_content="old",
    )
    assert is_valid is False
    assert "replacement_content" in error


def test_validate_replace_non_integer_lines():
    """validate() must reject non-integer line ranges for replace."""
    tool = FilesystemTool()
    is_valid, error = tool.validate(
        "replace_file_content",
        file_path="@project/README.md",
        start_line="1",
        end_line=1,
        target_content="old",
        replacement_content="new",
    )
    assert is_valid is False
    assert "integers" in error


def test_validate_delete_file_missing_path():
    """validate() must reject delete_file without file_path."""
    tool = FilesystemTool()
    is_valid, error = tool.validate("delete_file")
    assert is_valid is False
    assert "path" in error


def test_validate_write_file_valid():
    """validate() passes a fully-specified write_file call."""
    tool = FilesystemTool()
    is_valid, error = tool.validate(
        "write_file", file_path="@project/file.txt", content="data"
    )
    assert is_valid is True
    assert error is None
