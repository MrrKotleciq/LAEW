"""Multi-agent coordination for LAEW.

Public API for the multi-agent runtime (ADR-018):
- Messages: :class:`AgentMessage`, :class:`MessageKind`
- Shared context: :class:`SharedContext`, :class:`SharedContextItem`
- Specialist roles: :class:`SpecialistRole`, :func:`build_specialist_system_prompt`
- Plans: :class:`MultiAgentPlan`, :class:`SubTask`, :func:`load_multiagent_plan_from_yaml`
- Coordination: :class:`MultiAgentCoordinator`, :class:`DelegationResult`,
  :class:`Conflict`, :class:`MultiAgentResult`
"""

from laew.multiagent.message import AgentMessage, MessageKind
from laew.multiagent.context import SharedContext, SharedContextItem
from laew.multiagent.roles import (
    ROLE_PROMPT_NAMES,
    ROLE_REQUIREMENTS,
    SpecialistRole,
    build_specialist_system_prompt,
    role_description,
)
from laew.multiagent.plan import (
    MultiAgentPlan,
    MultiAgentPlanError,
    SubTask,
    load_multiagent_plan_from_yaml,
    parse_multiagent_plan,
)
from laew.multiagent.coordinator import (
    Conflict,
    DelegationResult,
    MultiAgentCoordinator,
    MultiAgentResult,
)

__all__ = [
    "AgentMessage",
    "MessageKind",
    "SharedContext",
    "SharedContextItem",
    "ROLE_PROMPT_NAMES",
    "ROLE_REQUIREMENTS",
    "SpecialistRole",
    "build_specialist_system_prompt",
    "role_description",
    "MultiAgentPlan",
    "MultiAgentPlanError",
    "SubTask",
    "load_multiagent_plan_from_yaml",
    "parse_multiagent_plan",
    "Conflict",
    "DelegationResult",
    "MultiAgentCoordinator",
    "MultiAgentResult",
]