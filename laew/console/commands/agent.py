"""Agent command handlers for the LAEW testing console.

Drives the single-agent loop (``agent run``), an interactive chat loop
(``agent chat``), and the step-trace toggle (``trace on|off``).  The run path
reuses the shared runtime composition (``build_provider`` + shared tools) so
what the console exercises is the identical wiring the CLI chat command uses.
"""

import time
from typing import Callable, Dict, Optional

from laew.console.state import SessionState
from laew.runtime import (
    build_provider,
    build_shared_tools,
    resolve_model_name,
    terminal_allowlist_from_manifest,
)


def _err(msg: str) -> int:
    print(f"[FAIL] {msg}")
    return 1


def _build_agent(state: SessionState):
    """Compose the session agent exactly like ``laew chat`` does."""
    from laew.agent.base import Agent, AgentConfig

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


def _print_trace(result, state: SessionState) -> None:
    """Print the step-by-step trace for a completed run, if enabled."""
    if not state.trace:
        return
    for step in result.steps:
        if step.thought and not (step.tool_name or step.response):
            print(f"  step {step.step_number}: thought: {step.thought[:180]}")
        if step.tool_name:
            line = (
                f"  step {step.step_number}: {step.tool_name}.{step.operation}"
                f" -> {'OK' if step.tool_result and step.tool_result.success else 'FAIL'}"
            )
            print(line)
        if step.response:
            print(f"  step {step.step_number}: response: {step.response[:180]}")


def cmd_agent_run(args: list, state: SessionState) -> int:
    """agent [run] "<prompt>" — run the agent loop and print the trace."""
    # Accept both `agent "prompt"` and the explicit `agent run "prompt"` form.
    prompt_args = args
    if args and args[0] == "run":
        prompt_args = args[1:]
    if not prompt_args:
        return _err('usage: agent run "<prompt>"')
    prompt = " ".join(prompt_args)

    try:
        agent, model_name = _build_agent(state)
    except Exception as e:
        return _err(f"could not build agent: {e}")

    from laew.agent.executor import AgentExecutor

    executor = AgentExecutor(agent)
    print(f"Running agent on '{model_name}'...")
    start = time.perf_counter()
    try:
        result = executor.run(prompt)
    except Exception as e:
        return _err(f"execution failed: {e}")
    elapsed = time.perf_counter() - start

    _print_trace(result, state)
    if result.success:
        print(f"\n[OK] completed in {elapsed:.2f}s ({result.total_steps} steps)")
        print(result.final_response)
        return 0

    print(f"\n[FAIL] {result.error or 'agent loop failed'}")
    return 1


def cmd_agent_chat(args: list, state: SessionState) -> int:
    """agent chat — interactive conversation on the same agent wiring."""
    try:
        agent, model_name = _build_agent(state)
    except Exception as e:
        return _err(f"could not build agent: {e}")

    from laew.agent.executor import AgentExecutor

    executor = AgentExecutor(agent)
    print(f"Chatting with '{model_name}'. Type 'exit' or 'quit' to end.")
    while True:
        try:
            user_input = input("you> ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        result = executor.run(user_input)
        _print_trace(result, state)
        if result.success:
            print(f"\nagent> {result.final_response}")
        else:
            print(f"\nagent> [FAIL] {result.error}")
    return 0


def cmd_trace(args: list, state: SessionState) -> int:
    """trace on|off — toggle the agent step-trace output."""
    if len(args) < 1 or args[0] not in ("on", "off"):
        return _err("usage: trace on|off")
    state.set_override("trace", args[0])
    print(f"[OK] trace {'on' if state.trace else 'off'}")
    return 0


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
def register() -> Dict[str, Callable]:
    """Return this module's command handlers keyed by command name."""
    return {
        "agent": cmd_agent_run,  # `agent "<prompt>"` and `agent run "<prompt>"`
        "chat": cmd_agent_chat,
        "trace": cmd_trace,
    }