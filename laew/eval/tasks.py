"""Evaluation tasks and dataset loading for the LAEW Evaluation Harness."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from laew.agent.base import Agent


@dataclass
class EvaluationTask:
    """A single evaluation task with expected outcomes and evaluation criteria."""

    task_id: str
    description: str
    input_prompt: str
    expected_tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    expected_outcome_contains: List[str] = field(default_factory=list)
    expected_outcome_not_contains: List[str] = field(default_factory=list)
    evaluation_criteria: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate task structure."""
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.input_prompt:
            raise ValueError("input_prompt is required")

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "input_prompt": self.input_prompt,
            "expected_tool_calls": self.expected_tool_calls,
            "expected_outcome_contains": self.expected_outcome_contains,
            "expected_outcome_not_contains": self.expected_outcome_not_contains,
            "evaluation_criteria": self.evaluation_criteria,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationTask":
        """Create task from dictionary."""
        return cls(**data)


class TaskRegistry:
    """Registry for managing evaluation tasks and datasets."""

    def __init__(self):
        self._tasks: Dict[str, EvaluationTask] = {}
        self._datasets: Dict[str, List[EvaluationTask]] = {}

    def register(self, task: EvaluationTask) -> None:
        """Register a single task."""
        if task.task_id in self._tasks:
            raise ValueError(f"Task with id '{task.task_id}' already registered")
        self._tasks[task.task_id] = task

    def register_dataset(self, dataset_name: str, tasks: List[EvaluationTask]) -> None:
        """Register a dataset (list of tasks)."""
        if dataset_name in self._datasets:
            raise ValueError(f"Dataset '{dataset_name}' already registered")
        for task in tasks:
            self.register(task)
        self._datasets[dataset_name] = tasks

    def get(self, task_id: str) -> Optional[EvaluationTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)

    def get_dataset(self, dataset_name: str) -> Optional[List[EvaluationTask]]:
        """Get all tasks in a dataset."""
        return self._datasets.get(dataset_name)

    def list_datasets(self) -> List[str]:
        """List all registered dataset names."""
        return list(self._datasets.keys())

    def list_tasks(self) -> List[str]:
        """List all registered task IDs."""
        return list(self._tasks.keys())

    def all_tasks(self) -> List[EvaluationTask]:
        """Get all registered tasks."""
        return list(self._tasks.values())


def load_dataset(file_path: str) -> List[EvaluationTask]:
    """Load evaluation tasks from a JSON file.

    Expected JSON structure:
    {
        "tasks": [
            {
                "task_id": "task-001",
                "description": "Test file reading",
                "input_prompt": "Read the file README.md",
                "expected_tool_calls": [
                    {"tool": "filesystem", "operation": "view_file", "args": {"file_path": "README.md"}}
                ],
                "expected_outcome_contains": ["README", "LAEW"],
                "evaluation_criteria": {"relevance_threshold": 0.8}
            }
        ]
    }

    Args:
        file_path: Path to the JSON dataset file

    Returns:
        List of EvaluationTask objects
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    tasks = []
    for task_data in data.get("tasks", []):
        tasks.append(EvaluationTask.from_dict(task_data))

    return tasks


def create_default_registry() -> TaskRegistry:
    """Create a TaskRegistry with built-in LAEW benchmark datasets.

    Returns:
        TaskRegistry with loaded datasets
    """
    registry = TaskRegistry()

    # Load built-in datasets if they exist
    dataset_dir = Path(__file__).parent / "datasets"
    if dataset_dir.exists():
        for dataset_file in dataset_dir.glob("*.json"):
            dataset_name = dataset_file.stem
            try:
                tasks = load_dataset(str(dataset_file))
                registry.register_dataset(dataset_name, tasks)
            except (json.JSONDecodeError, ValueError) as e:
                # Log error but continue loading other datasets
                print(f"Warning: Failed to load dataset '{dataset_name}': {e}")

    return registry


# Global registry instance
_global_registry: Optional[TaskRegistry] = None


def get_global_registry() -> TaskRegistry:
    """Get the global task registry (lazy initialization)."""
    global _global_registry
    if _global_registry is None:
        _global_registry = create_default_registry()
    return _global_registry


def evaluate_task_result(
    task: EvaluationTask,
    actual_tool_calls: List[Dict[str, Any]],
    actual_response: str,
    agent: Agent,
) -> Dict[str, Any]:
    """Evaluate a task result against expected outcomes.

    Args:
        task: The evaluation task
        actual_tool_calls: List of actual tool calls made by the agent
        actual_response: The final response from the agent
        agent: The agent that executed the task

    Returns:
        Dictionary with evaluation results:
        - success: bool (overall success)
        - tool_call_match: bool (whether tool calls match expected)
        - outcome_contains_match: bool (whether expected strings are in response)
        - outcome_not_contains_match: bool (whether unexpected strings are absent)
        - useful_tool_calls: int (number of useful tool calls)
        - total_tool_calls: int (total tool calls made)
        - relevance_score: float (0-1 heuristic relevance score)
    """
    # Check tool call matching (simplified: check if expected tools were called)
    expected_tool_names = [tc.get("tool") for tc in task.expected_tool_calls]
    actual_tool_names = [tc.get("tool") for tc in actual_tool_calls]

    tool_call_match = all(
        expected in actual_tool_names for expected in expected_tool_names
    )

    # Check expected strings in response
    outcome_contains_match = all(
        expected in actual_response for expected in task.expected_outcome_contains
    )

    # Check unexpected strings absent from response
    outcome_not_contains_match = all(
        unexpected not in actual_response for unexpected in task.expected_outcome_not_contains
    )

    # Overall success (simplified heuristic)
    success = tool_call_match and outcome_contains_match and outcome_not_contains_match

    # Count useful tool calls (those matching expected)
    useful_tool_calls = sum(
        1 for tc in actual_tool_calls if tc.get("tool") in expected_tool_names
    )
    total_tool_calls = len(actual_tool_calls)

    # Heuristic relevance score
    relevance_score = 0.0
    if success:
        relevance_score = 1.0
    else:
        # Partial credit based on what matched
        matches = sum([
            tool_call_match,
            outcome_contains_match,
            outcome_not_contains_match,
        ])
        relevance_score = matches / 3.0

    return {
        "success": success,
        "tool_call_match": tool_call_match,
        "outcome_contains_match": outcome_contains_match,
        "outcome_not_contains_match": outcome_not_contains_match,
        "useful_tool_calls": useful_tool_calls,
        "total_tool_calls": total_tool_calls,
        "relevance_score": relevance_score,
    }