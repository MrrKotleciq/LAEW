"""Tests for the multi-agent coordinator runtime (ADR-018).

The coordinator's LLM boundary (AgentExecutor.run) is patched out so the
tests exercise coordination logic — delegation ordering, failure isolation,
shared-context population, conflict detection, and chief synthesis — without
requiring a live model.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from laew.multiagent.coordinator import (
    Conflict,
    DelegationResult,
    MultiAgentCoordinator,
    MultiAgentResult,
)
from laew.multiagent.plan import MultiAgentPlan, SubTask
from laew.multiagent.roles import SpecialistRole


def _plan(subtasks, objective="Objective", synthesize=True):
    """Build a MultiAgentPlan from a list of (role, deliverable[, prompt]) tuples."""
    parsed = [
        SubTask(
            id=f"{role.value}-{idx}",
            role=role,
            prompt=prompt or f"Task for {role.value}",
            deliverable=deliverable,
        )
        for idx, (role, deliverable, prompt) in enumerate(subtasks)
    ]
    return MultiAgentPlan(
        name="test-plan",
        objective=objective,
        subtasks=parsed,
        synthesize=synthesize,
    )


def _make_agents(*roles):
    """Return a chief + specialist dict using MagicMock agents."""
    chief = MagicMock()
    agents = {role: MagicMock() for role in roles}
    return chief, agents


class TestDelegationResult:
    def test_is_frozen(self):
        import dataclasses

        result = DelegationResult(
            role=SpecialistRole.CODER,
            subtask_id="c1",
            deliverable="code",
            success=True,
        )
        assert dataclasses.is_dataclass(result)
        assert result.__dataclass_params__.frozen

    def test_fields_defaults(self):
        result = DelegationResult(
            role=SpecialistRole.CODER,
            subtask_id="c1",
            deliverable="code",
            success=True,
            output="great code",
        )
        assert result.error == ""
        assert result.message is None


class TestRunSuccess:
    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_successful_delegations(self, MockExecutor):
        """Subtask outputs are collected and flagged successful."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True,
            final_response="  The answer is 42",
            error=None,
        )
        chief, agents = _make_agents(SpecialistRole.CODER, SpecialistRole.REVIEWER)
        coordinator = MultiAgentCoordinator(chief=chief, agents=agents)

        plan = _plan(
            [
                (SpecialistRole.CODER, "code", "Write code."),
                (SpecialistRole.REVIEWER, "review", "Review."),
            ],
            synthesize=False,
        )
        result = coordinator.run(plan)

        assert result.success is True
        assert len(result.delegations) == 2
        assert all(d.success for d in result.delegations)
        # Outputs are trimmed of surrounding whitespace.
        assert result.delegations[0].output == "The answer is 42"
        assert result.delegations[1].output == "The answer is 42"
        assert MockExecutor.call_count == 2

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_shared_context_populated(self, MockExecutor):
        """Successful outputs are posted to the shared context journal."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True,
            final_response="finding one",
            error=None,
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.RESEARCHER: MagicMock()},
        )
        plan = _plan([(SpecialistRole.RESEARCHER, "finding", "Find something.")])
        result = coordinator.run(plan)

        assert result.context.get("finding") is not None
        assert result.context.get("finding").content == "finding one"
        assert result.context.get("finding").source == "researcher"


class TestRunFailure:
    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_failing_delegation_is_isolated(self, MockExecutor):
        """A specialist failure does not abort the run and is recorded."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=False,
            final_response="",
            error="provider unreachable",
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.CODER: MagicMock()},
        )
        plan = _plan([(SpecialistRole.CODER, "code", "Write code.")], synthesize=False)
        result = coordinator.run(plan)

        assert result.success is False
        assert result.delegations[0].success is False
        assert result.delegations[0].error == "provider unreachable"
        assert "All specialist delegations failed" in result.error
        # Failure is also posted to shared context under the error key.
        assert result.context.get("code:error") is not None

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_unknown_role_agent_raises_key_error(self, MockExecutor):
        """Delegating to a role with no registered agent raises KeyError."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True, final_response="x", error=None
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.RESEARCHER: MagicMock()},
        )
        with pytest.raises(KeyError):
            coordinator.run(
                _plan([(SpecialistRole.ARCHITECT, "arch", "Architect the fix.")])
            )


class TestConflictDetection:
    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_conflicting_outputs_reported(self, MockExecutor):
        """Two specialists disagreeing on the same deliverable produce a Conflict."""
        responses = iter(
            [
                SimpleNamespace(success=True, final_response="Use postgres", error=None),
                SimpleNamespace(success=True, final_response="Use sqlite", error=None),
            ]
        )
        MockExecutor.return_value.run.side_effect = lambda *a, **k: next(responses)

        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={
                SpecialistRole.RESEARCHER: MagicMock(),
                SpecialistRole.ARCHITECT: MagicMock(),
            },
        )
        plan = _plan(
            [
                (SpecialistRole.RESEARCHER, "db_choice", "Which db?"),
                (SpecialistRole.ARCHITECT, "db_choice", "Which db?"),
            ],
            synthesize=False,
        )
        result = coordinator.run(plan)

        assert len(result.conflicts) == 1
        conflict = result.conflicts[0]
        assert conflict.deliverable == "db_choice"
        assert set(conflict.agents) == {
            SpecialistRole.RESEARCHER,
            SpecialistRole.ARCHITECT,
        }
        assert conflict.outputs[SpecialistRole.RESEARCHER] == "Use postgres"
        assert conflict.outputs[SpecialistRole.ARCHITECT] == "Use sqlite"

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_agreeing_outputs_not_a_conflict(self, MockExecutor):
        """Specialists agreeing on the same deliverable produce no conflict."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True, final_response="Use postgres", error=None
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={
                SpecialistRole.RESEARCHER: MagicMock(),
                SpecialistRole.ARCHITECT: MagicMock(),
            },
        )
        plan = _plan(
            [
                (SpecialistRole.RESEARCHER, "db_choice", "Which db?"),
                (SpecialistRole.ARCHITECT, "db_choice", "Which db?"),
            ],
            synthesize=False,
        )
        result = coordinator.run(plan)
        assert result.conflicts == []

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_different_deliverables_never_conflict(self, MockExecutor):
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True, final_response="something", error=None
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={
                SpecialistRole.RESEARCHER: MagicMock(),
                SpecialistRole.ARCHITECT: MagicMock(),
            },
        )
        plan = _plan(
            [
                (SpecialistRole.RESEARCHER, "finding_a", "A"),
                (SpecialistRole.ARCHITECT, "finding_b", "B"),
            ],
            synthesize=False,
        )
        result = coordinator.run(plan)
        assert result.conflicts == []


class TestSynthesis:
    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_chief_synthesis_runs(self, MockExecutor):
        """A chief agent synthesizes a final response when synthesize=True."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True,
            final_response="Synthesized final answer",
            error=None,
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.RESEARCHER: MagicMock()},
        )
        plan = _plan([(SpecialistRole.RESEARCHER, "finding", "Research.")])
        result = coordinator.run(plan)

        assert result.success is True
        assert result.final_response == "Synthesized final answer"

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_no_chief_with_synthesis_is_failure(self, MockExecutor):
        """Without a chief agent, synthesis cannot produce a final response."""
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True,
            final_response="finding",
            error=None,
        )
        coordinator = MultiAgentCoordinator(
            chief=None,
            agents={SpecialistRole.RESEARCHER: MagicMock()},
        )
        plan = _plan([(SpecialistRole.RESEARCHER, "finding", "Research.")])
        result = coordinator.run(plan)

        assert result.success is False
        assert "failed to synthesize" in result.error

    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_synthesis_skipped_when_plan_does_not_request(self, MockExecutor):
        """When synthesize=False, no chief call is made."""
        MockExecutor.return_value.run.side_effect = (
            lambda *a, **k: SimpleNamespace(
                success=True, final_response="finding", error=None
            )
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.RESEARCHER: MagicMock()},
        )
        plan = _plan(
            [(SpecialistRole.RESEARCHER, "finding", "Research.")], synthesize=False
        )
        result = coordinator.run(plan)

        assert result.success is True
        assert result.final_response == ""
        # Only the delegation called the executor (no chief synthesis call).
        assert MockExecutor.return_value.run.call_count == 1


class TestRunResult:
    @patch("laew.multiagent.coordinator.AgentExecutor")
    def test_result_exposes_delegations_and_context(self, MockExecutor):
        MockExecutor.return_value.run.return_value = SimpleNamespace(
            success=True, final_response="done", error=None
        )
        coordinator = MultiAgentCoordinator(
            chief=MagicMock(),
            agents={SpecialistRole.CODER: MagicMock()},
        )
        result = coordinator.run(_plan([(SpecialistRole.CODER, "code", "Write code.")]))

        assert isinstance(result, MultiAgentResult)
        assert result.delegations and isinstance(result.delegations[0], DelegationResult)
        assert len(result.conflicts) == 0

    def test_runs_are_independently_fresh(self):
        """Two runs on one coordinator do not leak delegation state."""
        with patch(
            "laew.multiagent.coordinator.AgentExecutor"
        ) as MockExecutor:
            MockExecutor.return_value.run.return_value = SimpleNamespace(
                success=True, final_response="done", error=None
            )
            coordinator = MultiAgentCoordinator(
                chief=MagicMock(),
                agents={SpecialistRole.CODER: MagicMock()},
            )
            plan = _plan(
                [(SpecialistRole.CODER, "code", "Write code.")], synthesize=False
            )
            first = coordinator.run(plan)
            second = coordinator.run(plan)

            assert len(first.delegations) == 1
            assert len(second.delegations) == 1
            assert first.delegations == second.delegations