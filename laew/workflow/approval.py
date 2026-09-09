from typing import Optional
from laew.tools.base import Tool, ToolResult

class ApprovalGate:
    """Manages approval for workflow steps."""

    def __init__(self):
        self._approved_steps: set[str] = set()

    def is_step_approved(self, workflow_id: str, step_id: str, tool: Optional[Tool] = None) -> bool:
        """Checks if a step is approved."""
        if f"{workflow_id}:{step_id}" in self._approved_steps:
            return True

        if tool and tool.is_approved():
            return True

        return False

    def approve_step(self, workflow_id: str, step_id: str):
        """Grants approval for a step."""
        self._approved_steps.add(f"{workflow_id}:{step_id}")