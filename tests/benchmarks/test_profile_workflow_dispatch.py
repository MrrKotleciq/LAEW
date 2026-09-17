"""Benchmark: ``WorkflowEngine`` dispatching a sequential no-op tool plan.

Offline baseline for the workflow hot path: step dispatch, approval-gate
checks, rollback-bookkeeping, and context accumulation across a fixed-length
sequential plan. No-op steps keep the measurement to engine overhead.

Tolerances are informational only — these tests record numbers for
``docs/performance/BASELINE.md``, they do not gate on wall clock.
"""

from laew.tools.base import Tool, ToolResult
from laew.workflow.definition import (
    StepType,
    WorkflowDefinition,
    WorkflowMode,
    WorkflowStep,
)
from laew.workflow.engine import WorkflowEngine

PLAN_STEPS = 20  # sequential no-op tool steps per run


class _NoopTool(Tool):
    """Tool whose operations succeed immediately."""

    def validate(self, operation: str, **kwargs) -> tuple:
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        return ToolResult(success=True, data={"operation": operation})


def _make_definition(steps: int) -> WorkflowDefinition:
    """A sequential automatic plan of ``steps`` no-op tool steps."""
    return WorkflowDefinition(
        name="bench-plan",
        description="Benchmark sequential no-op plan",
        mode=WorkflowMode.AUTOMATIC,
        steps=[
            WorkflowStep(
                id=f"s{i:02d}",
                name=f"noop-{i}",
                type=StepType.TOOL,
                tool="stub",
                operation="noop",
                arguments={"index": i},
            )
            for i in range(steps)
        ],
    )


def _make_engine(steps: int) -> WorkflowEngine:
    return WorkflowEngine(
        _make_definition(steps),
        tool_registry={"stub": _NoopTool()},
    )


def test_profile_workflow_sequential_run(benchmark):
    """Wall clock of running a 20-step sequential no-op plan."""
    engine = _make_engine(PLAN_STEPS)
    benchmark(engine.run)
    # After a successful run every step produced execution context.
    assert len(engine.execution_context) == PLAN_STEPS


def test_profile_workflow_large_plan(benchmark):
    """Wall clock of running a 60-step sequential no-op plan."""
    engine = _make_engine(60)
    benchmark(engine.run)
    assert len(engine.execution_context) == 60


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])