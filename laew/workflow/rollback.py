import logging
from typing import Any, Dict, List, Optional
from laew.workflow.definition import WorkflowStep, RollbackConfig, StepType
from laew.workflow.exceptions import WorkflowExecutionError, RollbackError
from laew.tools.base import Tool, ToolResult

logger = logging.getLogger("laew.workflow.rollback")

class RollbackEngine:
    """Handles compensating actions for workflow steps."""

    def __init__(
        self,
        execution_context: Dict[str, Any],
        tool_registry: Optional[Dict[str, Tool]] = None,
        agent_executor: Optional[Any] = None,
    ):
        self.execution_context = execution_context
        self.tool_registry = tool_registry or {}
        self.agent_executor = agent_executor
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
        """Executes a single rollback action by dispatching a real compensating call."""
        try:
            if rollback.type == StepType.TOOL:
                tool = self._resolve_tool(rollback.tool or "")
                if tool is None:
                    logger.warning(
                        "Skipping rollback tool '%s': not found in tool registry",
                        rollback.tool,
                    )
                    return
                result = tool.call(rollback.operation or "", **rollback.arguments)
                self.execution_context[f"rollback:{rollback.tool}:{rollback.operation}"] = result
                if not result.success:
                    raise RollbackError(
                        f"Rollback tool '{rollback.tool}' operation "
                        f"'{rollback.operation}' failed: {result.error_message}"
                    )
            elif rollback.type == StepType.AGENT:
                if self.agent_executor is None:
                    logger.warning(
                        "Skipping rollback agent '%s': no agent executor configured",
                        rollback.agent_role,
                    )
                    return
                execution_result = self.agent_executor.run(rollback.arguments.get("prompt", ""))
                if not execution_result.success:
                    raise RollbackError(
                        f"Rollback agent '{rollback.agent_role}' failed: {execution_result.error}"
                    )
            else:
                raise RollbackError(
                    f"Rollback type not supported: {rollback.type}"
                )
        except RollbackError:
            raise
        except Exception as e:
            raise RollbackError(f"Rollback failed: {e}")

    def _resolve_tool(self, requested: str) -> Optional[Tool]:
        """Resolve a rollback-declared tool name to a registered Tool instance."""
        if requested in self.tool_registry:
            return self.tool_registry[requested]

        requested_lower = requested.lower()
        for registered, tool in self.tool_registry.items():
            if registered.lower() == requested_lower:
                return tool
            if registered.lower().endswith("tool") and registered.lower()[:-4] == requested_lower:
                return tool
        return None
