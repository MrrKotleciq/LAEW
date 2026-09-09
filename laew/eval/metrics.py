"""Evaluation metrics for the LAEW Evaluation Harness."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class MetricResult:
    """Result of a metric computation."""

    name: str
    value: float
    description: str
    unit: str = ""
    threshold: Optional[float] = None  # Optional threshold for pass/fail


class EvaluationMetrics:
    """Container for computed evaluation metrics."""

    def __init__(self):
        self.metrics: Dict[str, MetricResult] = {}

    def add_metric(self, result: MetricResult):
        """Add a metric result."""
        self.metrics[result.name] = result

    def get(self, name: str) -> Optional[MetricResult]:
        """Get a metric by name."""
        return self.metrics.get(name)

    def all(self) -> Dict[str, MetricResult]:
        """Get all metrics."""
        return self.metrics.copy()

    def __str__(self) -> str:
        """String representation of metrics."""
        lines = ["Evaluation Metrics:"]
        for name, result in self.metrics.items():
            value_str = f"{result.value:.3f}"
            if result.unit:
                value_str += f" {result.unit}"
            if result.threshold is not None:
                status = "PASS" if result.value >= result.threshold else "FAIL"
                lines.append(f"  {name}: {value_str} (threshold: {result.threshold} {result.unit}) [{status}]")
            else:
                lines.append(f"  {name}: {value_str} {result.unit}")
        return "\n".join(lines)


def compute_task_success_rate(successful_tasks: int, total_tasks: int) -> MetricResult:
    """Compute the percentage of tasks completed successfully.

    Args:
        successful_tasks: Number of tasks completed successfully
        total_tasks: Total number of tasks attempted

    Returns:
        MetricResult with success rate as percentage (0-100)
    """
    if total_tasks == 0:
        rate = 0.0
    else:
        rate = (successful_tasks / total_tasks) * 100

    return MetricResult(
        name="task_success_rate",
        value=rate,
        description="Percentage of tasks completed successfully",
        unit="%",
        threshold=80.0  # Target: 80% success rate
    )


def compute_tool_usage_efficiency(useful_tool_calls: int, total_tool_calls: int) -> MetricResult:
    """Compute the ratio of useful tool calls to total tool calls.

    Args:
        useful_tool_calls: Number of tool calls that contributed to task completion
        total_tool_calls: Total number of tool calls made

    Returns:
        MetricResult with efficiency ratio as percentage (0-100)
    """
    if total_tool_calls == 0:
        efficiency = 0.0
    else:
        efficiency = (useful_tool_calls / total_tool_calls) * 100

    return MetricResult(
        name="tool_usage_efficiency",
        value=efficiency,
        description="Ratio of useful tool calls to total tool calls",
        unit="%",
        threshold=70.0  # Target: 70% efficiency
    )


def compute_response_quality(relevance_scores: List[float]) -> MetricResult:
    """Compute average response quality score.

    Args:
        relevance_scores: List of relevance scores (0-1) for responses

    Returns:
        MetricResult with average quality score
    """
    if not relevance_scores:
        avg_score = 0.0
    else:
        avg_score = sum(relevance_scores) / len(relevance_scores)

    return MetricResult(
        name="response_quality",
        value=avg_score,
        description="Average response relevance and correctness score",
        unit="score",
        threshold=0.7  # Target: 0.7+ quality score
    )


def compute_latency(latencies: List[float]) -> MetricResult:
    """Compute average task latency.

    Args:
        latencies: List of task latencies in seconds

    Returns:
        MetricResult with average latency
    """
    if not latencies:
        avg_latency = 0.0
    else:
        avg_latency = sum(latencies) / len(latencies)

    return MetricResult(
        name="latency",
        value=avg_latency,
        description="Average time taken per task",
        unit="seconds",
        threshold=30.0  # Target: <30 seconds per task
    )


def compute_resource_usage(token_usage: List[int], api_calls: List[int]) -> MetricResult:
    """Compute average resource usage per task.

    Args:
        token_usage: List of token counts used per task
        api_calls: List of API calls made per task

    Returns:
        MetricResult with average resource usage (combined score)
    """
    if not token_usage or not api_calls:
        avg_tokens = 0.0
        avg_calls = 0.0
    else:
        avg_tokens = sum(token_usage) / len(token_usage)
        avg_calls = sum(api_calls) / len(api_calls)

    # Normalize and combine (simple heuristic: tokens/100 + calls)
    combined_score = (avg_tokens / 100.0) + avg_calls

    return MetricResult(
        name="resource_usage",
        value=combined_score,
        description="Average resource usage (tokens/100 + API calls)",
        unit="units",
        threshold=10.0  # Target: <10 resource units
    )


def compute_metrics_from_results(results: List[Dict[str, Any]]) -> EvaluationMetrics:
    """Compute all metrics from a list of task results.

    Args:
        results: List of task result dictionaries, each containing:
            - success: bool
            - useful_tool_calls: int
            - total_tool_calls: int
            - relevance_score: float (0-1)
            - latency: float (seconds)
            - token_usage: int
            - api_calls: int

    Returns:
        EvaluationMetrics with all computed metrics
    """
    metrics = EvaluationMetrics()

    if not results:
        # Return zero metrics if no results
        metrics.add_metric(compute_task_success_rate(0, 0))
        metrics.add_metric(compute_tool_usage_efficiency(0, 0))
        metrics.add_metric(compute_response_quality([]))
        metrics.add_metric(compute_latency([]))
        metrics.add_metric(compute_resource_usage([], []))
        return metrics

    # Extract data from results
    successful_tasks = sum(1 for r in results if r.get("success", False))
    total_tasks = len(results)

    useful_tool_calls = sum(r.get("useful_tool_calls", 0) for r in results)
    total_tool_calls = sum(r.get("total_tool_calls", 0) for r in results)

    relevance_scores = [r.get("relevance_score", 0.0) for r in results]
    latencies = [r.get("latency", 0.0) for r in results]
    token_usage = [r.get("token_usage", 0) for r in results]
    api_calls = [r.get("api_calls", 0) for r in results]

    # Compute metrics
    metrics.add_metric(compute_task_success_rate(successful_tasks, total_tasks))
    metrics.add_metric(compute_tool_usage_efficiency(useful_tool_calls, total_tool_calls))
    metrics.add_metric(compute_response_quality(relevance_scores))
    metrics.add_metric(compute_latency(latencies))
    metrics.add_metric(compute_resource_usage(token_usage, api_calls))

    return metrics