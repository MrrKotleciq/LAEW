"""Agent execution loop coordinating LLM generation and tool calling."""

import inspect
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from laew.agent.base import Agent, AgentError
from laew.llm.base import LLMError, LLMMessage, LLMProvider, LLMResponse, MessageRole
from laew.tools.base import Tool, ToolResult

logger = logging.getLogger("laew.agent.executor")


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
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


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
    _FENCE = chr(96) * 3  # ```

    def __init__(self, agent: Agent):
        self.agent = agent
        # The system prompt (system text + tool descriptions + the constant
        # instruction block) is rebuilt from the same inputs on every run().
        # Cache the rendered string so inspect-based hints and description
        # formatting run once per executor instance instead of per user turn.
        self._system_prompt_cache: Optional[str] = None

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

    @staticmethod
    def _looks_like_tool_call_attempt(text: str) -> bool:
        """
        Heuristically detect a malformed tool-call attempt or raw command.

        Returns True when the text contains:
        1. The characteristic markers of a malformed JSON tool-call attempt
           ('\"tool\":' + '\"operation\":' + opening brace or fence), OR
        2. A raw shell command in a fenced code block (e.g. ```ls -l```),
           which indicates the model is trying to execute a command directly
           instead of using the tool_call format.
        """
        if not text:
            return False
        has_fence = '```' in text
        has_tool = '"tool"' in text
        has_op = '"operation"' in text
        has_open_brace = '{' in text
        # Match the exact pattern the prompt asks for (code fence + the two
        # required JSON keys), or the two keys plus an unclosed brace that
        # looks like truncated JSON.
        if has_tool and has_op and (has_fence or has_open_brace):
            return True
        # Detect raw shell commands in fenced code blocks (e.g. ```ls -l```).
        # Common indicators: the text is mostly a single command, no JSON structure.
        if has_fence:
            # Match ```<command>``` where command is a short shell-like string
            raw_cmd_pattern = re.compile(
                r'```\s*(ls|dir|cat|git\s+\w+|cd|pwd|echo|grep|find|mkdir|rm|cp|mv|touch|chmod|chown|sudo|apt|pip|npm|yarn|docker|kubectl|curl|wget)\b[^`]*\s*```',
                re.IGNORECASE
            )
            if raw_cmd_pattern.search(text):
                return True
        return False

    def _resolve_tool_name(self, requested: str) -> str:
        """
        Resolve a model-supplied tool name against the registered registry.

        Accepts an exact registry key first; otherwise compares a normalized
        (lowercase) form so "TerminalTool" and "terminal" both resolve to the
        TerminalTool entry.  Returns the canonical registry key when found,
        otherwise passes the requested name through unchanged.
        """
        if requested in self.agent.tools:
            return requested
        requested_lower = requested.lower()
        for registered in self.agent.tools:
            if registered.lower() == requested_lower:
                return registered
        return requested

    # Maximum times the model may repeat the *identical* tool+operation
    # before we inject a corrective stop instruction.
    _REPEAT_LIMIT: int = 3

    @staticmethod
    def _is_repeating(
        steps: list["ExecutionStep"],
        current_tool: str,
        current_operation: str,
        repeat_limit: int,
    ) -> bool:
        """Return True if the model has called the same tool+operation too many times consecutively."""
        recent = [
            s for s in steps[-(repeat_limit):]
            if s.tool_name and s.operation
        ]
        if len(recent) < repeat_limit:
            return False
        return all(
            (s.tool_name == current_tool and s.operation == current_operation)
            for s in recent
        )

    def _valid_operations_for(self, tool: Tool) -> list[str]:
        """
        Derive the valid operation names for a tool from its method surface.

        Underlying wrappers are prefixed with `_` (e.g. `_view_file` -> `view_file`);
        the public `execute(operation, ...)` dispatches on those names.
        """
        names = []
        for attr in dir(tool):
            if attr.startswith("_") and not attr.startswith("__"):
                names.append(attr[1:])
        return sorted(names)

    def _operation_hints(self, tool: Tool) -> str:
        """Format valid operations for a tool with their required parameter names."""
        # First check if tool has explicit operations dictionary
        if hasattr(tool, 'operations') and tool.operations:
            hints = []
            for op_name, op_info in tool.operations.items():
                params = op_info.get('params', [])
                if params:
                    hints.append(f"{op_name}({', '.join(params)})")
                else:
                    hints.append(op_name)
            return ", ".join(hints) if hints else "no documented operations"

        # Fall back to introspection of methods starting with underscore
        hints = []
        for method_name in self._valid_operations_for(tool):
            method = getattr(tool, method_name, None)
            if not callable(method):
                continue
            try:
                params = inspect.signature(method).parameters.values()
            except (TypeError, ValueError):
                continue
            param_names = [
                p.name
                for p in params
                if p.name not in ("self", "kwargs", "args")
            ]
            if param_names:
                hints.append(f"{method_name}({', '.join(param_names)})")
            else:
                hints.append(method_name)
        return ", ".join(hints) if hints else "no documented operations"

    def _format_tools_description(self) -> str:
        """Format descriptions of available tools for inclusion in prompt."""
        if not self.agent.tools:
            return "No tools available."

        lines = ["Available tools:"]
        for name, tool in self.agent.tools.items():
            lines.append(f"- {name}: {tool.description}")
            lines.append(f"  Operations: {self._operation_hints(tool)}")
        return "\n".join(lines)

    def _build_system_prompt(self) -> str:
        """
        Build the full system prompt (system text + tools + instructions).

        Memoized on the executor instance: the inputs (system prompt text,
        tool registry, operation hints) are static for the agent's lifetime,
        so the expensive inspect-based hint formatting runs exactly once.
        """
        if self._system_prompt_cache is not None:
            return self._system_prompt_cache

        system_text = self.agent.get_system_prompt_text()
        tools_desc = self._format_tools_description()

        full_system_prompt = (
            f"{system_text}\n\n"
            f"{tools_desc}\n\n"
            "IMPORTANT: You MUST always use the structured tool_call format to "
            "invoke tools. NEVER output raw shell commands, never write bare "
            "commands inside ``` blocks, and never try to run commands directly.\n"
            "To use a tool, respond with EXACTLY one JSON block wrapped in a "
            "```tool_call fenced code block (if your tools describe operations "
            "with parameters, use those exact parameter names as keys in \"args\"):\n"
            "```tool_call\n"
            '{"tool": "<tool_name>", "operation": "<operation_name>", "args": {<arguments>}}\n'
            "```\n"
            "\n"
            "Examples — the \"tool\" value MUST be the exact name listed above "
            "(e.g. FilesystemTool, GitTool, TerminalTool, WebTool):\n"
            "```tool_call\n"
            '{"tool": "FilesystemTool", "operation": "list_dir", "args": {"directory_path": "."}}\n'
            "```\n"
            "```tool_call\n"
            '{"tool": "TerminalTool", "operation": "run_command", "args": {"command": "ls -la"}}\n'
            "```\n"
            "```tool_call\n"
            '{"tool": "GitTool", "operation": "git_status", "args": {}}\n'
            "```\n"
            "\n"
            "NEVER write raw shell commands like ```ls -l``` or ```dir``` outside of "
            "a proper tool_call block. ALWAYS use the JSON tool_call format shown above.\n"
            "Never abbreviate or rename \"tool\"/\"operation\"/\"args\". "
            "If the tool or operation you want is not listed above, you may not "
            "call it. If you do not need any tools, provide your final answer "
            "directly without a tool block.\n"
            "\n"
            "After a tool completes successfully and you have the information "
            "you need, STOP calling tools and give your final answer in plain "
            "text. Do not repeat the same tool call unless you actually need "
            "different data."
        )
        self._system_prompt_cache = full_system_prompt
        return full_system_prompt

    def _token_ratio(self) -> Optional[float]:
        """Return the configured calibrated chars/token ratio, if any."""
        return getattr(self.agent.config, "token_ratio", None)

    @staticmethod
    def _provider_streams(provider: LLMProvider) -> bool:
        """
        Return True when the provider implements true incremental streaming.

        ``LLMProvider.generate_stream`` has a concrete default that delegates
        to ``generate()`` and yields the whole response as one chunk.  Only
        providers overriding it (e.g. ``OllamaProvider``) can stream; the
        executor keeps using ``generate()`` otherwise so results and token
        accounting stay identical.  Uses ``getattr`` so duck-typed providers
        that merely implement ``generate`` (no ``generate_stream``) are treated
        as non-streaming.
        """
        stream_method = getattr(type(provider), "generate_stream", None)
        if stream_method is None:
            return False
        return stream_method is not LLMProvider.generate_stream

    def _generate(self, messages: list, stream: bool) -> LLMResponse:
        """
        Generate an LLM response, optionally via the provider's stream path.

        When ``stream`` is set and the provider overrides ``generate_stream``,
        the chunks are consumed through the streaming endpoint and the
        accumulated content plus the stream's final token counts are returned
        as a normal :class:`LLMResponse`.  Otherwise — and for providers that
        only inherit the single-chunk default — ``generate()`` is used so
        external behaviour (final text, token accounting) is identical either
        way.

        Args:
            messages: Work message list sent to the provider
            stream: Prefer the streaming endpoint when available

        Returns:
            LLMResponse with the full accumulated content
        """
        model = self.agent.config.model
        if not (stream and self._provider_streams(self.agent.provider)):
            return self.agent.provider.generate(
                messages=messages,
                model=model,
                temperature=self.agent.config.temperature,
                max_tokens=self.agent.config.max_tokens,
            )

        chunks: list[str] = []
        for chunk in self.agent.provider.generate_stream(
            messages=messages,
            model=model,
            temperature=self.agent.config.temperature,
            max_tokens=self.agent.config.max_tokens,
        ):
            chunks.append(chunk)

        streamed = getattr(self.agent.provider, "_last_stream_response", None)
        return LLMResponse(
            content="".join(chunks),
            model=model,
            prompt_tokens=streamed.prompt_tokens if streamed else None,
            completion_tokens=streamed.completion_tokens if streamed else None,
            total_tokens=streamed.total_tokens if streamed else None,
            finish_reason=streamed.finish_reason if streamed else "stop",
        )

    def _estimate_messages_tokens(self, messages: list) -> int:
        """Estimate tokens for messages using the configured ratio."""
        from laew.prompts.context_budget import TokenEstimator

        dicts = [m.to_dict() if hasattr(m, "to_dict") else m for m in messages]
        return TokenEstimator.estimate_messages(dicts, self._token_ratio())

    @staticmethod
    def _message_char_count(message) -> int:
        """Character length of a message's content (dict or LLMMessage)."""
        content = message.content if hasattr(message, "content") else message.get("content", "")
        return len(content or "")

    @staticmethod
    def _estimate_chars(total_length: int, chars_per_token: float) -> int:
        """Token estimate for a running content length, mirroring TokenEstimator."""
        return max(1, int(total_length // chars_per_token))

    def _trim_to_budget(
        self, messages: list, live_user_index: int
    ) -> None:
        """
        Trim oldest seeded conversation turns when ``messages`` exceeds budget.

        Uses the real token count from the previous ``generate()`` when one is
        available, otherwise the calibrated ``TokenEstimator`` estimate.  The
        system prompt (index 0) and the live user turn (``live_user_index``)
        are never trimmed.  Consecutive steps can still append tool
        observations above this seeded-history trim; this keeps the *seeded*
        conversation from overflowing the configured context window (P6).

        Args:
            messages: The work message list sent to the provider
            live_user_index: Index of the live user turn (never trimmed)
        """
        budget = self.agent.config.context_budget
        if budget is None:
            return
        available = budget.available_for_prompt()
        # Convert each message's content length once and track the running
        # total (including the separator spaces ``estimate_messages`` would
        # join).  This gives both the under-budget fast path and the trim below
        # a single O(n) pass: re-joining and re-estimating the whole list after
        # every drop was O(k^2) once history crossed the budget.
        from laew.prompts.context_budget import TokenEstimator

        ratio = self._token_ratio()
        chars_per_token = (
            ratio if ratio and ratio > 0 else TokenEstimator.CHARS_PER_TOKEN
        )
        lengths = [self._message_char_count(message) for message in messages]
        separator_count = max(0, len(messages) - 1)
        total_length = sum(lengths, separator_count)
        if self._estimate_chars(total_length, chars_per_token) <= available:
            return
        # Drop oldest non-system turns (history seeded before the live turn)
        # until the estimate fits or only the live turn remains.  The live user
        # turn sits at ``live_user_index``; once it drops to index 1 (directly
        # after the system prompt) there is nothing left to trim.
        while (
            live_user_index > 1
            and self._estimate_chars(total_length, chars_per_token) > available
        ):
            # messages[0] is SYSTEM; messages[1] is the oldest seeded turn.
            total_length -= lengths[1] + 1  # content plus its join separator
            del messages[1]
            del lengths[1]
            live_user_index -= 1
        if self._estimate_chars(total_length, chars_per_token) > available:
            logger.warning(
                "Agent context estimate %d exceeds budget (%d) even after "
                "trimming to the live turn; sending oversized prompt",
                self._estimate_chars(total_length, chars_per_token),
                available,
            )

    def run(self, user_prompt: str, stream: bool = False) -> ExecutionResult:
        """
        Execute the agent loop until completion or max iterations.

        Args:
            user_prompt: The user query or task description
            stream: When True (and the provider overrides ``generate_stream``),
                LLM calls stream through the provider's streaming endpoint;
                the accumulated result is identical to the non-streaming path.
                Tool-call parsing still needs the full response, so streaming
                here is a transport optimisation, not an output-different one.

        Returns:
            ExecutionResult containing all execution steps and final output
        """
        result = ExecutionResult(agent_name=self.agent.config.name)

        full_system_prompt = self._build_system_prompt()

        # Prepare messages
        messages: List[LLMMessage] = [
            LLMMessage(role=MessageRole.SYSTEM, content=full_system_prompt)
        ]

        # Include conversation history
        messages.extend(self.agent.history)

        # Add the new user message
        messages.append(LLMMessage(role=MessageRole.USER, content=user_prompt))
        self.agent.add_message(MessageRole.USER, user_prompt)
        # Index of the live user turn inside ``messages``.  Budget enforcement
        # may drop OLDER seeded history turns but never the system prompt
        # (index 0) nor this live turn.
        live_user_index = len(messages) - 1

        iteration = 0
        while iteration < self.agent.config.max_iterations:
            iteration += 1
            step = ExecutionStep(step_number=iteration)

            # Enforce the configured context budget: drop oldest seeded turns
            # before growing further (P6 / ADR-004).
            self._trim_to_budget(messages, live_user_index)

            # Attempt LLM generation with retry + bounded provider fallback.
            #
            # The per-provider retry loop below can switch to a fallback
            # provider when the current one fails.  Each switch resets
            # `attempt` to 0, so without an outer bound a set of providers
            # that advertise availability but keep failing would loop
            # forever.  `remaining_tries` bounds the total number of
            # generate() calls issued for this single step.
            llm_response = None
            last_error = None
            retry_config = self.agent.config.retry
            attempt = 0
            remaining_tries = max(
                retry_config.max_attempts * len(self.agent.providers),
                retry_config.max_attempts,
            )

            while attempt < retry_config.max_attempts and remaining_tries > 0:
                remaining_tries -= 1
                try:
                    llm_response = self._generate(messages, stream=stream)
                    break  # Success, exit retry loop
                except Exception as e:
                    last_error = e
                    attempt += 1

                    if attempt >= retry_config.max_attempts:
                        # Exhausted retries for current provider; try fallback.
                        if remaining_tries <= 0:
                            break  # No budget left; will fail after loop
                        try:
                            self.agent._current_provider_index += 1
                            self.agent._ensure_available_provider()
                            attempt = 0
                        except RuntimeError:
                            break  # No more providers; will fail after loop
                    else:
                        # Exponential backoff between retries (only while we
                        # still have budget, so we never sleep into a loop we
                        # cannot finish).
                        if remaining_tries > 0:
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

            # Real token accounting (Stream C): accumulate actual counts from
            # the provider's response when reported.
            if llm_response.prompt_tokens:
                result.prompt_tokens += llm_response.prompt_tokens
            if llm_response.completion_tokens:
                result.completion_tokens += llm_response.completion_tokens
            if llm_response.total_tokens:
                result.total_tokens += llm_response.total_tokens

            response_content = llm_response.content
            step.thought = response_content

            # Parse tool call
            tool_call = self._parse_tool_call(response_content)

            if not tool_call:
                # No valid tool call found.  Check whether the model
                # *looked like* it was trying to call a tool so we
                # can give a corrective observation instead of
                # silently swallowing the attempt as a final answer.
                if self._looks_like_tool_call_attempt(response_content):
                    step.thought = (
                        "Model attempted a tool call but the "
                        "JSON could not be parsed.  Correcting format."
                    )
                    correction = (
                        "Your tool call could not be parsed as valid "
                        "JSON.  Please respond with a properly fenced "
                        "```tool_call block:\n"
                        "```tool_call\n"
                        '{"tool": "<name>", "operation": "<op>", "args": {}}\n'
                        "```\n"
                        "\n"
                        "Use exact key names \"tool\", \"operation\", "
                        "\"args\" and valid JSON inside the fence.\n"
                        "\n"
                        "NEVER output raw shell commands or bare commands "
                        "in fenced code blocks. ALWAYS use the JSON "
                        "tool_call format above."
                    )
                    messages.append(
                        LLMMessage(
                            role=MessageRole.ASSISTANT,
                            content=response_content,
                        )
                    )
                    self.agent.add_message(MessageRole.ASSISTANT, response_content)
                    messages.append(
                        LLMMessage(role=MessageRole.USER, content=correction)
                    )
                    self.agent.add_message(MessageRole.USER, correction)
                    result.steps.append(step)
                    continue  # Retry the loop with corrective feedback

                # No tool call at all — treat as final answer
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

            # Resolve the tool name, tolerating a case variant (e.g. "terminal"
            # instead of "TerminalTool").  The prompt teaches the exact registry
            # keys, but a lowercased form is a cheap safety net.
            resolved_name = self._resolve_tool_name(tool_name)
            tool = self.agent.tools.get(resolved_name)
            if tool is None:
                tool_output = f"Error: Tool '{tool_name}' not found."
                tool_res = ToolResult(success=False, error_code="ERR_TOOL_NOT_FOUND", error_message=tool_output)
            else:
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

            # Repetition guard: if the model keeps issuing the *identical*
            # tool+operation call, stop feeding it eager observations and
            # force it to synthesize an answer from what it already has.
            if self._is_repeating(
                result.steps, tool_name, operation, self._REPEAT_LIMIT
            ):
                stop_msg = (
                    "You have called the same tool with the same operation "
                    "several times in a row without producing an answer. Stop "
                    "calling tools now. Using the information already collected, "
                    "write your final answer to the user's original question in "
                    "plain text. Do NOT output another tool_call block."
                )
                messages.append(
                    LLMMessage(role=MessageRole.USER, content=stop_msg)
                )
                self.agent.add_message(MessageRole.USER, stop_msg)

        # Reached max iterations without a final answer.  Before failing,
        # give the model one last chance to synthesize an answer from the
        # tool results it already collected.  This converts a hard failure
        # (e.g. the model over-researching) into a usable response.
        forced_prompt = (
            "You have reached the tool-call limit. Do NOT call any tools again. "
            "Using the tool results already collected, write your final answer "
            "to the user's original question in plain text now."
        )
        messages.append(LLMMessage(role=MessageRole.USER, content=forced_prompt))
        self._trim_to_budget(messages, live_user_index)
        try:
            llm_response = self._generate(messages, stream=stream)
        except Exception as e:
            result.success = False
            result.error = (
                f"Reached maximum iterations ({self.agent.config.max_iterations}) "
                f"without completion, and final answer attempt failed: {str(e)}"
            )
            result.total_steps = iteration
            return result

        # Real token accounting for the forced final generation.
        if llm_response.prompt_tokens:
            result.prompt_tokens += llm_response.prompt_tokens
        if llm_response.completion_tokens:
            result.completion_tokens += llm_response.completion_tokens
        if llm_response.total_tokens:
            result.total_tokens += llm_response.total_tokens

        # Return whatever the forced generation produced as the final answer —
        # but only if it is genuinely an answer.  If the model still emits a
        # tool-call block (or empty output), treat the run as failed rather
        # than surfacing a raw tool_call as a "final answer".
        final_answer = llm_response.content
        still_tool_calling = (
            self._parse_tool_call(final_answer) is not None
            or self._looks_like_tool_call_attempt(final_answer)
        )
        if not final_answer.strip() or still_tool_calling:
            result.success = False
            result.error = (
                f"Reached maximum iterations ({self.agent.config.max_iterations}) "
                f"without a valid final answer."
            )
            result.total_steps = iteration
            return result

        step = ExecutionStep(step_number=iteration + 1)
        step.response = final_answer
        result.steps.append(step)
        result.final_response = final_answer
        result.total_steps = iteration + 1
        result.success = True
        return result
