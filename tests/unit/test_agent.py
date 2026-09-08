"""Tests for agent orchestration and execution loop."""

import json
from unittest.mock import MagicMock, patch

import pytest

from laew.agent import Agent, AgentConfig, AgentError, AgentExecutor, ExecutionResult
from laew.agent.base import AgentRole, RetryConfig
from laew.llm.base import LLMError, LLMMessage, LLMResponse, MessageRole
from laew.prompts.context_budget import ContextBudget
from laew.prompts.loader import LayeredPrompt, PromptSection
from laew.tools.base import Tool, ToolResult


class ExecutionStep:
    """A single step in the agent's execution loop."""

    def __init__(
        self,
        step_number: int,
        thought: str | None = None,
        tool_name: str | None = None,
        operation: str | None = None,
        args: dict | None = None,
        tool_result: ToolResult | None = None,
        response: str | None = None,
    ):
        self.step_number = step_number
        self.thought = thought
        self.tool_name = tool_name
        self.operation = operation
        self.args = args or {}
        self.tool_result = tool_result
        self.response = response


class MockTool(Tool):
    """Mock tool for testing."""

    name = "mock_tool"
    description = "A mock tool for testing"

    def __init__(self, should_succeed: bool = True, result_data: dict = None):
        super().__init__()
        self.should_succeed = should_succeed
        self.result_data = result_data or {"key": "value"}
        self.call_count = 0
        self.last_operation = None
        self.last_args = None

    def validate(self, operation: str, **kwargs) -> tuple[bool, str | None]:
        """Validate operation."""
        return True, None

    def execute(self, operation: str, **kwargs) -> ToolResult:
        """Execute operation."""
        self.call_count += 1
        self.last_operation = operation
        self.last_args = kwargs

        if not self.should_succeed:
            return ToolResult(success=False, error_code="ERR_MOCK_FAILURE", error_message="Mock tool failure")

        return ToolResult(success=True, data=self.result_data)


class MockProvider:
    """Mock LLM provider for testing."""

    def __init__(self, responses: list = None):
        self.responses = responses or []
        self.call_count = 0
        self.last_messages = None

    def generate(
        self, messages: list, model: str, temperature: float = 0.7, max_tokens: int = None
    ) -> LLMResponse:
        self.last_messages = messages
        self.call_count += 1

        if self.responses and self.call_count <= len(self.responses):
            content = self.responses[self.call_count - 1]
        else:
            content = "Default response"

        return LLMResponse(
            content=content,
            model=model,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            finish_reason="stop",
        )

    def list_models(self) -> list:
        return ["mock-model"]

    def is_available(self) -> bool:
        return True


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AgentConfig()
        assert config.name == "chief"
        assert config.role == AgentRole.CHIEF
        assert config.model == "llama3.1"
        assert config.temperature == 0.7
        assert config.max_iterations == 10
        assert isinstance(config.context_budget, ContextBudget)

    def test_custom_config(self):
        """Test custom configuration."""
        budget = ContextBudget(system=3000, conversation=5000, rag=10000, tools=5000, total=23000)
        config = AgentConfig(
            name="test_agent",
            role=AgentRole.SPECIALIST,
            model="mistral",
            temperature=0.5,
            max_iterations=5,
            context_budget=budget,
        )
        assert config.name == "test_agent"
        assert config.role == AgentRole.SPECIALIST
        assert config.model == "mistral"
        assert config.temperature == 0.5
        assert config.max_iterations == 5
        assert config.context_budget.system == 3000


class TestAgentBase:
    """Tests for Agent base class."""

    def test_agent_creation(self):
        """
        Test creating an agent.
        Importers/Callers: laew.agent.Agent class, tests.unit.test_agent.TestAgentBase.
        Affected API: Agent.__init__ signature updated to accept providers List[LLMProvider].
        User Instruction: Proceed with next milestone (Agent Robustness & Error Recovery).
        """
        provider = MockProvider()
        config = AgentConfig(name="test")
        agent = Agent(config=config, providers=[provider])

        assert agent.config.name == "test"
        assert agent.provider == provider
        assert agent.tools == {}
        assert agent.history == []

    def test_register_tool(self):
        """Test registering a tool."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])

        tool = MockTool()
        agent.register_tool(tool)

        assert "mock_tool" in agent.tools
        assert agent.tools["mock_tool"] == tool

    def test_register_multiple_tools(self):
        """Test registering multiple tools."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])

        tool1 = MockTool()
        tool1.name = "tool_one"
        tool2 = MockTool()
        tool2.name = "tool_two"

        agent.register_tool(tool1)
        agent.register_tool(tool2)

        assert len(agent.tools) == 2
        assert "tool_one" in agent.tools
        assert "tool_two" in agent.tools

    def test_get_system_prompt_text_default(self):
        """Test default system prompt."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(name="assistant"), providers=[provider])

        prompt = agent.get_system_prompt_text()
        assert "assistant" in prompt
        assert "helpful engineering assistant" in prompt

    def test_get_system_prompt_text_string(self):
        """Test custom string system prompt."""
        provider = MockProvider()
        config = AgentConfig(system_prompt="Custom system prompt")
        agent = Agent(config=config, providers=[provider])

        prompt = agent.get_system_prompt_text()
        assert prompt == "Custom system prompt"

    def test_get_system_prompt_text_layered(self):
        """Test layered prompt as system prompt."""
        provider = MockProvider()
        layered = LayeredPrompt(name="test")
        layered.add_section(PromptSection(name="identity", content="You are a test agent.", priority=0))
        layered.add_section(PromptSection(name="rules", content="Follow the rules.", priority=1))

        config = AgentConfig(system_prompt=layered)
        agent = Agent(config=config, providers=[provider])

        prompt = agent.get_system_prompt_text()
        assert "You are a test agent." in prompt
        assert "Follow the rules." in prompt

    def test_add_message(self):
        """Test adding messages to history."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])

        agent.add_message(MessageRole.USER, "Hello")
        agent.add_message(MessageRole.ASSISTANT, "Hi there")

        assert len(agent.history) == 2
        assert agent.history[0].role == MessageRole.USER
        assert agent.history[0].content == "Hello"
        assert agent.history[1].role == MessageRole.ASSISTANT

    def test_reset_history(self):
        """Test resetting conversation history."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])

        agent.add_message(MessageRole.USER, "Hello")
        assert len(agent.history) == 1

        agent.reset_history()
        assert len(agent.history) == 0


class TestExecutionStep:
    """Tests for ExecutionStep."""

    def test_step_creation(self):
        """Test creating an execution step."""
        step = ExecutionStep(step_number=1)
        assert step.step_number == 1
        assert step.thought is None
        assert step.tool_name is None
        assert step.operation is None
        assert step.args == {}

    def test_step_with_data(self):
        """Test step with all fields."""
        step = ExecutionStep(
            step_number=2,
            thought="Thinking about the problem",
            tool_name="filesystem",
            operation="view_file",
            args={"file_path": "test.py"},
        )
        assert step.step_number == 2
        assert step.thought == "Thinking about the problem"
        assert step.tool_name == "filesystem"
        assert step.operation == "view_file"
        assert step.args["file_path"] == "test.py"


class TestExecutionResult:
    """Tests for ExecutionResult."""

    def test_result_creation(self):
        """Test creating an execution result."""
        result = ExecutionResult(agent_name="test")
        assert result.agent_name == "test"
        assert result.steps == []
        assert result.final_response == ""
        assert result.total_steps == 0
        assert result.success is True
        assert result.error is None

    def test_result_with_failure(self):
        """Test result with failure."""
        result = ExecutionResult(
            agent_name="test",
            success=False,
            error="Something went wrong",
        )
        assert result.success is False
        assert result.error == "Something went wrong"


class TestAgentExecutor:
    """Tests for AgentExecutor."""

    def test_parse_tool_call_valid(self):
        """Test parsing valid tool call."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        text = '''Here is my plan:
```tool_call
{"tool": "filesystem", "operation": "view_file", "args": {"file_path": "test.py"}}
```
Let me check the file.'''

        result = executor._parse_tool_call(text)
        assert result is not None
        assert result["tool"] == "filesystem"
        assert result["operation"] == "view_file"
        assert result["args"]["file_path"] == "test.py"

    def test_parse_tool_call_none(self):
        """Test parsing text without tool call."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        text = "This is just a regular response without any tool calls."
        result = executor._parse_tool_call(text)
        assert result is None

    def test_parse_tool_call_json_block(self):
        """Test parsing tool call in generic json block."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        text = '''```json
{"tool": "git", "operation": "git_status", "args": {}}
```'''

        result = executor._parse_tool_call(text)
        assert result is not None
        assert result["tool"] == "git"

    def test_format_tools_description_empty(self):
        """Test tool description when no tools available."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        desc = executor._format_tools_description()
        assert desc == "No tools available."

    def test_format_tools_description_with_tools(self):
        """Test tool description with registered tools."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), provider=provider)
        agent.register_tool(MockTool())

        executor = AgentExecutor(agent)
        desc = executor._format_tools_description()

        assert "mock_tool" in desc
        assert "A mock tool for testing" in desc

    def test_run_simple_response(self):
        """Test execution with simple response (no tool call)."""
        provider = MockProvider(responses=["This is the final answer."])
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        result = executor.run("What is 2+2?")

        assert result.success is True
        assert result.final_response == "This is the final answer."
        assert result.total_steps == 1
        assert len(result.steps) == 1
        assert result.steps[0].response == "This is the final answer."

    def test_run_with_tool_call(self):
        """Test execution with tool call."""
        tool_call_json = json.dumps({
            "tool": "mock_tool",
            "operation": "test_op",
            "args": {"key": "value"}
        })
        tool_response = f"```tool_call\n{tool_call_json}\n```"

        provider = MockProvider(responses=[
            tool_response,
            "The tool result shows the answer.",
        ])

        tool = MockTool()
        agent = Agent(config=AgentConfig(), provider=provider)
        agent.register_tool(tool)

        executor = AgentExecutor(agent)
        result = executor.run("Use the tool")

        assert result.success is True
        assert result.total_steps == 2
        assert tool.call_count == 1
        assert tool.last_operation == "test_op"

    def test_run_tool_not_found(self):
        """Test execution with nonexistent tool."""
        tool_call_json = json.dumps({
            "tool": "nonexistent",
            "operation": "test",
            "args": {}
        })
        tool_response = f"```tool_call\n{tool_call_json}\n```"

        provider = MockProvider(responses=[
            tool_response,
            "Okay, I understand.",
        ])

        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)
        result = executor.run("Use nonexistent tool")

        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0].tool_result is not None
        assert result.steps[0].tool_result.success is False
        assert "not found" in result.steps[0].tool_result.error_message.lower()

    def test_run_max_iterations(self):
        """Test execution hitting max iterations."""
        tool_call_json = json.dumps({
            "tool": "mock_tool",
            "operation": "test",
            "args": {}
        })
        tool_response = f"```tool_call\n{tool_call_json}\n```"

        # Always return a tool call, never finish
        provider = MockProvider(responses=[tool_response] * 20)

        tool = MockTool()
        agent = Agent(config=AgentConfig(max_iterations=3), provider=provider)
        agent.register_tool(tool)

        executor = AgentExecutor(agent)
        result = executor.run("Keep calling tools")

        assert result.success is False
        assert "maximum iterations" in result.error.lower()
        assert result.total_steps == 3

    def test_run_llm_error(self):
        """Test execution with LLM error."""
        provider = MagicMock()
        provider.generate.side_effect = Exception("LLM connection failed")

        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        result = executor.run("Hello")

        assert result.success is False
        assert "LLM generation failed" in result.error
        assert result.total_steps == 0

    def test_run_preserves_history(self):
        """Test that execution preserves conversation history."""
        provider = MockProvider(responses=["Response 1", "Response 2"])
        agent = Agent(config=AgentConfig(), provider=provider)
        executor = AgentExecutor(agent)

        executor.run("Question 1")
        assert len(agent.history) == 2  # USER + ASSISTANT
        assert agent.history[0].content == "Question 1"
        assert agent.history[1].content == "Response 1"

        executor.run("Question 2")
        assert len(agent.history) == 4  # + USER + ASSISTANT


class TestAgentIntegration:
    """Integration tests for agent orchestration."""

    def test_full_execution_flow(self):
        """Test complete execution flow with tools."""
        # Simulate: user asks -> agent calls tool -> agent sees result -> final answer
        tool_call = json.dumps({
            "tool": "mock_tool",
            "operation": "get_data",
            "args": {"query": "test"}
        })

        provider = MockProvider(responses=[
            f"```tool_call\n{tool_call}\n```",
            "Based on the tool result, here is my answer: 42",
        ])

        tool = MockTool(result_data={"result": 42})
        agent = Agent(config=AgentConfig(), provider=provider)
        agent.register_tool(tool)

        executor = AgentExecutor(agent)
        result = executor.run("What is the answer?")

        assert result.success is True
        assert result.final_response == "Based on the tool result, here is my answer: 42"
        assert tool.call_count == 1
        assert tool.last_args["query"] == "test"


class FlakyProvider:
    """Provider that fails a configurable number of times before succeeding."""

    def __init__(self, failures_before_success: int = 1):
        self.failures_before_success = failures_before_success
        self.call_count = 0

    def generate(self, messages, model, temperature=0.7, max_tokens=None) -> LLMResponse:
        self.call_count += 1
        if self.call_count <= self.failures_before_success:
            raise LLMError("Transient connection failure", code="CONNECTION_ERROR")
        return LLMResponse(content="Recovered response", model=model)

    def list_models(self) -> list:
        return ["flaky-model"]

    def is_available(self) -> bool:
        return True


class UnavailableProvider:
    """Provider that reports itself unavailable."""

    def generate(self, messages, model, temperature=0.7, max_tokens=None) -> LLMResponse:
        raise LLMError("Should not be called", code="UNEXPECTED_CALL")

    def list_models(self) -> list:
        return []

    def is_available(self) -> bool:
        return False


class TestAgentConfigRetry:
    """Tests for new AgentConfig resilience fields."""

    def test_retry_config_defaults(self):
        """Test default retry configuration."""
        from laew.agent.base import RetryConfig

        retry = RetryConfig()
        assert retry.max_attempts == 3
        assert retry.backoff_base_ms == 1000
        assert retry.max_backoff_ms == 5000

    def test_custom_retry_config(self):
        """Test custom retry configuration."""
        from laew.agent.base import RetryConfig

        config = AgentConfig(
            retry=RetryConfig(max_attempts=5, backoff_base_ms=200, max_backoff_ms=1000)
        )
        assert config.retry.max_attempts == 5
        assert config.retry.backoff_base_ms == 200

    def test_history_path_default_none(self):
        """Test history_path defaults to None (no persistence)."""
        config = AgentConfig()
        assert config.history_path is None


class TestAgentResilience:
    """Tests for agent provider fallback and history persistence."""

    def test_no_providers_raises(self):
        """Test agent with no providers raises ValueError."""
        with pytest.raises(ValueError):
            Agent(config=AgentConfig())

    def test_single_provider_backward_compat(self):
        """Test single provider argument still works (backward compat)."""
        provider = MockProvider(responses=["answer"])
        agent = Agent(config=AgentConfig(), provider=provider)
        assert len(agent.providers) == 1
        assert agent.provider == provider

    def test_provider_fallback_on_failure(self):
        """Test executor falls back to next provider when primary fails."""
        failing = MagicMock()
        failing.generate.side_effect = LLMError("down", code="CONNECTION_ERROR")
        failing.is_available.return_value = True

        backup = MockProvider(responses=["Fallback answer"])
        agent = Agent(
            config=AgentConfig(retry=RetryConfig(max_attempts=1, backoff_base_ms=1)),
            providers=[failing, backup],
        )
        executor = AgentExecutor(agent)
        result = executor.run("Hello")

        assert result.success is True
        assert result.final_response == "Fallback answer"
        assert agent.provider == backup

    def test_primary_unavailable_uses_second(self):
        """Test agent selects the first available provider on init."""
        unavailable = UnavailableProvider()
        available = MockProvider()
        agent = Agent(
            config=AgentConfig(),
            providers=[unavailable, available],
        )
        assert agent.provider == available

    def test_retry_transient_then_success(self):
        """Test executor retries transient failures then succeeds."""
        flaky = FlakyProvider(failures_before_success=2)
        agent = Agent(
            config=AgentConfig(retry=RetryConfig(max_attempts=5, backoff_base_ms=1)),
            providers=[flaky],
        )
        executor = AgentExecutor(agent)
        result = executor.run("Retry me")

        assert result.success is True
        assert result.final_response == "Recovered response"
        assert flaky.call_count == 3  # 2 failures + 1 success


class TestHistoryPersistence:
    """Tests for conversation history persistence."""

    def test_save_and_load_history(self, tmp_path):
        """Test history saves to disk and reloads into a new agent."""
        history_file = str(tmp_path / "history.json")

        provider = MockProvider(responses=["answer"])
        config = AgentConfig(name="persist", history_path=history_file)
        agent = Agent(config=config, providers=[provider])
        agent.add_message(MessageRole.USER, "Hello")
        agent.add_message(MessageRole.ASSISTANT, "Hi there")
        agent.save_history()

        # New agent loads the saved history
        config2 = AgentConfig(name="persist", history_path=history_file)
        agent2 = Agent(config=config2, providers=[provider])

        assert len(agent2.history) == 2
        assert agent2.history[0].role == MessageRole.USER
        assert agent2.history[0].content == "Hello"
        assert agent2.history[1].role == MessageRole.ASSISTANT
        assert agent2.history[1].content == "Hi there"

    def test_load_missing_history(self, tmp_path):
        """Test loading a non-existent history file yields empty history."""
        history_file = str(tmp_path / "missing.json")
        provider = MockProvider()
        agent = Agent(
            config=AgentConfig(history_path=history_file),
            providers=[provider],
        )
        assert agent.history == []

    def test_save_without_path_is_noop(self):
        """Test save_history with no configured path does nothing."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])
        agent.add_message(MessageRole.USER, "Hello")
        agent.save_history()  # Should not raise
        assert len(agent.history) == 1


class TestStructuredOutputValidation:
    """Tests for structured output parsing robustness."""

    def test_parse_malformed_json_returns_none(self):
        """Test malformed JSON in tool block is ignored."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])
        executor = AgentExecutor(agent)

        text = "```tool_call\n{this is not valid json\n```"
        result = executor._parse_tool_call(text)
        assert result is None

    def test_parse_missing_operation_gets_default(self):
        """Test tool call missing operation gets an empty default."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])
        executor = AgentExecutor(agent)

        text = '```tool_call\n{"tool": "filesystem"}\n```'
        result = executor._parse_tool_call(text)
        assert result is not None
        assert result["tool"] == "filesystem"
        assert result["operation"] == ""
        assert result["args"] == {}

    def test_parse_non_dict_args_gets_default(self):
        """Test tool call with non-dict args gets an empty dict default."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])
        executor = AgentExecutor(agent)

        text = '```tool_call\n{"tool": "filesystem", "operation": "view_file", "args": "not-a-dict"}\n```'
        result = executor._parse_tool_call(text)
        assert result is not None
        assert result["args"] == {}

    def test_parse_non_string_tool_returns_none(self):
        """Test tool call with non-string tool value is rejected."""
        provider = MockProvider()
        agent = Agent(config=AgentConfig(), providers=[provider])
        executor = AgentExecutor(agent)

        text = '```tool_call\n{"tool": 12345, "operation": "view_file"}\n```'
        result = executor._parse_tool_call(text)
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
