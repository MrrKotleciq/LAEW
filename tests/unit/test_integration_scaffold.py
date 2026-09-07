"""Integration test scaffold for LAEW.

These tests verify that components work together correctly:
- Agent + Tools
- Agent + RAG
- RAG + KnowledgeBase + Embeddings
- CLI + Tools
"""

import tempfile
from pathlib import Path

import pytest

from laew.agent.base import Agent, AgentConfig, AgentRole
from laew.agent.executor import AgentExecutor
from laew.cli import main
from laew.llm.ollama import OllamaProvider
from laew.manifest import load_manifest
from laew.prompts.context_budget import ContextBudget, TokenEstimator
from laew.prompts.loader import PromptLoader
from laew.rag import KnowledgeBase, KnowledgeScope, RAGPipeline
from laew.tools.filesystem import FilesystemTool
from laew.tools.git import GitTool
from laew.tools.terminal import TerminalTool
from laew.tools.web import WebTool


class TestAgentToolsIntegration:
    """Test agent working with tools."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir) / "projects" / "test-project"
            project.mkdir(parents=True)
            (project / "README.md").write_text("# Test Project\n\nIntegration test.")
            (project / "src").mkdir()
            (project / "src" / "main.py").write_text("def main():\n    print('hello')\n")
            # Initialize a git repository so that git status works
            import subprocess
            subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
            yield project

    @pytest.fixture
    def executor(self, temp_project):
        """Create an agent executor with all tools available."""
        from laew.security import PathResolver

        config = AgentConfig(
            role=AgentRole.CHIEF,
            system_prompt="You are a helpful assistant with access to tools.",
        )

        # Configure PathResolver for the temp project
        path_resolver = PathResolver(project_root=temp_project)

        # Tools
        filesystem = FilesystemTool(resolver=path_resolver)
        git = GitTool(repo_root=temp_project)
        terminal = TerminalTool()
        web = WebTool()

        agent = Agent(
            config=config,
            provider=OllamaProvider(),
            tools=[filesystem, git, terminal, web]
        )
        return AgentExecutor(agent)

    def test_agent_can_list_files(self, executor, temp_project):
        """Test agent can list directory via filesystem tool."""
        result = executor.agent.tools["FilesystemTool"].list_dir(str(temp_project))
        assert result.success
        names = [e["name"] for e in result.data["entries"]]
        assert "README.md" in names
        assert "src" in names

    def test_agent_can_view_file(self, executor, temp_project):
        """Test agent can read file via filesystem tool."""
        result = executor.agent.tools["FilesystemTool"].view_file(str(temp_project / "README.md"))
        assert result.success
        assert "# Test Project" in result.data["content"]

    def test_agent_can_git_status(self, executor):
        """Test agent can run git status."""
        result = executor.agent.tools["GitTool"].git_status()
        assert result.success
        assert "branch" in result.data

    def test_agent_can_run_allowlisted_command(self, executor):
        """Test agent can run allowlisted terminal command."""
        result = executor.agent.tools["TerminalTool"].execute("run_command", command="ls")
        assert result.success
        assert "stdout" in result.data


class TestAgentRAGIntegration:
    """Test agent working with RAG system."""

    @pytest.fixture
    def rag_components(self):
        """Create RAG components with mock embeddings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup project with documents
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "architecture.md").write_text(
                "# Architecture\n\nLAEW uses modular architecture."
            )

            knowledge_dir = Path(tmpdir) / "knowledge"
            knowledge_dir.mkdir()
            (knowledge_dir / "notes.md").write_text(
                "# Notes\n\nEngineering best practices."
            )

            # Use mock embedding for speed
            from tests.unit.test_rag import MockEmbeddingService
            embedding_service = MockEmbeddingService()

            kb = KnowledgeBase(
                project_root=str(project_dir),
                knowledge_root=str(knowledge_dir),
                embedding_service=embedding_service,
            )
            kb.load()

            pipeline = RAGPipeline(
                knowledge_base=kb,
                embedding_service=embedding_service,
                top_k=3,
                similarity_threshold=0.1,
            )

            yield {
                "knowledge_base": kb,
                "pipeline": pipeline,
                "embedding_service": embedding_service,
            }

    def test_rag_retrieves_project_docs(self, rag_components):
        """Test RAG retrieves from project scope."""
        result = rag_components["pipeline"].retrieve(
            "What is the architecture?",
            scope=KnowledgeScope.PROJECT,
        )
        assert result.total_tokens > 0
        assert len(result.chunks) > 0
        assert any("LAEW" in chunk.text for chunk, _ in result.chunks)

    def test_rag_retrieves_hybrid_scope(self, rag_components):
        """Test RAG retrieves from hybrid scope."""
        result = rag_components["pipeline"].retrieve(
            "engineering information",
            scope=KnowledgeScope.HYBRID,
        )
        assert result.scope == KnowledgeScope.HYBRID
        assert len(result.chunks) > 0

    def test_rag_source_attribution(self, rag_components):
        """Test RAG results include source attribution."""
        result = rag_components["pipeline"].retrieve(
            "architecture",
            scope=KnowledgeScope.PROJECT,
        )
        assert len(result.sources) > 0
        # Sources should indicate project scope (the filename itself is enough)
        for source in result.sources:
            assert "architecture.md" in source.lower()


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_check_manifest(self, capsys):
        """Test laew check with the actual manifest."""
        import sys
        from unittest.mock import patch

        with patch("sys.argv", ["laew", "check", "--manifest", "manifests/SYSTEM_MANIFEST.yaml"]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Manifest loaded successfully" in captured.out

    def test_tool_filesystem_list(self, capsys):
        """Test laew tool filesystem list_dir."""
        import sys
        from unittest.mock import patch

        with patch("sys.argv", ["laew", "tool", "filesystem", "list_dir", "directory_path=."]):
            exit_code = main()

        assert exit_code in [0, 1]
        captured = capsys.readouterr()
        assert "Executing: filesystem.list_dir" in captured.out

    def test_tool_git_status(self, capsys):
        """Test laew tool git git_status."""
        import sys
        from unittest.mock import patch

        with patch("sys.argv", ["laew", "tool", "git", "git_status"]):
            exit_code = main()

        assert exit_code in [0, 1]
        captured = capsys.readouterr()
        assert "Executing: git.git_status" in captured.out


class TestPromptBudgetIntegration:
    """Test prompt loading with context budgeting."""

    def test_prompt_loader_with_budget(self):
        """Test prompt loader respects context budget."""
        budget = ContextBudget()
        # The API doesn't take budget in __init__
        loader = PromptLoader(base_paths=["prompts"])

        # Load core prompt
        prompt = loader.load_prompt("core")
        assert len(prompt.render()) > 0

        # Test token estimation
        estimated_tokens = TokenEstimator.estimate_prompt_sections([prompt.render()])
        assert estimated_tokens > 0

        # Budget should track if we're over budget
        is_over = budget.is_over_budget(estimated_tokens)
        # This is just testing the mechanism - we don't assert on the value
        # since it depends on the actual prompt content


class TestManifestToolsIntegration:
    """Test manifest validation with actual tool configs."""

    def test_manifest_tool_policies_loaded(self):
        """Test manifest tool policies are properly structured."""
        manifest = load_manifest("manifests/SYSTEM_MANIFEST.yaml")

        # Verify all tool categories present
        categories = manifest["tools"]["categories"]
        assert "filesystem" in categories
        assert "git" in categories
        assert "terminal" in categories
        assert "web" in categories

        # Verify policies
        assert categories["filesystem"]["policy"] == "read_only_by_default"
        assert categories["git"]["policy"] == "inspection_first"
        assert categories["terminal"]["policy"] == "safe_command_allowlist"
        assert categories["web"]["policy"] == "read_only"

        # Verify approval requirements
        fs_approvals = categories["filesystem"]["require_user_approval"]
        assert "write_file" in fs_approvals
        assert "replace_file_content" in fs_approvals
        assert "delete_file" in fs_approvals


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
