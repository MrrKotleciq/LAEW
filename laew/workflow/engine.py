from typing import Any, Dict, List, Optional
from laew.workflow.definition import WorkflowDefinition, WorkflowStep, StepType, WorkflowMode
from laew.workflow.exceptions import WorkflowExecutionError, ApprovalRequiredError
from laew.workflow.approval import ApprovalGate
from laew.workflow.rollback import RollbackEngine

class WorkflowEngine:
    """Orchestrates workflow execution."""

    def __init__(self, definition: WorkflowDefinition):
        self.definition = definition
        self.approval_gate = ApprovalGate()
        self.execution_context: Dict[str, Any] = {}
        self.rollback_engine = RollbackEngine(self.execution_context)

    def run(self):
        """Runs the workflow based on its mode."""
        if self.definition.mode == WorkflowMode.DISABLED:
            return

        # Simple sequential execution (simplified for now)
        for step in self.definition.steps:
            if self.definition.mode == WorkflowMode.MANUAL or step.approval_required:
                if not self.approval_gate.is_step_approved(self.definition.name, step.id):
                    raise ApprovalRequiredError(f"Step {step.id} requires approval")

            try:
                self._execute_step(step)
                if step.rollback:
                    self.rollback_engine.push_rollback(step.rollback)
            except Exception as e:
                self.rollback_engine.execute_all()
                raise WorkflowExecutionError(f"Step {step.id} failed: {e}")

    def _execute_step(self, step: WorkflowStep):
        """Executes a single step."""
        if step.type == StepType.TOOL:
            print(f"Executing tool: {step.tool} - {step.operation}")
            # Actual tool execution
        elif step.type == StepType.AGENT:
            print(f"Executing agent: {step.agent_role}")
            # Actual agent execution