"""Evaluation runner for the LAEW Evaluation Harness."""

import time
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from laew.agent.base import Agent
from laew.agent.executor import AgentExecutor
from laew.eval.tasks import EvaluationTask, TaskRegistry, evaluate_task_result
from laew.eval.metrics import EvaluationMetrics, compute_metrics_from_results


class EvaluationReport:
    """Container for evaluation results and metrics."""

    def __init__(
        self,
        dataset_name: str,
        start_time: float,
        end_time: float,
        task_results: List[Dict[str, Any]],
        metrics: EvaluationMetrics,
    ):
        self.dataset_name = dataset_name
        self.start_time = start_time
        self.end_time = end_time
        self.task_results = task_results
        self.metrics = metrics

    @property
    def duration(self) -> float:
        """Total evaluation duration in seconds."""
        return self.end_time - self.start_time

    @property
    def task_count(self) -> int:
        """Number of tasks evaluated."""
        return len(self.task_results)

    @property
    def successful_task_count(self) -> int:
        """Number of successfully completed tasks."""
        return sum(1 for r in self.task_results if r.get("success", False))

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "dataset_name": self.dataset_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "task_count": self.task_count,
            "successful_task_count": self.successful_task_count,
            "task_results": self.task_results,
            "metrics": {
                name: asdict(result) for name, result in self.metrics.all().items()
            },
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def summary(self) -> str:
        """Generate a human-readable summary of the evaluation."""
        lines = [
            f"Evaluation Report: {self.dataset_name}",
            f"Duration: {self.duration:.2f} seconds",
            f"Tasks: {self.successful_task_count}/{self.task_count} successful",
            "",
            "Metrics:",
            str(self.metrics),
            "",
            "Task Details:",
        ]

        for i, result in enumerate(self.task_results, 1):
            status = "PASS" if result.get("success", False) else "FAIL"
            lines.append(
                f"  {i}. {result.get('task_id', 'unknown')}: {status} "
                f"(relevance: {result.get('relevance_score', 0):.2f})"
            )

        return "\n".join(lines)


class EvaluationRunner:
    """Runs evaluation tasks against an agent and collects metrics."""

    def __init__(self, agent: Agent):
        """
        Initialize the evaluation runner.

        Args:
            agent: The LAEW agent to evaluate
        """
        self.agent = agent
        self.executor = AgentExecutor(agent)
        self.task_registry = TaskRegistry()

    def run_task(
        self, task: EvaluationTask
    ) -> Dict[str, Any]:
        """
        Run a single evaluation task.

        Args:
            task: The evaluation task to run

        Returns:
            Dictionary with task execution and evaluation results
        """
        start_time = time.time()

        # Execute the agent with the task prompt
        execution_result = self.executor.run(task.input_prompt)

        end_time = time.time()
        latency = end_time - start_time

        # Extract tool calls from execution steps
        actual_tool_calls = []
        for step in execution_result.steps:
            if step.tool_name and step.operation is not None:
                actual_tool_calls.append(
                    {
                        "tool": step.tool_name,
                        "operation": step.operation,
                        "args": step.args,
                    }
                )

        # Evaluate the result
        evaluation_result = evaluate_task_result(
            task, actual_tool_calls, execution_result.final_response, self.agent
        )

        # Combine results
        result = {
            "task_id": task.task_id,
            "description": task.description,
            "input_prompt": task.input_prompt,
            "execution_success": execution_result.success,
            "execution_error": execution_result.error,
            "final_response": execution_result.final_response,
            "actual_tool_calls": actual_tool_calls,
            "latency": latency,
            "token_usage": 0,  # Would need to extract from LLM responses
            "api_calls": len(actual_tool_calls),
            "success": evaluation_result["success"],
            "tool_call_match": evaluation_result["tool_call_match"],
            "outcome_contains_match": evaluation_result["outcome_contains_match"],
            "outcome_not_contains_match": evaluation_result[
                "outcome_not_contains_match"
            ],
            "useful_tool_calls": evaluation_result["useful_tool_calls"],
            "total_tool_calls": evaluation_result["total_tool_calls"],
            "relevance_score": evaluation_result["relevance_score"],
        }

        return result

    def run_dataset(
        self, dataset_name: str
    ) -> EvaluationReport:
        """
        Run all tasks in a dataset.

        Args:
            dataset_name: Name of the dataset to run

        Returns:
            EvaluationReport with results and metrics
        """
        # Load dataset from registry or file
        tasks = self.task_registry.get_dataset(dataset_name)
        if tasks is None:
            # Try to load from file directly
            from laew.eval.tasks import load_dataset
            import os

            dataset_path = os.path.join(
                os.path.dirname(__file__), "datasets", f"{dataset_name}.json"
            )
            if os.path.exists(dataset_path):
                tasks = load_dataset(dataset_path)
            else:
                raise ValueError(f"Dataset '{dataset_name}' not found")

        start_time = time.time()
        task_results = []

        for task in tasks:
            try:
                result = self.run_task(task)
                task_results.append(result)
            except Exception as e:
                # Record failed task
                task_results.append(
                    {
                        "task_id": task.task_id,
                        "description": task.description,
                        "input_prompt": task.input_prompt,
                        "execution_success": False,
                        "execution_error": str(e),
                        "final_response": "",
                        "actual_tool_calls": [],
                        "latency": 0.0,
                        "token_usage": 0,
                        "api_calls": 0,
                        "success": False,
                        "tool_call_match": False,
                        "outcome_contains_match": False,
                        "outcome_not_contains_match": False,
                        "useful_tool_calls": 0,
                        "total_tool_calls": 0,
                        "relevance_score": 0.0,
                    }
                )

        end_time = time.time()

        # Compute metrics from results
        metrics = compute_metrics_from_results(task_results)

        return EvaluationReport(
            dataset_name=dataset_name,
            start_time=start_time,
            end_time=end_time,
            task_results=task_results,
            metrics=metrics,
        )

    def run_all_datasets(self) -> List[EvaluationReport]:
        """
        Run all registered datasets.

        Returns:
            List of EvaluationReports, one per dataset
        """
        dataset_names = self.task_registry.list_datasets()
        if not dataset_names:
            # Try to discover datasets in the datasets directory
            from laew.eval.tasks import load_dataset
            import os
            import glob

            dataset_dir = os.path.join(os.path.dirname(__file__), "datasets")
            if os.path.exists(dataset_dir):
                dataset_files = glob.glob(os.path.join(dataset_dir, "*.json"))
                dataset_names = [
                    os.path.splitext(os.path.basename(f))[0]
                    for f in dataset_files
                ]

        reports = []
        for dataset_name in dataset_names:
            try:
                report = self.run_dataset(dataset_name)
                reports.append(report)
            except Exception as e:
                print(f"Error running dataset '{dataset_name}': {e}")

        return reports