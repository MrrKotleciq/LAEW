from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkflowMode(str, Enum):
    """Execution modes for workflows per ADR-015."""
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    DISABLED = "disabled"


class StepType(str, Enum):
    """Supported step types."""
    TOOL = "tool"
    AGENT = "agent"
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class RollbackConfig:
    """Compensating action configuration."""
    type: StepType
    tool: Optional[str] = None
    operation: Optional[str] = None
    agent_role: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowStep:
    """Definition of a single workflow step."""
    id: str
    name: str
    type: StepType

    # Tool specific
    tool: Optional[str] = None
    operation: Optional[str] = None

    # Agent specific
    agent_role: Optional[str] = None
    prompt: Optional[str] = None

    arguments: Dict[str, Any] = field(default_factory=dict)
    approval_required: bool = False

    rollback: Optional[RollbackConfig] = None
    on_success: List[str] = field(default_factory=list)
    on_failure: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class WorkflowDefinition:
    """Full workflow definition."""
    name: str
    description: str
    mode: WorkflowMode
    steps: List[WorkflowStep]
