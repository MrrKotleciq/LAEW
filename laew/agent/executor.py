"""Agent execution loop coordinating LLM generation and tool calling."""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from laew.agent.base import Agent, AgentError
from laew.llm.base import LLMError, LLMMessage, MessageRole
from laew.tools.base import ToolResult


@dataclass
class ExecutionStep:
    """A single step in the agent's execution loop."""

    step_number: int
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    operation: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    tool_result: Optional[ToolResult] = None
    response: Optional[str] = None


@dataclass
class ExecutionResult:
    """Final result of an agent execution run."""

    agent_name: str
    steps: List[ExecutionStep] = field(default_factory=list)
    final_response: str = ""
    total_steps: int = 0
    success: bool = True
    error: Optional[str] = None


class AgentExecutor:
    """
    Executes an agent loop: Thought -> Action -> Observation -> Response.

    Parses tool calls from LLM responses using JSON format blocks:
    ```tool_call
    {"tool": "filesystem", "operation": "view_file", "args": {"file_path": "foo.py"}}
    ```
    """

    TOOL_CALL_PATTERN = re.compile(
        r"```(?:tool_call|json)?\s*(\{.*?\})\s*```", re.DOTALL
    )

    def __init__(self, agent: Agent):
        self.agent = agent

    def _parse_tool_call(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract a structured tool call from text if present."""
        matches = self.TOOL_CALL_PATTERN.findall(text)
        for match in matches:
            try:
                data = json.loads(match)
                # Validate required structure
                if isinstance(data, dict) and "tool" in data and isinstance(data["tool"], str):
                    # Ensure operation and args exist with defaults
                    if "operation" not in data:
                        data["operation"] = ""
                    if "args" not in data:
                        data["args"] = {}
                    elif not isinstance(data["args"], dict):
                        data["args"] = {}
                    return data
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def _format_tools_description(self) -> str:
        """Format descriptions of available tools for inclusion in prompt."""
        if not self.agent.tools:
            return "No tools available."

        lines = ["Available tools:"]
        for name, tool in self.agent.tools.items():
            lines.append(f"- {name}: {tool.description}")
            if hasattr(tool, "operations") and tool.operations:
                lines.append(f"  Operations: {', '.join(tool.operations.keys())}")
        return "\n".join(lines)

    def run(self, user_prompt: str) -> ExecutionResult:
        """
        Execute the agent loop until completion or max iterations.

        Args:
            user_prompt: The user query or task description

        Returns:
            ExecutionResult containing all execution steps and final output
        """
        result = ExecutionResult(agent_name=self.agent.config.name)

        # Build initial system message with tool instructions
        system_text = self.agent.get_system_prompt_text()
        tools_desc = self._format_tools_description()

        full_system_prompt = (
            f"{system_text}\n\n"
            f"{tools_desc}\n\n"
            "To use a tool, respond with a JSON block in the format:\n"
            "```tool_call\n"
            '{"tool": "<tool_name>", "operation": "<operation_name>", "args": {<arguments>}}\n'
            "```\n"
            "If you do not need any more tools, provide your final answer directly without tool blocks."
        )

        # Prepare messages
        messages: List[LLMMessage] = [
            LLMMessage(role=MessageRole.SYSTEM, content=full_system_prompt)
        ]

        # Include conversation history
        messages.extend(self.agent.history)

        # Add the new user message
        messages.append(LLMMessage(role=MessageRole.USER, content=user_prompt))
        self.agent.add_message(MessageRole.USER, user_prompt)

        iteration = 0
        while iteration < self.agent.config.max_iterations:
            iteration += 1
            step = ExecutionStep(step_number=iteration)

            # Attempt LLM generation with retry + provider fallback.
            llm_response = None
            last_error = None
            retry_config = self.agent.config.retry
            attempt = 0

            while attempt < retry_config.max_attempts:
                try:
                    llm_response = self.agent.provider.generate(
                        messages=messages,
                        model=self.agent.config.model,
                        temperature=self.agent.config.temperature,
                        max_tokens=self.agent.config.max_tokens,
                    )
                    break  # Success, exit retry loop
                except Exception as e:
                    last_error = e
                    attempt += 1

                    if attempt >= retry_config.max_attempts:
                        # Exhausted retries for current provider; try fallback.
                        try:
                            self.agent._current_provider_index += 1
                            self.agent._ensure_available_provider()
                            attempt = 0
                        except RuntimeError:
                            pass  # No more providers; will fail after loop
                    else:
                        # Exponential backoff between retries.
                        backoff_ms = min(
                            retry_config.backoff_base_ms * (2 ** (attempt - 1)),
                            retry_config.max_backoff_ms
                        )
                        time.sleep(backoff_ms / 1000.0)  # Convert to seconds

            if llm_response is None:
                result.success = False
                result.error = f"LLM generation failed at step {iteration} after {retry_config.max_attempts} attempts: {str(last_error)}"
                result.steps.append(step)
                return result

            response_content = llm_response.content
            step.thought = response_content

            # Parse tool call
            tool_call = self._parse_tool_call(response_content)

            if not tool_call:
                # No tool call, treat as final answer
                step.response = response_content
                result.steps.append(step)
                result.final_response = response_content
                result.total_steps = iteration
                self.agent.add_message(MessageRole.ASSISTANT, response_content)
                return result

            # Tool call requested
            tool_name = tool_call.get("tool")
            operation = tool_call.get("operation")
            args = tool_call.get("args", {})

            step.tool_name = tool_name
            step.operation = operation
            step.args = args

            if tool_name not in self.agent.tools:
                tool_output = f"Error: Tool '{tool_name}' not found."
                tool_res = ToolResult(success=False, error_code="ERR_TOOL_NOT_FOUND", error_message=tool_output)
            else:
                tool = self.agent.tools[tool_name]
                try:
                    tool_res = tool.call(operation, **args)
                except Exception as e:
                    tool_res = ToolResult(success=False, error_code="ERR_AGENT_EXECUTION", error_message=str(e))

            step.tool_result = tool_res
            result.steps.append(step)

            # Record assistant call and tool observation in context
            messages.append(LLMMessage(role=MessageRole.ASSISTANT, content=response_content))
            self.agent.add_message(MessageRole.ASSISTANT, response_content)

            obs_content = (
                f"Tool '{tool_name}' (operation '{operation}') result:\n"
                f"Success: {tool_res.success}\n"
                f"Data: {json.dumps(tool_res.data) if tool_res.data is not None else 'None'}\n"
            )
            if tool_res.error_code:
                obs_content += f"Error: {tool_res.error_message}\n"

            messages.append(LLMMessage(role=MessageRole.USER, content=obs_content))
            self.agent.add_message(MessageRole.USER, obs_content)

        # Reached max iterations
        result.success = False
        result.error = f"Reached maximum iterations ({self.agent.config.max_iterations}) without completion."
        result.total_steps = iteration
        return result
