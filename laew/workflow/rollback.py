from typing import Any, Dict, List, Optional
from laew.workflow.definition import WorkflowStep, RollbackConfig, StepType
from laew.workflow.exceptions import WorkflowExecutionError, RollbackError

class RollbackEngine:
    """Handles compensating actions for workflow steps."""

    def __init__(self, execution_context: Dict[str, Any]):
        self.execution_context = execution_context
        self._rollback_stack: List[RollbackConfig] = []

    def push_rollback(self, rollback: RollbackConfig):
        """Pushes a rollback action to the stack."""
        self._rollback_stack.append(rollback)

    def execute_all(self):
        """Executes all rollbacks in reverse order."""
        while self._rollback_stack:
            rollback = self._rollback_stack.pop()
            self._execute_rollback(rollback)

    def _execute_rollback(self, rollback: RollbackConfig):
        """Executes a single rollback action."""
        # Logic to map RollbackConfig to actual tool/agent execution
        try:
            if rollback.type == StepType.TOOL:
                print(f"Executing rollback: Tool {rollback.tool} - {rollback.operation}")
                # Actual tool call logic goes here (e.g. tool_registry.get(rollback.tool).execute(...))
            elif rollback.type == StepType.AGENT:
                print(f"Executing rollback: Agent {rollback.agent_role}")
                # Actual agent call logic goes here
        except Exception as e:
            raise RollbackError(f"Rollback failed: {e}")
