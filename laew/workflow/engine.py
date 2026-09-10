from typing import Any, Dict, List, Optional
from laew.workflow.definition import WorkflowDefinition, WorkflowStep, StepType, WorkflowMode
from laew.workflow.exceptions import WorkflowExecutionError, ApprovalRequiredError
from laew.workflow.approval import ApprovalGate
from laew.workflow.rollback import RollbackEngine
from laew.tools.base import Tool, ToolResult

class WorkflowEngine:
    """Orchestrates workflow execution."""

    def __init__(
        self,
        definition: WorkflowDefinition,
        tool_registry: Optional[Dict[str, Tool]] = None,
        agent_executor: Optional[Any] = None,
    ):
        """
        Initialize engine.

        Args:
            definition: Workflow definition to execute
            tool_registry: Mapping of tool name -> Tool instance used to
                dispatch TOOL steps (and matching rollback actions).
            agent_executor: Optional AgentExecutor used to dispatch AGENT steps.
        """
        self.definition = definition
        self.tool_registry = tool_registry or {}
        self.agent_executor = agent_executor
        self.approval_gate = ApprovalGate()
        self.execution_context: Dict[str, Any] = {}
        self.rollback_engine = RollbackEngine(
            self.execution_context,
            tool_registry=self.tool_registry,
            agent_executor=self.agent_executor,
        )

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

    def _resolve_tool(self, requested: str) -> Optional[Tool]:
        """
        Resolve a workflow-declared tool name to a registered Tool instance.

        Accepts an exact registry key first, then a case-insensitive match, then
        a match against the class name with the trailing 'Tool' suffix removed
        (so 'filesystem' resolves to 'FilesystemTool').
        """
        if requested in self.tool_registry:
            return self.tool_registry[requested]

        requested_lower = requested.lower()
        for registered, tool in self.tool_registry.items():
            if registered.lower() == requested_lower:
                return tool
            # 'FilesystemTool' -> 'filesystem'
            if registered.lower().endswith("tool") and registered.lower()[:-4] == requested_lower:
                return tool
        return None

    def _execute_step(self, step: WorkflowStep):
        """Executes a single step by dispatching to the configured runtime."""
        if step.type == StepType.TOOL:
            tool = self._resolve_tool(step.tool or "")
            if tool is None:
                raise WorkflowExecutionError(
                    f"Step {step.id}: cannot execute tool step - "
                    f"tool '{step.tool}' not found in the tool registry"
                )
            result = tool.call(step.operation or "", **step.arguments)
            self.execution_context[step.id] = {
                "tool": step.tool,
                "operation": step.operation,
                "result": result,
            }
            if not result.success:
                raise WorkflowExecutionError(
                    f"Step {step.id}: tool '{step.tool}' operation "
                    f"'{step.operation}' failed: {result.error_message}"
                )
        elif step.type == StepType.AGENT:
            if self.agent_executor is None:
                raise WorkflowExecutionError(
                    f"Step {step.id}: cannot execute agent step - "
                    "no agent executor was provided to WorkflowEngine"
                )
            execution_result = self.agent_executor.run(step.prompt or "")
            self.execution_context[step.id] = {
                "agent_role": step.agent_role,
                "result": execution_result,
            }
            if not execution_result.success:
                raise WorkflowExecutionError(
                    f"Step {step.id}: agent step failed: {execution_result.error}"
                )
        else:
            raise WorkflowExecutionError(
                f"Step {step.id}: unsupported step type: {step.type}"
            )