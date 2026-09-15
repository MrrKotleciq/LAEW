"""Tests for the ``workflow``/``multiagent``/``eval`` console commands.

Discovery and inspection run against the real fixtures under tests/workflow and
tests/multiagent (pure parsing, no execution).  Execution paths mock the engines
so the tests never touch the filesystem, a live model, or a network endpoint.
"""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from laew.console.commands.automation import cmd_workflow, cmd_multiagent, cmd_eval
from laew.console.state import SessionState


@pytest.fixture
def state():
    return SessionState(manifest_path="manifests/SYSTEM_MANIFEST.yaml")


# --------------------------------------------------------------------------- #
# workflow
# --------------------------------------------------------------------------- #
def test_workflow_discover_lists_fixtures(state, capsys):
    """workflow discover lists the bundled workflow YAML fixtures."""
    assert cmd_workflow(["discover"], state) == 0
    out = capsys.readouterr().out
    assert "test_simple_workflow.yaml" in out
    assert "test_approval_workflow.yaml" in out
    assert "fixture(s)" in out


def test_workflow_show_loads_definition(state, capsys):
    """workflow show parses a YAML fixture and prints its steps."""
    assert cmd_workflow(["show", "test_simple_workflow.yaml"], state) == 0
    out = capsys.readouterr().out
    assert "name: test_simple_workflow" in out
    assert "automatic" in out
    assert "step_read" in out


def test_workflow_show_missing_file(state, capsys):
    """workflow show on a nonexistent file returns a readable error."""
    assert cmd_workflow(["show", "missing.yaml"], state) == 1
    assert "not found" in capsys.readouterr().out


def test_workflow_dispatch_unknown_subcommand(state, capsys):
    """workflow with an unknown subcommand is rejected."""
    assert cmd_workflow(["explain"], state) == 1
    assert "unknown workflow subcommand" in capsys.readouterr().out


def test_workflow_need_filename(state, capsys):
    """show/run without a file produce a usage error."""
    assert cmd_workflow(["show"], state) == 1
    assert "usage:" in capsys.readouterr().out
    assert cmd_workflow(["run"], state) == 1


def test_workflow_run_automatic(state, capsys):
    """workflow run executes an automatic-mode workflow via the engine."""
    engine = MagicMock()
    with patch("laew.workflow.engine.WorkflowEngine", return_value=engine):
        assert cmd_workflow(["run", "test_simple_workflow.yaml"], state) == 0
    engine.run.assert_called_once()
    assert "[OK] workflow completed" in capsys.readouterr().out


def test_workflow_run_engine_failure(state, capsys):
    """An engine exception nets into a readable failure and exit code 1."""
    engine = MagicMock()
    engine.run.side_effect = RuntimeError("tool missing")
    with patch("laew.workflow.engine.WorkflowEngine", return_value=engine):
        assert cmd_workflow(["run", "test_simple_workflow.yaml"], state) == 1
    assert "workflow execution failed" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# multiagent
# --------------------------------------------------------------------------- #
def test_multiagent_discover_lists_plan_fixtures(state, capsys):
    """multiagent discover lists the bundled plan YAML fixtures."""
    assert cmd_multiagent(["discover"], state) == 0
    assert "test_plan.yaml" in capsys.readouterr().out


def test_multiagent_show_loads_plan(state, capsys):
    """multiagent show parses a plan fixture and prints its subtasks."""
    assert cmd_multiagent(["show", "test_plan.yaml"], state) == 0
    out = capsys.readouterr().out
    assert "Test Documentation Review Plan" in out
    assert "research-1" in out
    assert "review-1" in out


def test_multiagent_show_missing_file(state, capsys):
    """multiagent show on a nonexistent file returns a readable error."""
    assert cmd_multiagent(["show", "nope.yaml"], state) == 1
    assert "not found" in capsys.readouterr().out


def test_multiagent_run_success(state, capsys):
    """multiagent run delegates subtasks and reports delegations."""
    agent = MagicMock(provider=MagicMock())
    delegation = SimpleNamespace(
        role=SimpleNamespace(value="researcher"), subtask_id="r1",
        success=True, error=None,
    )
    result = SimpleNamespace(
        delegations=[delegation], conflicts=[], success=True,
        final_response="synthesized output", error=None,
    )
    coordinator = MagicMock()
    coordinator.run.return_value = result
    with patch("laew.console.commands.automation._build_shared_agent", return_value=(agent, "m")), \
         patch("laew.multiagent.MultiAgentCoordinator", return_value=coordinator), \
         patch("laew.multiagent.build_specialist_system_prompt", return_value="sys"):
        assert cmd_multiagent(["run", "test_plan.yaml"], state) == 0
    out = capsys.readouterr().out
    assert "researcher" in out and "r1" in out
    assert "synthesized output" in out


def test_multiagent_run_with_conflicts(state, capsys):
    """Conflicts between handlers are surfaced in the output."""
    agent = MagicMock(provider=MagicMock())
    delegation = SimpleNamespace(
        role=SimpleNamespace(value="reviewer"), subtask_id="v1",
        success=True, error=None,
    )
    result = SimpleNamespace(
        delegations=[delegation],
        conflicts=[SimpleNamespace(deliverable="doc_issues", agents=("researcher", "reviewer"))],
        success=True, final_response=None, error=None,
    )
    coordinator = MagicMock()
    coordinator.run.return_value = result
    with patch("laew.console.commands.automation._build_shared_agent", return_value=(agent, "m")), \
         patch("laew.multiagent.MultiAgentCoordinator", return_value=coordinator), \
         patch("laew.multiagent.build_specialist_system_prompt", return_value="sys"):
        assert cmd_multiagent(["run", "test_plan.yaml"], state) == 0
    out = capsys.readouterr().out
    assert "Conflict on 'doc_issues'" in out


def test_multiagent_run_overall_failure(state, capsys):
    """An unsuccessful coordinator result fails the command with its error."""
    agent = MagicMock(provider=MagicMock())
    result = SimpleNamespace(
        delegations=[], conflicts=[], success=False, final_response=None,
        error="chief unavailable",
    )
    coordinator = MagicMock()
    coordinator.run.return_value = result
    with patch("laew.console.commands.automation._build_shared_agent", return_value=(agent, "m")), \
         patch("laew.multiagent.MultiAgentCoordinator", return_value=coordinator), \
         patch("laew.multiagent.build_specialist_system_prompt", return_value="sys"):
        assert cmd_multiagent(["run", "test_plan.yaml"], state) == 1
    assert "chief unavailable" in capsys.readouterr().out


def test_multiagent_run_plan_load_error(state, capsys):
    """A bad plan file nets into a readable error."""
    assert cmd_multiagent(["run", "bad_plan.yaml"], state) == 1
    assert "not found" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# eval
# --------------------------------------------------------------------------- #
def test_eval_datasets_lists_real_datasets(state, capsys):
    """eval datasets lists the bundled benchmark datasets."""
    assert cmd_eval(["datasets"], state) == 0
    out = capsys.readouterr().out
    assert "laew_specific" in out
    assert "general_reasoning" in out


def test_eval_tasks_all(state, capsys):
    """eval tasks lists every registered task across datasets."""
    assert cmd_eval(["tasks"], state) == 0
    out = capsys.readouterr().out
    assert "total task(s)" in out
    assert "laew-manifest-check" in out


def test_eval_tasks_filtered_by_dataset(state, capsys):
    """eval tasks <dataset> lists only that dataset's tasks."""
    assert cmd_eval(["tasks", "general_reasoning"], state) == 0
    out = capsys.readouterr().out
    assert "general-file-exists" in out
    assert "- laew-manifest-check" not in out


def test_eval_tasks_unknown_dataset(state, capsys):
    """eval tasks with an unknown dataset is rejected."""
    assert cmd_eval(["tasks", "nope"], state) == 1
    assert "dataset 'nope' not found" in capsys.readouterr().out


def test_eval_task_details(state, capsys):
    """eval task <id> prints the task's prompt and expectations."""
    assert cmd_eval(["task", "laew-filesystem-list"], state) == 0
    out = capsys.readouterr().out
    assert "task_id: laew-filesystem-list" in out
    assert "input_prompt:" in out


def test_eval_task_unknown(state, capsys):
    """eval task with an unknown id is rejected."""
    assert cmd_eval(["task", "nope"], state) == 1
    assert "task 'nope' not found" in capsys.readouterr().out


def test_eval_task_missing_id(state, capsys):
    """eval task without an id is rejected with a usage error."""
    assert cmd_eval(["task"], state) == 1
    assert "usage: eval task <task_id>" in capsys.readouterr().out


def test_eval_dataset_run(state, capsys):
    """eval dataset runs the runner and prints the report summary."""
    report = MagicMock()
    report.summary.return_value = "Evaluation Report: laew_specific"
    runner = MagicMock()
    runner.run_dataset.return_value = report
    with patch("laew.console.commands.automation._build_shared_agent", return_value=(MagicMock(), "m")), \
         patch("laew.eval.runner.EvaluationRunner", return_value=runner):
        assert cmd_eval(["dataset", "laew_specific"], state) == 0
    runner.run_dataset.assert_called_once_with("laew_specific")
    assert "Evaluation Report: laew_specific" in capsys.readouterr().out


def test_eval_dataset_runner_failure(state, capsys):
    """A runner exception nets into a readable failure."""
    with patch("laew.console.commands.automation._build_shared_agent", return_value=(MagicMock(), "m")), \
         patch(
             "laew.eval.runner.EvaluationRunner.run_dataset",
             side_effect=RuntimeError("agent crashed"),
         ):
        assert cmd_eval(["dataset", "laew_specific"], state) == 1
    assert "evaluation failed: agent crashed" in capsys.readouterr().out


def test_eval_unknown_subcommand(state, capsys):
    """eval with an unknown subcommand is rejected."""
    assert cmd_eval(["suite"], state) == 1
    assert "unknown eval subcommand" in capsys.readouterr().out