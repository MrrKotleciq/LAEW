"""Agent command handlers for the LAEW testing console.

Drives the single-agent loop (``agent run``), an interactive chat loop
(``agent chat``), and the step-trace toggle (``trace on|off``).  The run path
reuses the shared runtime composition (``build_provider_for_role`` + shared tools)
so what the console exercises is the identical wiring the CLI chat command uses.
"""

import time
from typing import Callable, Dict, Optional

from laew.console.state import SessionState
from laew.runtime import (
    build_provider_for_role,
    build_shared_tools,
    context_budget_from_manifest,
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
    provider = build_provider_for_role(
        manifest,
        "primary",
        base_url=state.overrides.get("base-url"),
        timeout=int(state.overrides["timeout"]) if state.overrides.get("timeout") else None,
    )
    model_name = resolve_model_name(
        state.overrides.get("model"), state.manifest_model(), provider
    )
    allowlist = terminal_allowlist_from_manifest(manifest)
    agent = Agent(
        config=AgentConfig(
            name="laew-console",
            model=model_name,
            context_budget=context_budget_from_manifest(manifest),
        ),
        provider=provider,
        tools=build_shared_tools(allowlist),
    )
    # Resume any saved conversation memory (Milestone 13). The stored turns are
    # memory/history — never treated as current project state (ADR-012), which
    # the executor re-derives from the live filesystem on each tool call.
    agent.history = state.conversation_to_messages()
    return agent, model_name


def _record_exchange(state: SessionState, user_input: str, result) -> None:
    """
    Persist one user/assistant exchange into the session conversation memory.

    Only the successful final answer is recorded as the assistant turn; tool
    observations and corrective prompts are transient run detail and are not
    recalled as conversation memory.
    """
    state.conversation.append({"role": "user", "content": user_input})
    if result.success and result.final_response:
        state.conversation.append(
            {"role": "assistant", "content": result.final_response}
        )


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
    """
    agent run "<prompt>" — run the agent loop and print the trace.

    Both forms work: ``agent "prompt"`` and ``agent run "prompt"``. Uses the
    same composition as ``laew chat`` (shared provider registry + the four
    security-gated tools). Requires a live model (Ollama by default).

    Examples:
      agent "list the files in docs/"
      agent run "summarize the manifest"   then 'trace on' to see each step

    See also: 'agent chat', 'trace on|off', 'set approval auto|ask|deny'.
    """
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
        print(
            f"\n[OK] completed in {elapsed:.2f}s ({result.total_steps} steps)"
            f" | {result.prompt_tokens}p / {result.completion_tokens}c tokens"
        )
        print(result.final_response)
        _record_exchange(state, prompt, result)
        return 0

    print(f"\n[FAIL] {result.error or 'agent loop failed'}")
    return 1


def cmd_agent_chat(args: list, state: SessionState) -> int:
    """
    agent chat — interactive conversation on the same agent wiring.

    Runs a multi-turn loop on the same AgentExecutor the run form uses (shared
    context history). Type 'exit' or 'quit' to end; 'trace on' during the chat
    shows each thought/action/observation step.

    Examples:
      agent chat
      trace on
    """
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

        result = executor.run(user_input, stream=True)
        _print_trace(result, state)
        if result.success:
            tokens = (
                f" ({result.prompt_tokens}p / {result.completion_tokens}c)"
                if result.total_tokens
                else ""
            )
            print(f"\nagent> {result.final_response}{tokens}")
            _record_exchange(state, user_input, result)
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