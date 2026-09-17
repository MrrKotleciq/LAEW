"""Benchmark: full ``AgentExecutor.run()`` over a stub provider.

Offline baseline for the agent hot path (system-prompt cache, message
estimation, budget trimming, tool dispatch). The provider is scripted to drive
a fixed multi-step tool-call sequence plus a final answer, so the measured time
is LAEW runtime overhead, not model latency.

pytest-benchmark's ``setup`` is invoked once per round and the callable is
timed *outside* that setup window, so the module-global pattern below gives each
measured round a fresh executor (clean history) without billing its
construction to the number. Accumulating history across rounds would otherwise
make per-call cost grow with history — and the measurement would refund the very
thing it is supposed to record.

Tolerances are informational only — these tests record numbers for
``docs/performance/BASELINE.md``, they do not gate on wall clock.
"""

import json
from typing import List, Optional

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.base import LLMResponse
from laew.tools.base import Tool, ToolResult

STEPS = 4  # tool-call steps before the final answer


class _MockTool(Tool):
    """Minimal tool that answers any operation instantly."""

    description = "bench stub tool"

    def __init__(self):
        super().__init__()
        self._calls = 0

    def validate(self, operation: str, **kwargs) -> tuple:
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        self._calls += 1
        return ToolResult(success=True, data={"steps": self._calls})


class _ScriptedProvider:
    """Duck-typed provider that replays a scripted tool-call sequence.

    A fresh instance is built per benchmark round, so ``call_count`` always
    starts at zero and the scripted sequence is deterministic every round.
    """

    def __init__(self, steps: int):
        self.steps = steps
        self.call_count = 0

    def generate(
        self,
        messages: list,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.call_count += 1
        if self.call_count <= self.steps:
            payload = json.dumps({
                "tool": "mock_tool",
                "operation": "test_op",
                "args": {},
            })
            content = f"```tool_call\n{payload}\n```"
        else:
            content = "Benchmark destination reached."
        return LLMResponse(
            content=content,
            model="stub",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )

    def list_models(self) -> List[str]:
        return ["stub"]

    def is_available(self) -> bool:
        return True


def _make_executor() -> AgentExecutor:
    """Build a fresh executor wired to a fresh scripted stub provider."""
    agent = Agent(config=AgentConfig(name="bench", model="stub"), provider=_ScriptedProvider(STEPS))
    agent.register_tool(_MockTool())
    return AgentExecutor(agent)


# pytest-benchmark `setup` must return None (a truthy return is unpacked as
# benchmark arguments), so the fresh executor is handed to each round through a
# module-level slot instead.
_BENCH: dict = {}

def _setup_executor():
    """pytest-benchmark setup: replace the per-round executor (untimed)."""
    _BENCH["executor"] = _make_executor()


def _run_full():
    """Measured target: a single 4-tool-step + final-answer executor run."""
    return _BENCH["executor"].run("use a tool")


def _run_repeated():
    """Measured target: ten single-step runs on the one fresh executor."""
    for _ in range(10):
        _BENCH["executor"].run("task")


def test_profile_full_agent_run(benchmark):
    """Wall clock of a 4-tool-step + final answer executor run (fresh state)."""
    result = benchmark.pedantic(_run_full, setup=_setup_executor, rounds=20)

    # Record sanity: all scripted steps executed and tokens accumulated.
    assert result.total_steps >= 1
    assert result.total_tokens > 0


def test_profile_system_prompt_cache_hit(benchmark):
    """Repeated single-step runs on one executor benefit from the cached prompt."""
    benchmark.pedantic(_run_repeated, setup=_setup_executor, rounds=10)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])