"""LAEW Evaluation Harness.

Provides systematic evaluation of agent and RAG quality through:
- Metrics for task success, tool usage efficiency, response quality
- Benchmark datasets for LAEW-specific and general reasoning tasks
- Evaluation runner for executing tasks and generating reports
"""

from laew.eval.metrics import (
    EvaluationMetrics,
    MetricResult,
    compute_task_success_rate,
    compute_tool_usage_efficiency,
    compute_response_quality,
    compute_latency,
    compute_resource_usage,
)
from laew.eval.tasks import EvaluationTask, TaskRegistry, load_dataset
from laew.eval.runner import EvaluationRunner, EvaluationReport

__all__ = [
    "EvaluationMetrics",
    "MetricResult",
    "compute_task_success_rate",
    "compute_tool_usage_efficiency",
    "compute_response_quality",
    "compute_latency",
    "compute_resource_usage",
    "EvaluationTask",
    "TaskRegistry",
    "load_dataset",
    "EvaluationRunner",
    "EvaluationReport",
]