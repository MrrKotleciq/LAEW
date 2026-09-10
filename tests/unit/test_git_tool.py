"""Tests for LAEW GitTool (CONTRACT.md)."""

from pathlib import Path
import subprocess
import tempfile

import pytest

from laew.tools.base import ErrorCode
from laew.tools.git import GitTool


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary git repository."""
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Configure git user for commits
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=str(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    return repo


@pytest.fixture
def tool(tmp_repo):
    """Create GitTool with test repository."""
    return GitTool(repo_root=tmp_repo)


# === Status operations ===

def test_git_status_empty_repo(tool):
    """Test git status on empty repository."""
    result = tool.git_status()

    assert result.success
    assert result.data["branch"] in {"main", "master", "HEAD"}
    assert result.data["is_clean"] is True
    assert result.data["staged"] == []
    assert result.data["unstaged"] == []
    assert result.data["untracked"] == []


def test_git_status_with_untracked_files(tool, tmp_repo):
    """Test git status with untracked files."""
    (tmp_repo / "test.txt").write_text("hello")

    result = tool.git_status()

    assert result.success
    assert "test.txt" in result.data["untracked"]
    assert result.data["is_clean"] is False


def test_git_status_with_staged_changes(tool, tmp_repo):
    """Test git status with staged changes."""
    (tmp_repo / "test.txt").write_text("hello")

    # Stage file
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    result = tool.git_status()

    assert result.success
    assert "test.txt" in result.data["staged"]
    assert result.data["is_clean"] is False


def test_git_status_with_unstaged_changes(tool, tmp_repo):
    """Test git status with unstaged changes."""
    # Create and commit a file
    (tmp_repo / "test.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Modify file
    (tmp_repo / "test.txt").write_text("world")

    result = tool.git_status()

    assert result.success
    assert "test.txt" in result.data["unstaged"]
    assert result.data["is_clean"] is False


# === Diff operations ===

def test_git_diff_no_changes(tool):
    """Test git diff with no changes."""
    result = tool.git_diff()

    assert result.success
    assert result.data["diff"] == ""
    assert result.data["files_changed"] == 0


def test_git_diff_with_changes(tool, tmp_repo):
    """Test git diff with changes."""
    # Create and commit initial file
    (tmp_repo / "test.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Modify file
    (tmp_repo / "test.txt").write_text("world")

    result = tool.git_diff()

    assert result.success
    assert "hello" in result.data["diff"]
    assert "world" in result.data["diff"]


def test_git_diff_staged(tool, tmp_repo):
    """Test git diff for staged changes."""
    (tmp_repo / "test.txt").write_text("hello")

    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    result = tool.git_diff(staged=True)

    assert result.success
    # Staged diff should show the new file
    assert result.data["files_changed"] > 0


# === Log operations ===

def test_git_log_empty_repo(tool):
    """Test git log on empty repository."""
    result = tool.git_log()

    assert result.success
    assert result.data["commits"] == []


def test_git_log_with_commits(tool, tmp_repo):
    """Test git log with commits."""
    # Create and commit files
    for i in range(3):
        (tmp_repo / f"file{i}.txt").write_text(f"content{i}")
        subprocess.run(
            ["git", "add", f"file{i}.txt"],
            cwd=str(tmp_repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=str(tmp_repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    result = tool.git_log()

    assert result.success
    assert len(result.data["commits"]) == 3
    assert all("hash" in c and "author" in c and "date" in c and "message" in c for c in result.data["commits"])


def test_git_log_max_count(tool, tmp_repo):
    """Test git log with max_count limit."""
    # Create and commit files
    for i in range(5):
        (tmp_repo / f"file{i}.txt").write_text(f"content{i}")
        subprocess.run(
            ["git", "add", f"file{i}.txt"],
            cwd=str(tmp_repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        subprocess.run(
            ["git", "commit", "-m", f"commit {i}"],
            cwd=str(tmp_repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    result = tool.git_log(max_count=2)

    assert result.success
    assert len(result.data["commits"]) == 2


# === Commit operations ===

def test_git_commit_requires_approval(tool, tmp_repo):
    """Test that git commit requires approval."""
    (tmp_repo / "test.txt").write_text("hello")

    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    result = tool.git_commit("test commit")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_git_commit_with_approval(tool, tmp_repo):
    """Test git commit with approval."""
    (tmp_repo / "test.txt").write_text("hello")

    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    tool.approve()
    result = tool.git_commit("test commit")

    assert result.success
    assert "commit_hash" in result.data
    assert result.data["status"] == "success"


def test_git_commit_nothing_to_commit(tool):
    """Test git commit with nothing staged."""
    tool.approve()
    result = tool.git_commit("test commit")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_NOTHING_TO_COMMIT


def test_git_commit_with_file_list(tool, tmp_repo):
    """Test git commit with explicit file list."""
    (tmp_repo / "test1.txt").write_text("hello")
    (tmp_repo / "test2.txt").write_text("world")

    tool.approve()
    result = tool.git_commit("test commit", files=["test1.txt"])

    assert result.success
    assert "commit_hash" in result.data


def test_git_commit_rejects_path_traversal(tool, tmp_repo):
    """git commit must refuse to stage a path that escapes the repository."""
    tool.approve()
    result = tool.git_commit("bad commit", files=["../../outside.txt"])

    assert not result.success
    assert result.error_code == ErrorCode.ERR_PATH_DENIED


def test_git_commit_rejects_restricted_path(tool, tmp_repo):
    """git commit must refuse to stage restricted paths (e.g. .git internals)."""
    tool.approve()
    result = tool.git_commit("bad commit", files=[".git/config"])

    assert not result.success
    assert result.error_code == ErrorCode.ERR_PATH_DENIED


# === Checkout operations ===

def test_git_checkout_requires_approval(tool, tmp_repo):
    """Test that git checkout requires approval."""
    result = tool.git_checkout("new-branch", create_new=True)

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_git_checkout_create_branch_with_approval(tool, tmp_repo):
    """Test creating new branch with approval."""
    tool.approve()
    result = tool.git_checkout("new-branch", create_new=True)

    assert result.success
    assert result.data["current_branch"] == "new-branch"


def test_git_checkout_dirty_working_tree(tool, tmp_repo):
    """Test checkout fails with dirty working tree."""
    # Create initial commit
    (tmp_repo / "test.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Determine default branch
    proc = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    default_branch = proc.stdout.strip()

    # Create branch1 with different content
    subprocess.run(
        ["git", "checkout", "-b", "branch1"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    (tmp_repo / "test.txt").write_text("world")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "branch1 change"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Switch back to default branch and create conflicting local changes
    subprocess.run(
        ["git", "checkout", default_branch],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    (tmp_repo / "test.txt").write_text("modified")

    # Try to checkout branch1 - should fail due to conflicting changes
    tool.approve()
    result = tool.git_checkout("branch1")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_DIRTY_WORKING_TREE


# === Branch operations ===

def test_git_branch_requires_approval(tool):
    """Test that git branch requires approval."""
    result = tool.git_branch("new-branch")

    assert not result.success
    assert result.error_code == ErrorCode.ERR_UNAUTHORIZED


def test_git_branch_create_with_approval(tool, tmp_repo):
    """Test creating branch with approval."""
    # Create initial commit first (required for branch operations)
    (tmp_repo / "test.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    tool.approve()
    result = tool.git_branch("new-branch")

    assert result.success
    assert result.data["branch"] == "new-branch"


def test_git_branch_delete_with_approval(tool, tmp_repo):
    """Test deleting branch with approval."""
    # Create initial commit first
    (tmp_repo / "test.txt").write_text("hello")
    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Create and commit on test branch
    subprocess.run(
        ["git", "checkout", "-b", "test-branch"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Switch back to main/master
    subprocess.run(
        ["git", "checkout", "-"],
        cwd=str(tmp_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Delete branch
    tool.approve()
    result = tool.git_branch("test-branch", delete=True)

    assert result.success


# === Forbidden operations ===

def test_forbidden_reset_hard(tool):
    """Test that reset --hard is blocked."""
    tool.approve()
    # Direct call to _run_git to trigger forbidden check
    with pytest.raises(PermissionError, match="Forbidden git subcommand"):
        tool._run_git(["reset", "--hard"])


def test_forbidden_push_force(tool):
    """Test that push --force is blocked."""
    tool.approve()
    with pytest.raises(PermissionError, match="Forbidden git subcommand"):
        tool._run_git(["push", "--force"])


def test_forbidden_clean_f(tool):
    """Test that clean -f is blocked."""
    tool.approve()
    with pytest.raises(PermissionError, match="Forbidden git subcommand"):
        tool._run_git(["clean", "-f"])


def test_forbidden_branch_delete_force(tool):
    """Test that branch -D is blocked."""
    tool.approve()
    with pytest.raises(PermissionError, match="Forbidden git subcommand"):
        tool._run_git(["branch", "-D"])
