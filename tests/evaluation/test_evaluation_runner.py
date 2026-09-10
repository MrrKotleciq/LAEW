"""Tests for the evaluation runner with benchmark datasets."""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from laew.agent.base import Agent, AgentConfig, MessageRole
from laew.agent.executor import AgentExecutor
from laew.llm.base import LLMResponse
from laew.tools.base import Tool, ToolResult
from laew.eval.runner import EvaluationRunner
from laew.eval.tasks import load_dataset, evaluate_task_result, EvaluationTask


# Mock tool classes that inherit the correct names from the actual tool classes
# This ensures the name property returns the expected PascalCase names

class FilesystemTool(Tool):
    """Mock FilesystemTool for testing - name matches actual tool class."""

    OPERATIONS = {
        "list_dir": {"description": "List directory", "args": {"path": "."}},
        "view_file": {"description": "View file", "args": {"file_path": "README.md"}},
    }

    def __init__(self):
        self.description = "Mock FilesystemTool for testing"

    def validate(self, operation: str, **kwargs):
        return operation in self.OPERATIONS

    def execute(self, operation: str, **kwargs):
        return ToolResult(success=True, data=f"Result of {operation}")

    def call(self, operation: str, **kwargs):
        if not self.validate(operation, **kwargs):
            return ToolResult(
                success=False,
                error_code="ERR_VALIDATION",
                error_message=f"Unknown operation: {operation}",
            )
        return self.execute(operation, **kwargs)


class GitTool(Tool):
    """Mock GitTool for testing - name matches actual tool class."""

    OPERATIONS = {
        "git_status": {"description": "Git status", "args": {}},
        "git_log": {"description": "Git log", "args": {"max_count": 3}},
    }

    def __init__(self):
        self.description = "Mock GitTool for testing"

    def validate(self, operation: str, **kwargs):
        return operation in self.OPERATIONS

    def execute(self, operation: str, **kwargs):
        return ToolResult(success=True, data=f"Result of {operation}")

    def call(self, operation: str, **kwargs):
        if not self.validate(operation, **kwargs):
            return ToolResult(
                success=False,
                error_code="ERR_VALIDATION",
                error_message=f"Unknown operation: {operation}",
            )
        return self.execute(operation, **kwargs)


class TerminalTool(Tool):
    """Mock TerminalTool for testing - name matches actual tool class."""

    OPERATIONS = {
        "run_command": {"description": "Run command", "args": {"command": "grep ..."}},
    }

    def __init__(self):
        self.description = "Mock TerminalTool for testing"

    def validate(self, operation: str, **kwargs):
        return operation in self.OPERATIONS

    def execute(self, operation: str, **kwargs):
        return ToolResult(success=True, data=f"Result of {operation}")

    def call(self, operation: str, **kwargs):
        if not self.validate(operation, **kwargs):
            return ToolResult(
                success=False,
                error_code="ERR_VALIDATION",
                error_message=f"Unknown operation: {operation}",
            )
        return self.execute(operation, **kwargs)


class WebTool(Tool):
    """Mock WebTool for testing - name matches actual tool class."""

    OPERATIONS = {
        "read_url_content": {"description": "Read URL", "args": {"url": "https://example.com"}},
    }

    def __init__(self):
        self.description = "Mock WebTool for testing"

    def validate(self, operation: str, **kwargs):
        return operation in self.OPERATIONS

    def execute(self, operation: str, **kwargs):
        return ToolResult(success=True, data=f"Result of {operation}")

    def call(self, operation: str, **kwargs):
        if not self.validate(operation, **kwargs):
            return ToolResult(
                success=False,
                error_code="ERR_VALIDATION",
                error_message=f"Unknown operation: {operation}",
            )
        return self.execute(operation, **kwargs)


def make_mock_llm_response(content: str) -> LLMResponse:
    """Build a valid LLMResponse for the given content."""
    return LLMResponse(
        content=content,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        finish_reason="stop",
    )


def make_agent_with_tools(max_iterations: int = 5):
    """Build an agent with mock provider and standard tools."""
    agent = Agent(
        config=AgentConfig(name="test-agent", max_iterations=max_iterations),
        provider=MagicMock(),
    )
    agent.tools = {
        "FilesystemTool": FilesystemTool(),
        "GitTool": GitTool(),
        "TerminalTool": TerminalTool(),
        "WebTool": WebTool(),
    }
    return agent


def test_load_laew_specific_dataset():
    """Test that the laew_specific dataset loads correctly with fixed tool names."""
    dataset_path = Path("laew/eval/datasets/laew_specific.json")
    if dataset_path.exists():
        data = load_dataset(dataset_path)
        assert isinstance(data, list)
        assert len(data) == 5

        # Verify all tasks use PascalCase tool names
        for task in data:
            for expected_call in task.expected_tool_calls:
                tool_name = expected_call.get("tool")
                assert tool_name in ["FilesystemTool", "GitTool"], \
                    f"Expected PascalCase tool name, got: {tool_name}"
    else:
        pytest.skip("Dataset file not found")


def test_load_general_reasoning_dataset():
    """Test that the general_reasoning dataset loads correctly with fixed tool names."""
    dataset_path = Path("laew/eval/datasets/general_reasoning.json")
    if dataset_path.exists():
        data = load_dataset(dataset_path)
        assert isinstance(data, list)
        assert len(data) == 5

        # Verify all tasks use PascalCase tool names
        for task in data:
            for expected_call in task.expected_tool_calls:
                tool_name = expected_call.get("tool")
                assert tool_name in ["FilesystemTool", "GitTool", "TerminalTool", "WebTool"], \
                    f"Expected PascalCase tool name, got: {tool_name}"

        # Verify specific operations are correct
        git_log_task = next(t for t in data if t.task_id == "general-git-log")
        expected_call = git_log_task.expected_tool_calls[0]
        assert expected_call["operation"] == "git_log"

        web_read_task = next(t for t in data if t.task_id == "general-web-read-url")
        expected_call = web_read_task.expected_tool_calls[0]
        assert expected_call["operation"] == "read_url_content"

        terminal_task = next(t for t in data if t.task_id == "general-file-content-search")
        expected_call = terminal_task.expected_tool_calls[0]
        assert expected_call["operation"] == "run_command"
    else:
        pytest.skip("Dataset file not found")


def test_evaluation_runner_executes_task():
    """Test that EvaluationRunner can execute a single task with mocked LLM."""
    agent = make_agent_with_tools()
    runner = EvaluationRunner(agent)

    # Mock the LLM to return a valid tool call then a final answer
    agent.provider.generate.side_effect = [
        make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
```'''),
        make_mock_llm_response("Found the files: laew, tests, docs"),
    ]

    # Create a test task
    task = EvaluationTask(
        task_id="test-filesystem-list",
        description="Test filesystem list",
        input_prompt="List files in current directory",
        expected_tool_calls=[
            {"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
        ],
        expected_outcome_contains=["laew", "tests"],
    )

    result = runner.run_task(task)

    assert result["execution_success"] is True
    assert result["success"] is True
    assert result["tool_call_match"] is True
    assert result["outcome_contains_match"] is True
    assert len(result["actual_tool_calls"]) == 1
    assert result["actual_tool_calls"][0]["tool"] == "FilesystemTool"
    assert result["actual_tool_calls"][0]["operation"] == "list_dir"


def test_evaluation_runner_dataset_run():
    """Test that EvaluationRunner can run a full dataset."""
    agent = make_agent_with_tools()
    runner = EvaluationRunner(agent)

    # Mock LLM to respond correctly for all tasks
    # Order matches laew_specific.json task order
    agent.provider.generate.side_effect = [
        # Task 1: laew-manifest-check (view_file on manifest)
        make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "view_file", "args": {"file_path": "manifests/SYSTEM_MANIFEST.yaml"}}
```'''),
        make_mock_llm_response("workspace configuration"),

        # Task 2: laew-filesystem-list (list_dir)
        make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
```'''),
        make_mock_llm_response("Found: laew, tests, docs, manifests"),

        # Task 3: laew-git-status (git_status)
        make_mock_llm_response('''```tool_call
{"tool": "GitTool", "operation": "git_status", "args": {}}
```'''),
        make_mock_llm_response("On branch main, working tree clean"),

        # Task 4: laew-tool-filesystem-view-readme (view_file on README.md)
        make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "view_file", "args": {"file_path": "README.md"}}
```'''),
        make_mock_llm_response("LAEW - Local AI Engineering Workspace"),

        # Task 5: laew-manifest-model-roles (view_file on manifest)
        make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "view_file", "args": {"file_path": "manifests/SYSTEM_MANIFEST.yaml"}}
```'''),
        make_mock_llm_response("role definitions for agent, primary, embedding"),
    ]

    # Run the laew_specific dataset
    report = runner.run_dataset("laew_specific")

    assert report.task_count == 5
    assert report.successful_task_count == 5
    assert report.metrics is not None


def test_evaluation_runner_handles_execution_failure():
    """Test that runner handles agent execution failures gracefully."""
    agent = make_agent_with_tools(max_iterations=2)
    runner = EvaluationRunner(agent)

    # Mock LLM to always return malformed tool calls that will exhaust iterations
    agent.provider.generate.return_value = make_mock_llm_response(
        '```tool_call\n{"tool": "FilesystemTool", "operation": "invalid_op", "args": {}}\n```'
    )

    task = EvaluationTask(
        task_id="test-fail",
        description="Test failure handling",
        input_prompt="This will fail",
        expected_tool_calls=[
            {"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
        ],
        expected_outcome_contains=["should not match"],
    )

    result = runner.run_task(task)

    # The executor should fail due to max iterations or invalid operations
    assert result["execution_success"] is False or result["execution_error"] is not None
    assert result["success"] is False


def test_evaluate_task_result_matches_pascal_case():
    """Test that evaluate_task_result correctly matches PascalCase tool names."""
    task = EvaluationTask(
        task_id="test-pascal-case",
        description="Test PascalCase matching",
        input_prompt="Test",
        expected_tool_calls=[
            {"tool": "FilesystemTool", "operation": "list_dir", "args": {}}
        ],
        expected_outcome_contains=[],
    )

    # Actual tool calls from executor use PascalCase (class name)
    actual_tool_calls = [
        {"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
    ]

    agent = make_agent_with_tools()
    result = evaluate_task_result(task, actual_tool_calls, "Done", agent)

    assert result["tool_call_match"] is True
    assert result["useful_tool_calls"] == 1


def test_evaluate_task_result_case_sensitive():
    """Test that evaluate_task_result is case-sensitive (lowercase won't match)."""
    task = EvaluationTask(
        task_id="test-case-sensitive",
        description="Test case sensitivity",
        input_prompt="Test",
        expected_tool_calls=[
            {"tool": "FilesystemTool", "operation": "list_dir", "args": {}}
        ],
        expected_outcome_contains=[],
    )

    # Lowercase tool name should NOT match
    actual_tool_calls = [
        {"tool": "filesystem", "operation": "list_dir", "args": {"path": "."}}
    ]

    agent = make_agent_with_tools()
    result = evaluate_task_result(task, actual_tool_calls, "Done", agent)

    assert result["tool_call_match"] is False
    assert result["useful_tool_calls"] == 0


def test_evaluation_runner_all_datasets():
    """Test that run_all_datasets discovers and runs both datasets."""
    agent = make_agent_with_tools()
    runner = EvaluationRunner(agent)

    # Mock many responses for both datasets (10 tasks x 2 calls each = 20)
    responses = []
    for i in range(20):
        if i % 2 == 0:
            responses.append(make_mock_llm_response('''```tool_call
{"tool": "FilesystemTool", "operation": "list_dir", "args": {"path": "."}}
```'''))
        else:
            responses.append(make_mock_llm_response("Task completed successfully"))

    agent.provider.generate.side_effect = responses

    reports = runner.run_all_datasets()

    assert len(reports) >= 2
    dataset_names = [r.dataset_name for r in reports]
    assert "laew_specific" in dataset_names
    assert "general_reasoning" in dataset_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
