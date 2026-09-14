"""Tests for the multi-agent plan schema and YAML loading (ADR-018)."""

from pathlib import Path

import pytest

from laew.multiagent.plan import (
    MultiAgentPlan,
    MultiAgentPlanError,
    SubTask,
    load_multiagent_plan_from_yaml,
    parse_multiagent_plan,
)
from laew.multiagent.roles import SpecialistRole

FIXTURE = Path(__file__).parent / "test_plan.yaml"


class TestParseMultiAgentPlan:
    def test_valid_plan(self):
        plan = parse_multiagent_plan(
            {
                "name": "Plan A",
                "objective": "Improve the codebase",
                "synthesize": True,
                "subtasks": [
                    {
                        "id": "r1",
                        "role": "researcher",
                        "prompt": "Research the codebase.",
                        "deliverable": "findings",
                    }
                ],
            }
        )
        assert plan.name == "Plan A"
        assert plan.objective == "Improve the codebase"
        assert plan.synthesize is True
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].id == "r1"
        assert plan.subtasks[0].role is SpecialistRole.RESEARCHER

    def test_synthesize_defaults_to_true(self):
        plan = parse_multiagent_plan(
            {
                "name": "Plan B",
                "objective": "Do things",
                "subtasks": [
                    {
                        "id": "s1",
                        "role": "coder",
                        "prompt": "Write some code.",
                        "deliverable": "code",
                    }
                ],
            }
        )
        assert plan.synthesize is True

    def test_synthesize_false(self):
        plan = parse_multiagent_plan(
            {
                "name": "Plan C",
                "objective": "Do things",
                "synthesize": False,
                "subtasks": [
                    {
                        "id": "s1",
                        "role": "coder",
                        "prompt": "Write some code.",
                        "deliverable": "code",
                    }
                ],
            }
        )
        assert plan.synthesize is False

    def test_role_case_insensitive(self):
        plan = parse_multiagent_plan(
            {
                "name": "Plan D",
                "objective": "Do things",
                "subtasks": [
                    {
                        "id": "d1",
                        "role": "REVIEWER",
                        "prompt": "Review.",
                        "deliverable": "review",
                    }
                ],
            }
        )
        assert plan.subtasks[0].role is SpecialistRole.REVIEWER

    def test_unknown_role_raises(self):
        with pytest.raises(MultiAgentPlanError) as exc_info:
            parse_multiagent_plan(
                {
                    "name": "Plan E",
                    "objective": "Do things",
                    "subtasks": [
                        {
                            "id": "e1",
                            "role": "wizard",
                            "prompt": "Cast a spell.",
                            "deliverable": "spell",
                        }
                    ],
                }
            )
        assert "Unknown specialist role" in str(exc_info.value)

    def test_missing_name_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(
                {
                    "objective": "Do things",
                    "subtasks": [],
                }
            )

    def test_missing_objective_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(
                {
                    "name": "Plan F",
                    "subtasks": [],
                }
            )

    def test_no_subtasks_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(
                {
                    "name": "Plan G",
                    "objective": "Do things",
                    "subtasks": [],
                }
            )

    def test_subtask_missing_fields_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(
                {
                    "name": "Plan H",
                    "objective": "Do things",
                    "subtasks": [
                        {"id": "h1", "role": "coder"}  # missing prompt/deliverable
                    ],
                }
            )

    def test_non_mapping_top_level_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(["not", "a", "mapping"])  # type: ignore

    def test_non_boolean_synthesize_raises(self):
        with pytest.raises(MultiAgentPlanError):
            parse_multiagent_plan(
                {
                    "name": "Plan I",
                    "objective": "Do things",
                    "synthesize": "yes",
                    "subtasks": [
                        {
                            "id": "i1",
                            "role": "coder",
                            "prompt": "Code.",
                            "deliverable": "code",
                        }
                    ],
                }
            )

    def test_prompt_and_deliverable_trimmed(self):
        plan = parse_multiagent_plan(
            {
                "name": "Plan J",
                "objective": "Do things",
                "subtasks": [
                    {
                        "id": "j1",
                        "role": "coder",
                        "prompt": "  Write code.  ",
                        "deliverable": "  code  ",
                    }
                ],
            }
        )
        assert plan.subtasks[0].prompt == "Write code."
        assert plan.subtasks[0].deliverable == "code"


class TestLoadFromYAML:
    def test_loads_fixture(self):
        plan = load_multiagent_plan_from_yaml(str(FIXTURE))
        assert isinstance(plan, MultiAgentPlan)
        assert plan.name == "Test Documentation Review Plan"
        assert "API documentation" in plan.objective
        assert len(plan.subtasks) == 2
        assert plan.subtasks[0].role is SpecialistRole.RESEARCHER
        assert plan.subtasks[1].role is SpecialistRole.REVIEWER

    def test_fixture_subtask_ids(self):
        plan = load_multiagent_plan_from_yaml(str(FIXTURE))
        assert [s.id for s in plan.subtasks] == ["research-1", "review-1"]
        assert [s.deliverable for s in plan.subtasks] == [
            "api_endpoints",
            "doc_issues",
        ]

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_multiagent_plan_from_yaml(str(FIXTURE.parent / "does_not_exist.yaml"))

    def test_invalid_yaml_raises_plan_error(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("name: [unclosed", encoding="utf-8")
        with pytest.raises(MultiAgentPlanError) as exc_info:
            load_multiagent_plan_from_yaml(str(bad))
        assert "YAML" in str(exc_info.value)


class TestSubTask:
    def test_subtask_is_frozen(self):
        import dataclasses

        st = SubTask(
            id="x",
            role=SpecialistRole.CODER,
            prompt="p",
            deliverable="d",
        )
        assert dataclasses.is_dataclass(st)
        assert st.__dataclass_params__.frozen