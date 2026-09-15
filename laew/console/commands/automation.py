"""Automation command handlers for the LAEW testing console.

Drives workflow execution, multi-agent coordination, and the evaluation
harness through ``workflow``, ``multiagent``, and ``eval`` commands — all
offline-first where possible and gated by the session approval mode.
"""

import json
from pathlib import Path
from typing import Callable, Dict, List

from laew.console.state import SessionState

#: Root of the repository (relative paths resolve here).
_REPO = Path(__file__).resolve().parents[3]


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


# --------------------------------------------------------------------------- #
# Workflow commands
# --------------------------------------------------------------------------- #
def _workflow_yamls() -> List[Path]:
    """Discover workflow YAML fixtures shipped with the test suite."""
    tests_dir = _REPO / "tests" / "workflow"
    if not tests_dir.is_dir():
        return []
    return sorted(tests_dir.glob("*.yaml"))


def cmd_workflow(args: list, state: SessionState) -> int:
    """workflow discover | show <file> | run <file>."""
    sub = args[0] if args else "discover"

    if sub == "discover":
        yamls = _workflow_yamls()
        print(f"{len(yamls)} workflow fixture(s):")
        for p in yamls:
            print(f"  - {p.name}")
        return 0

    if sub == "show":
        if len(args) < 2:
            return _err("usage: workflow show <file.yaml>")
        path = _REPO / "tests" / "workflow" / args[1]
        if not path.exists():
            return _err(f"not found: {path}")
        try:
            from laew.workflow.yaml_loader import load_workflow_from_yaml
            definition = load_workflow_from_yaml(path)
        except Exception as e:
            return _err(f"could not load workflow: {e}")
        print(f"name: {definition.name}")
        print(f"description: {definition.description}")
        print(f"mode: {definition.mode.value}")
        print(f"steps: {len(definition.steps)}")
        for step in definition.steps:
            print(f"  [{step.type.value}] {step.id}: {step.name}"
                  f"  {'(approval required)' if step.approval_required else ''}")
        return 0

    if sub == "run":
        if len(args) < 2:
            return _err("usage: workflow run <file.yaml>")
        path = _REPO / "tests" / "workflow" / args[1]
        if not path.exists():
            return _err(f"not found: {path}")
        try:
            from laew.workflow.yaml_loader import load_workflow_from_yaml
            from laew.workflow.engine import WorkflowEngine
            from laew.runtime import build_shared_tools, terminal_allowlist_from_manifest
            definition = load_workflow_from_yaml(path)
        except Exception as e:
            return _err(f"could not load workflow: {e}")

        manifest = state.load_manifest()
        allowlist = terminal_allowlist_from_manifest(manifest)
        tools = build_shared_tools(allowlist)
        tool_registry = {tool.name: tool for tool in tools}

        # Pre-approve tools when approval mode is 'auto' so the engine does
        # not pause at P8 gates during automated console runs.
        if state.approval == "auto":
            for tool in tools:
                tool.approve()

        print(f"Running workflow '{definition.name}' ({definition.mode.value})...")
        engine = WorkflowEngine(definition, tool_registry=tool_registry)
        try:
            engine.run()
        except Exception as e:
            return _err(f"workflow execution failed: {e}")
        print("[OK] workflow completed")
        return 0

    return _err(f"unknown workflow subcommand: {sub} (discover|show|run)")


# --------------------------------------------------------------------------- #
# Multi-agent commands
# --------------------------------------------------------------------------- #
def _multiagent_yamls() -> List[Path]:
    """Discover multi-agent plan YAML fixtures shipped with the test suite."""
    tests_dir = _REPO / "tests" / "multiagent"
    if not tests_dir.is_dir():
        return []
    return sorted(tests_dir.glob("*.yaml"))


def cmd_multiagent(args: list, state: SessionState) -> int:
    """multiagent discover | show <file> | run <file>."""
    sub = args[0] if args else "discover"

    if sub == "discover":
        yamls = _multiagent_yamls()
        print(f"{len(yamls)} multi-agent plan fixture(s):")
        for p in yamls:
            print(f"  - {p.name}")
        return 0

    if sub == "show":
        if len(args) < 2:
            return _err("usage: multiagent show <plan.yaml>")
        path = _REPO / "tests" / "multiagent" / args[1]
        if not path.exists():
            return _err(f"not found: {path}")
        try:
            from laew.multiagent.plan import load_multiagent_plan_from_yaml
            plan = load_multiagent_plan_from_yaml(path)
        except Exception as e:
            return _err(f"could not load plan: {e}")
        print(f"name: {plan.name}")
        print(f"objective: {plan.objective}")
        print(f"synthesize: {plan.synthesize}")
        print(f"subtasks: {len(plan.subtasks)}")
        for subtask in plan.subtasks:
            print(f"  [{subtask.role.value}] {subtask.id}: {subtask.deliverable}")
        return 0

    if sub == "run":
        if len(args) < 2:
            return _err("usage: multiagent run <plan.yaml>")
        path = _REPO / "tests" / "multiagent" / args[1]
        if not path.exists():
            return _err(f"not found: {path}")

        try:
            from laew.multiagent.plan import load_multiagent_plan_from_yaml, MultiAgentPlanError
            plan = load_multiagent_plan_from_yaml(path)
        except MultiAgentPlanError as e:
            return _err(f"could not load plan: {e}")

        try:
            agent, model_name = _build_shared_agent(state)
        except Exception as e:
            return _err(f"could not build agents: {e}")

        from laew.agent.base import AgentConfig, AgentRole
        from laew.multiagent import (
            MultiAgentCoordinator,
            build_specialist_system_prompt,
        )
        from laew.runtime import build_shared_tools, terminal_allowlist_from_manifest

        manifest = state.load_manifest()
        allowlist = terminal_allowlist_from_manifest(manifest)
        shared_tools = build_shared_tools(allowlist)
        provider = agent.provider

        def build_agent(name: str, system_prompt: str):
            from laew.agent.base import Agent, AgentConfig, AgentRole
            return Agent(
                config=AgentConfig(name=name, model=model_name, role=AgentRole.CHIEF if name == "chief" else AgentRole.SPECIALIST, system_prompt=system_prompt),
                provider=provider,
                tools=shared_tools,
            )

        chief = None
        if plan.synthesize:
            chief = build_agent("chief", "You are the chief agent. Synthesize delegated results.")
        specialists = {}
        for subtask in plan.subtasks:
            if subtask.role not in specialists:
                specialists[subtask.role] = build_agent(
                    subtask.role.value,
                    build_specialist_system_prompt(subtask.role),
                )

        coordinator = MultiAgentCoordinator(chief=chief, agents=specialists)
        print(f"Running multi-agent plan '{plan.name}'...")
        result = coordinator.run(plan)

        for delegation in result.delegations:
            status = "OK" if delegation.success else f"FAILED ({delegation.error})"
            print(f"[{delegation.role.value}] {delegation.subtask_id}: {status}")

        for conflict in result.conflicts:
            print(f"[!] Conflict on '{conflict.deliverable}' "
                  f"between {', '.join(str(a) for a in conflict.agents)}")

        if not result.success:
            return _err(result.error or "multi-agent run failed")
        if result.final_response:
            print(f"\n{result.final_response}")
        print("[OK] multi-agent run completed")
        return 0

    return _err(f"unknown multiagent subcommand: {sub} (discover|show|run)")


def _build_shared_agent(state: SessionState):
    """Build an agent on the same wiring that laew chat / laew multiagent run use."""
    from laew.agent.base import Agent, AgentConfig, AgentRole
    from laew.runtime import (
        build_provider,
        build_shared_tools,
        resolve_model_name,
        terminal_allowlist_from_manifest,
    )
    manifest = state.load_manifest()
    provider = build_provider(
        manifest,
        provider_type=state.overrides.get("provider"),
        base_url=state.overrides.get("base-url"),
        timeout=int(state.overrides["timeout"]) if state.overrides.get("timeout") else None,
    )
    model_name = resolve_model_name(
        state.overrides.get("model"), state.manifest_model(), provider
    )
    allowlist = terminal_allowlist_from_manifest(manifest)
    agent = Agent(
        config=AgentConfig(name="laew-console", model=model_name),
        provider=provider,
        tools=build_shared_tools(allowlist),
    )
    return agent, model_name


# --------------------------------------------------------------------------- #
# Eval commands
# --------------------------------------------------------------------------- #
def _eval_datasets() -> List[str]:
    """List registered evaluation dataset names (built-in files)."""
    from laew.eval.tasks import create_default_registry
    registry = create_default_registry()
    return registry.list_datasets()


def cmd_eval(args: list, state: SessionState) -> int:
    """eval datasets | tasks [dataset] | task <id> | dataset <name>."""
    sub = args[0] if args else "datasets"

    if sub == "datasets":
        names = _eval_datasets()
        print(f"{len(names)} evaluation dataset(s):")
        for name in names:
            print(f"  - {name}")
        return 0

    if sub == "tasks":
        from laew.eval.tasks import create_default_registry
        registry = create_default_registry()
        dataset_name = args[1] if len(args) > 1 else None
        if dataset_name:
            tasks = registry.get_dataset(dataset_name)
            if tasks is None:
                return _err(f"dataset '{dataset_name}' not found")
            print(f"{len(tasks)} task(s) in '{dataset_name}':")
            for t in tasks:
                print(f"  - {t.task_id}: {t.description}")
            return 0
        # List all tasks across all datasets.
        all_ids = registry.list_tasks()
        print(f"{len(all_ids)} total task(s):")
        for tid in all_ids:
            task = registry.get(tid)
            print(f"  - {tid}: {task.description if task else '(missing)'}")
        return 0

    if sub == "task":
        if len(args) < 2:
            return _err("usage: eval task <task_id>")
        from laew.eval.tasks import create_default_registry
        registry = create_default_registry()
        task_id = args[1]
        task = registry.get(task_id)
        if task is None:
            return _err(f"task '{task_id}' not found")
        print(f"task_id: {task.task_id}")
        print(f"description: {task.description}")
        print(f"input_prompt: {task.input_prompt}")
        if task.expected_tool_calls:
            print("expected_tool_calls:")
            for tc in task.expected_tool_calls:
                print(f"  - {json.dumps(tc)}")
        if task.expected_outcome_contains:
            print(f"expected_outcome_contains: {task.expected_outcome_contains}")
        return 0

    if sub == "dataset":
        if len(args) < 2:
            return _err("usage: eval dataset <name>")
        dataset_name = args[1]
        try:
            agent, model_name = _build_shared_agent(state)
        except Exception as e:
            return _err(f"could not build agent: {e}")
        from laew.eval.runner import EvaluationRunner
        runner = EvaluationRunner(agent)
        print(f"Running evaluation dataset '{dataset_name}' on '{model_name}'...")
        try:
            report = runner.run_dataset(dataset_name)
        except Exception as e:
            return _err(f"evaluation failed: {e}")
        print(report.summary())
        return 0

    return _err(f"unknown eval subcommand: {sub} (datasets|tasks|task|dataset)")


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {
        "workflow": cmd_workflow,
        "multiagent": cmd_multiagent,
        "eval": cmd_eval,
    }