"""Tests for the AgentExecutor tool call safety net."""

from unittest.mock import MagicMock

from laew.agent.base import Agent, AgentConfig, MessageRole
from laew.agent.executor import AgentExecutor
from laew.llm.base import LLMResponse
from laew.tools.base import Tool, ToolResult


class DummyTool(Tool):
    """A minimal tool for testing."""

    def __init__(self):
        self.description = "A dummy tool for testing"

    def validate(self, operation: str, **kwargs):
        return True

    def execute(self, operation: str, **kwargs):
        return ToolResult(success=True, data=f"Result of {operation}")

    def call(self, operation: str, **kwargs):
        if not self.validate(operation, **kwargs):
            return ToolResult(
                success=False,
                error_code="ERR_VALIDATION",
                error_message="Validation failed",
            )
        return self.execute(operation, **kwargs)


def respond(content: str) -> LLMResponse:
    """Build a valid LLMResponse for the given content."""
    return LLMResponse(
        content=content,
        model="test-model",
        prompt_tokens=10,
        completion_tokens=10,
        total_tokens=20,
        finish_reason="stop",
    )


def make_agent(max_iterations: int = 5):
    """Build an agent with a mock provider and a single dummy tool."""
    agent = Agent(
        config=AgentConfig(name="test-agent", max_iterations=max_iterations),
        provider=MagicMock(),
    )
    agent.tools = {"dummy": DummyTool()}
    return agent


def test_executor_handles_malformed_tool_call_with_retry():
    """Executor should detect malformed tool call attempts and retry with correction."""
    agent = make_agent()
    executor = AgentExecutor(agent)

    # 1) malformed attempt (JSON object missing required "operation" key),
    # 2) valid tool call, 3) final answer
    agent.provider.generate.side_effect = [
        respond('''Some preamble
```tool_call
{"tool": "dummy", "args": {"param": "value"}}
```'''),
        respond('''```tool_call
{"tool": "dummy", "operation": "test_op", "args": {"param": "value"}}
```'''),
        respond("Final answer after tool use"),
    ]

    result = executor.run("Test prompt")

    assert result.success is True
    assert result.final_response == "Final answer after tool use"
    assert result.total_steps == 3
    assert agent.provider.generate.call_count == 3


def test_executor_accepts_valid_tool_call_immediately():
    """Executor should process valid tool calls on first attempt."""
    agent = make_agent()
    executor = AgentExecutor(agent)

    agent.provider.generate.side_effect = [
        respond('''```tool_call
{"tool": "dummy", "operation": "test_op", "args": {}}
```'''),
        respond("All done"),
    ]

    result = executor.run("Test prompt")

    assert result.success is True
    assert result.final_response == "All done"
    assert result.total_steps == 2
    assert agent.provider.generate.call_count == 2


def test_executor_treats_plain_text_as_final_answer():
    """Executor should treat plain text (no tool call attempt) as final answer."""
    agent = make_agent()
    executor = AgentExecutor(agent)

    agent.provider.generate.return_value = respond(
        "This is just a regular answer with no tool call."
    )

    result = executor.run("Test prompt")

    assert result.success is True
    assert result.final_response == "This is just a regular answer with no tool call."
    assert result.total_steps == 1
    assert agent.provider.generate.call_count == 1


def test_executor_gives_up_after_max_iterations_on_continued_malformed():
    """Executor should stop after max iterations if model keeps making malformed calls."""
    agent = make_agent(max_iterations=2)
    executor = AgentExecutor(agent)

    # Continuously produces tool-call-looking output that cannot be parsed
    agent.provider.generate.return_value = respond(
        '```tool_call\n{"tool": "dummy", "operation": "test"\n```'
    )

    result = executor.run("Test prompt")

    assert result.success is False
    assert "maximum iterations" in result.error
    assert result.total_steps == 2
    assert agent.provider.generate.call_count == 3  # 2 loop + 1 forced attempt


def test_executor_feeds_correction_back_to_model():
    """The corrective guidance should be threaded into the next provider call."""
    agent = make_agent(max_iterations=3)
    executor = AgentExecutor(agent)

    agent.provider.generate.side_effect = [
        respond('```tool_call\n{"tool": "dummy", "operation": "test"\n```'),  # truncated
        respond('''```tool_call
{"tool": "dummy", "operation": "test_op", "args": {}}
```'''),
        respond("Now lets conclude"),
    ]

    executor.run("Test prompt")

    # The correction is appended right after the model's malformed attempt,
    # before the (valid) tool call that follows.  Any call after the first
    # must contain the corrective user message.
    calls = agent.provider.generate.call_args_list
    second_call_messages = calls[1].kwargs["messages"]
    assert any(
        m.role == MessageRole.USER and "could not be parsed" in m.content
        for m in second_call_messages
    )