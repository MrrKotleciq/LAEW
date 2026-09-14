"""Multi-agent plan schema and YAML loading.

Defines the data structures for a multi-agent delegation plan and provides
functions to load such a plan from a YAML file (ADR-018). The plan lists
subtasks, each assigned to a specialist role, and an optional synthesis
step for the chief agent to produce a final answer.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import yaml

from laew.multiagent.roles import SpecialistRole


class MultiAgentPlanError(Exception):
    """Raised when a multi-agent plan is malformed or cannot be loaded."""
    pass


@dataclass(frozen=True)
class SubTask:
    """A single unit of work delegated to a specialist agent.

    Attributes:
        id: Stable identifier for the subtask (used in messages and reporting).
        role: The specialist role that should perform the work.
        prompt: The natural-language instruction for the specialist.
        deliverable: A short name for the expected output (used as context key).
    """

    id: str
    role: SpecialistRole
    prompt: str
    deliverable: str


@dataclass(frozen=True)
class MultiAgentPlan:
    """The complete multi-agent delegation plan.

    Attributes:
        name: Human-readable name of the plan.
        objective: The overall goal that the plan seeks to achieve.
        subtasks: Ordered list of subtasks to delegate to specialists.
        synthesize: If True, the chief agent will synthesize the results
            into a final response after all subtasks complete.
    """

    name: str
    objective: str
    subtasks: List[SubTask]
    synthesize: bool = True


def _load_role(value: str) -> SpecialistRole:
    """Convert a string from YAML to a SpecialistRole enum member."""
    try:
        return SpecialistRole[value.upper()]
    except KeyError as exc:
        valid = [r.name for r in SpecialistRole]
        raise MultiAgentPlanError(
            f"Unknown specialist role '{value}'. Valid roles: {', '.join(valid)}"
        ) from exc


def parse_multiagent_plan(data: dict) -> MultiAgentPlan:
    """Parse a dictionary (from YAML) into a MultiAgentPlan.

    Expected structure:
    ---
    name: string
    objective: string
    synthesize: boolean (optional, default true)
    subtasks:
      - id: string
        role: string  # one of researcher, architect, reviewer, debugger, documenter, coder
        prompt: string
        deliverable: string

    Raises:
        MultiAgentPlanError: If the structure is invalid or a role is unknown.
    """
    if not isinstance(data, dict):
        raise MultiAgentPlanError("Plan YAML must be a mapping at the top level")

    # Required top-level fields
    name = data.get("name")
    if not name or not isinstance(name, str):
        raise MultiAgentPlanError("Plan must contain a non-empty string 'name'")

    objective = data.get("objective")
    if not objective or not isinstance(objective, str):
        raise MultiAgentPlanError("Plan must contain a non-empty string 'objective'")

    # Optional synthesize flag
    synthesize = data.get("synthesize", True)
    if not isinstance(synthesize, bool):
        raise MultiAgentPlanError("The 'synthesize' field must be a boolean if present")

    # Subtasks
    subtasks_raw = data.get("subtasks")
    if not isinstance(subtasks_raw, list):
        raise MultiAgentPlanError("Plan must contain a 'subtasks' list")

    subtasks: List[SubTask] = []
    for idx, entry in enumerate(subtasks_raw):
        if not isinstance(entry, dict):
            raise MultiAgentPlanError(f"Subtask #{idx} must be a mapping")

        sub_id = entry.get("id")
        if not sub_id or not isinstance(sub_id, str):
            raise MultiAgentPlanError(f"Subtask #{idx} must contain a non-empty string 'id'")

        role_raw = entry.get("role")
        if not role_raw or not isinstance(role_raw, str):
            raise MultiAgentPlanError(f"Subtask #{idx} must contain a string 'role'")
        role = _load_role(role_raw)

        prompt = entry.get("prompt")
        if not prompt or not isinstance(prompt, str):
            raise MultiAgentPlanError(f"Subtask #{idx} must contain a non-empty string 'prompt'")

        deliverable = entry.get("deliverable")
        if not deliverable or not isinstance(deliverable, str):
            raise MultiAgentPlanError(f"Subtask #{idx} must contain a non-empty string 'deliverable'")

        subtasks.append(
            SubTask(
                id=sub_id,
                role=role,
                prompt=prompt.strip(),
                deliverable=deliverable.strip(),
            )
        )

    if not subtasks:
        raise MultiAgentPlanError("Plan must contain at least one subtask")

    return MultiAgentPlan(
        name=name.strip(),
        objective=objective.strip(),
        subtasks=subtasks,
        synthesize=synthesize,
    )


def load_multiagent_plan_from_yaml(path: str) -> MultiAgentPlan:
    """Load a multi-agent plan from a YAML file.

    Args:
        path: Path to the YAML file.

    Returns:
        The parsed MultiAgentPlan.

    Raises:
        MultiAgentPlanError: If the file cannot be read, is not valid YAML,
            or fails validation.
        FileNotFoundError: If the file does not exist.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise
    except yaml.YAMLError as exc:
        raise MultiAgentPlanError(f"Invalid YAML: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise MultiAgentPlanError(f"Unable to read plan file: {exc}") from exc

    return parse_multiagent_plan(data)