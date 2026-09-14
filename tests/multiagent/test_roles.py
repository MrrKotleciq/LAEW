"""Tests for multi-agent specialist role definitions (ADR-018)."""

from laew.multiagent.roles import (
    ROLE_PROMPT_NAMES,
    ROLE_REQUIREMENTS,
    SpecialistRole,
    build_specialist_system_prompt,
    role_description,
)


def test_all_six_roles_defined():
    """The six documented specialist roles exist."""
    expected = {
        SpecialistRole.RESEARCHER,
        SpecialistRole.ARCHITECT,
        SpecialistRole.REVIEWER,
        SpecialistRole.DEBUGGER,
        SpecialistRole.DOCUMENTER,
        SpecialistRole.CODER,
    }
    assert set(SpecialistRole) == expected


def test_role_values():
    assert SpecialistRole.RESEARCHER.value == "researcher"
    assert SpecialistRole.ARCHITECT.value == "architect"
    assert SpecialistRole.REVIEWER.value == "reviewer"
    assert SpecialistRole.DEBUGGER.value == "debugger"
    assert SpecialistRole.DOCUMENTER.value == "documenter"
    assert SpecialistRole.CODER.value == "coder"


def test_every_role_has_requirement():
    for role in SpecialistRole:
        assert role in ROLE_REQUIREMENTS
        assert ROLE_REQUIREMENTS[role].strip()


def test_every_role_has_prompt_name():
    for role in SpecialistRole:
        assert role in ROLE_PROMPT_NAMES
        assert ROLE_PROMPT_NAMES[role].strip()


def test_prompt_names_refer_to_existing_templates():
    """Every role maps to an existing, loadable prompt template name."""
    from laew.prompts.loader import load_prompt

    for role in SpecialistRole:
        template_name = ROLE_PROMPT_NAMES[role]
        prompt = load_prompt(template_name)
        assert prompt.render().strip()  # loadable and non-empty


def test_role_description_returns_requirement():
    for role in SpecialistRole:
        assert role_description(role) == ROLE_REQUIREMENTS[role]
        assert role_description(role).strip()


def test_build_specialist_system_prompt_includes_core():
    """The specialist prompt layers role requirements over the core prompt."""
    prompt = build_specialist_system_prompt(SpecialistRole.REVIEWER)
    assert "LAEW (Local AI Engineering Workspace)" in prompt
    assert "Identity & Operating Environment" in prompt


def test_build_specialist_system_prompt_includes_role_requirement():
    prompt = build_specialist_system_prompt(SpecialistRole.DEBUGGER)
    assert "Diagnose failures" in prompt
    assert "root causes" in prompt


def test_build_specialist_system_prompt_includes_role_template():
    """The role-specific layered template content is layered in."""
    prompt = build_specialist_system_prompt(SpecialistRole.ARCHITECT)
    assert "architecture" in prompt.lower() or "Architect" in prompt


def test_build_specialist_prompt_distinct_per_role():
    """Different roles produce different system prompts."""
    researcher = build_specialist_system_prompt(SpecialistRole.RESEARCHER)
    coder = build_specialist_system_prompt(SpecialistRole.CODER)
    assert researcher != coder