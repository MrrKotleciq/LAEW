import yaml
from pathlib import Path
from typing import Dict, Any

from laew.workflow.definition import WorkflowDefinition, WorkflowStep, RollbackConfig, WorkflowMode, StepType


class WorkflowValidationError(Exception):
    """Raised when workflow YAML is invalid."""
    pass


def load_workflow_from_yaml(yaml_path: Path) -> WorkflowDefinition:
    """Loads and validates a workflow from a YAML file."""
    if not yaml_path.exists():
        raise WorkflowValidationError(f"Workflow file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise WorkflowValidationError(f"Invalid YAML format: {e}")

    return _parse_workflow(data)


def _parse_workflow(data: Dict[str, Any]) -> WorkflowDefinition:
    """Parses raw dict into WorkflowDefinition."""
    try:
        mode = WorkflowMode(data.get("mode", WorkflowMode.AUTOMATIC))

        steps = []
        for step_data in data.get("steps", []):
            rollback = None
            if "rollback" in step_data:
                rollback_data = step_data["rollback"]
                rollback = RollbackConfig(
                    type=StepType(rollback_data["type"]),
                    tool=rollback_data.get("tool"),
                    operation=rollback_data.get("operation"),
                    agent_role=rollback_data.get("agent_role"),
                    arguments=rollback_data.get("arguments", {}),
                )

            step = WorkflowStep(
                id=step_data["id"],
                name=step_data["name"],
                type=StepType(step_data["type"]),
                tool=step_data.get("tool"),
                operation=step_data.get("operation"),
                agent_role=step_data.get("agent_role"),
                prompt=step_data.get("prompt"),
                arguments=step_data.get("arguments", {}),
                approval_required=step_data.get("approval_required", False),
                rollback=rollback,
                on_success=step_data.get("on_success", []),
                on_failure=step_data.get("on_failure", []),
            )
            steps.append(step)

        return WorkflowDefinition(
            name=data["name"],
            description=data["description"],
            mode=mode,
            steps=steps
        )
    except (KeyError, ValueError) as e:
        raise WorkflowValidationError(f"Invalid workflow definition structure: {e}")