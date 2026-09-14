"""Specialist role definitions and prompt building for the LAEW multi-agent runtime.

Defines the six specialist roles used in multi-agent delegation (ADR-018) and
provides helpers to build role-specific system prompts by mapping each role to
its corresponding layered prompt template (principle P3, reuse existing assets).
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class SpecialistRole(Enum):
    """The six specialist roles available for multi-agent delegation."""

    RESEARCHER = "researcher"
    ARCHITECT = "architect"
    REVIEWER = "reviewer"
    DEBUGGER = "debugger"
    DOCUMENTER = "documenter"
    CODER = "coder"


# Role requirement descriptions used when constructing the specialist system
# prompt. These are short imperative sentences that tell the model what the
# role should focus on.
ROLE_REQUIREMENTS: Dict[SpecialistRole, str] = {
    SpecialistRole.RESEARCHER: (
        "Gather relevant facts, precedents, and external knowledge. "
        "Summarize findings with sources."
    ),
    SpecialistRole.ARCHITECT: (
        "Propose structural or architectural changes. "
        "Focus on components, interfaces, and long-term maintainability."
    ),
    SpecialistRole.REVIEWER: (
        "Critically examine the work for correctness, completeness, and style. "
        "Identify gaps, inconsistencies, and potential improvements."
    ),
    SpecialistRole.DEBUGGER: (
        "Diagnose failures, trace root causes, and suggest concrete fixes. "
        "Think like a debugger stepping through execution."
    ),
    SpecialistRole.DOCUMENTER: (
        "Explain concepts clearly and produce structured documentation. "
        "Write for a future maintainer who needs to understand the system."
    ),
    SpecialistRole.CODER: (
        "Write clean, idiomatic code that solves the stated problem. "
        "Follow existing patterns and include error handling."
    ),
}

# Mapping from role to the name of the layered prompt template that already
# exists in `laew/prompts/templates.py`. Reusing these templates keeps the
# specialist behavior consistent with the single-agent chief/sub-agent split.
ROLE_PROMPT_NAMES: Dict[SpecialistRole, str] = {
    SpecialistRole.RESEARCHER: "research",
    SpecialistRole.ARCHITECT: "architecture",
    SpecialistRole.REVIEWER: "code-review",
    SpecialistRole.DEBUGGER: "debugging",
    SpecialistRole.DOCUMENTER: "documentation",
    SpecialistRole.CODER: "core",  # generic coding falls back to core
}


def role_description(role: SpecialistRole) -> str:
    """Return the one-sentence requirement description for a role."""
    return ROLE_REQUIREMENTS[role]


def build_specialist_system_prompt(role: SpecialistRole) -> str:
    """Assemble the system prompt for a specialist agent.

    The prompt combines:
    1. The universal LAEW core prompt (identity, principles, available tools).
    2. The role-specific requirement sentence from `ROLE_REQUIREMENTS`.
    3. The layered prompt template matched to the role (see `ROLE_PROMPT_NAMES`).

    Args:
        role: The specialist role to build a prompt for.

    Returns:
        A complete system prompt string ready for an AgentConfig.
    """
    from laew.prompts.loader import load_prompt

    # Start with the universal core prompt (tools, identity, principles)
    prompt = load_prompt("core").render()

    # Add the role-specific imperative
    prompt += f"\n\nRole requirement: {role_description(role)}"

    # Finally, layer the existing prompt template for this role
    template_name = ROLE_PROMPT_NAMES[role]
    prompt += f"\n\n{load_prompt(template_name).render()}"

    return prompt.strip()


def underlying_agent_role(role: SpecialistRole) -> str:
    """Map a SpecialistRole to the laew.agent.base.AgentRole enum value.

    Specialist agents are technically SPECIALIST agent roles; the chief
    agent uses CHIEF. This helper keeps the mapping explicit.
    """
    return "SPECIALIST"