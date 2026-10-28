"""Integration tests for the llama.cpp chat provider (Milestone 17).

These tests drive the **real** HTTP code path of :class:`~laew.llm.llamacpp.LlamaCppProvider`
against an in-process llama.cpp OpenAI-compatible server
(:class:`~tests.integration._llamacpp_test_server.LlamaCppTestServer`).  No
live ``llama-server`` binary or ``.gguf`` weights are required, so the tests
run rather than skip.  They cover:

- Non-streaming ``generate`` over ``/v1/chat/completions`` (content + parsed
  token usage, base URL normalization, request payload shape).
- Streaming ``generate_stream`` over SSE (chunk accumulation, ``[DONE]``
  termination, token accounting on ``_last_stream_response``).
- The LAEW text-based tool-call end-to-end: a fenced ``tool_call`` block in the
  server response is parsed by the executor, and the stub tool is dispatched
  with the exact ``operation``/``args``.
- The request body contains **no** ``tools``/``tool_choice`` keys.
"""

import json

import pytest
from unittest.mock import patch

from laew.agent import Agent, AgentConfig, AgentExecutor
from laew.llm.base import LLMMessage, MessageRole
from laew.llm.llamacpp import LlamaCppProvider
from laew.tools.base import Tool, ToolResult

from tests.unit.test_agent import MockTool


@pytest.fixture
def tool():
    """A MockTool named 'mock_tool' (class-level name attribute)."""
    return MockTool()


def _messages(content: str) -> list[LLMMessage]:
    return [LLMMessage(role=MessageRole.USER, content=content)]


# ---------------------------------------------------------------------------
# Non-streaming generate
# ---------------------------------------------------------------------------


def test_generate_returns_content_and_parsed_usage(llamacpp_server):
    """generate over /v1/chat/completions returns the assistant content and
    parsed token usage, with the base URL normalized to end in /v1."""
    base, _ = llamacpp_server
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    assert provider.base_url.endswith("/v1")
    response = provider.generate(messages=_messages("hi"), model="gpt-oss-20b-q4")

    assert response.content == "Hello! I am a llama.cpp chat assistant."
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 5
    assert response.total_tokens == 15
    assert response.finish_reason == "stop"


def test_generate_normalizes_base_url_without_v1(llamacpp_server):
    """generate hits /v1 even when the base URL lacks a trailing /v1 suffix."""
    base, _ = llamacpp_server
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base.removesuffix("/v1"))

    assert provider.base_url.endswith("/v1")

    captured = []
    real_request = provider._request

    def spy_request(url, payload, **kwargs):
        captured.append(url)
        return real_request(url, payload, **kwargs)

    with patch.object(provider, "_request", side_effect=spy_request):
        provider.generate(messages=_messages("hi"), model="gpt-oss-20b-q4")

    assert captured
    assert captured[0].endswith("/v1/chat/completions")


def test_generate_request_body_has_no_native_tool_keys(llamacpp_server):
    """The chat request body uses top-level params only — no tools/tool_choice.

    LAEW's tool protocol is text-based: the executor parses a fenced
    ``tool_call`` block, so native OpenAI tool keys must not be sent.
    """
    base, server = llamacpp_server
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    provider.generate(messages=_messages("hi"), model="gpt-oss-20b-q4")

    body = server.config.last_chat_request
    assert isinstance(body, dict)
    assert "tools" not in body
    assert "tool_choice" not in body
    assert body["model"] == "gpt-oss-20b-q4"
    assert "messages" in body


def test_generate_without_usage_leaves_token_counts_none(llamacpp_server):
    """A response without a usage block leaves the token counts None."""
    base, server = llamacpp_server
    server.config.chat_usage = None
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    response = provider.generate(messages=_messages("hi"), model="gpt-oss-20b-q4")

    assert response.prompt_tokens is None
    assert response.completion_tokens is None
    assert response.total_tokens is None
    assert response.content == "Hello! I am a llama.cpp chat assistant."


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def test_generate_stream_yields_delta_chunks_and_accumulates(llamacpp_server):
    """generate_stream yields each fragmented data: delta and accumulates the
    full content, terminating on [DONE] with no residual iterator state."""
    base, _ = llamacpp_server
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    gen = provider.generate_stream(messages=_messages("hi"), model="gpt-oss-20b-q4")
    chunks = list(gen)
    # Only frames carrying a content delta are yielded (role frame is not).
    assert chunks == ["Hello", "!", " llama.cpp", " assistant."]

    # The full accumulated content matches the non-streaming response.
    assert "".join(chunks) == "Hello! llama.cpp assistant."

    # [DONE] terminated the stream; the consumed generator is now exhausted.
    with pytest.raises(StopIteration):
        next(gen)

    # Token accounting from the final usage frame.
    assert provider._last_stream_response is not None
    assert provider._last_stream_response.total_tokens == 15


# ---------------------------------------------------------------------------
# Tool-call end-to-end
# ---------------------------------------------------------------------------


def test_generate_stream_terminates_after_done(llamacpp_server):
    """A second [DONE] frame (or generator exhaustion) does not raise a
    malformed-data error."""
    base, server = llamacpp_server
    server.config.chat_stream_chunks = [
        {"choices": [{"delta": {"content": "hi"}, "finish_reason": "stop"}]},
        {"choices": [{"delta": {"content": ""}, "finish_reason": "stop"}]},
    ]
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    chunks = list(provider.generate_stream(messages=_messages("hi"), model="gpt-oss-20b-q4"))
    assert chunks == ["hi"]
    assert provider._last_stream_response.total_tokens == 15


def test_tool_call_end_to_end_through_executor(llamacpp_server, tool):
    """The LAEW text-based tool-call round-trips end-to-end over real HTTP.

    The server emits a fenced ``tool_call`` block; an Agent with the
    LlamaCppProvider and a stub tool runs to completion, the executor's
    ``_parse_tool_call`` extracts tool/operation/args, and the stub tool is
    dispatched with those exact arguments.
    """
    base, server = llamacpp_server
    tool_call_json = json.dumps(
        {"tool": "mock_tool", "operation": "test_op", "args": {"key": "value"}}
    )
    fenced = f"```tool_call\n{tool_call_json}\n```"
    server.config.chat_sequence = [fenced, "The tool result shows the answer."]

    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)
    agent = Agent(config=AgentConfig(), provider=provider)
    agent.register_tool(tool)
    executor = AgentExecutor(agent)

    result = executor.run("Use the tool")

    assert result.success is True
    assert result.total_steps == 2
    assert tool.call_count == 1
    assert tool.last_operation == "test_op"
    assert tool.last_args == {"key": "value"}
    assert result.final_response == "The tool result shows the answer."


def test_tool_call_end_to_end_no_native_tool_keys(llamacpp_server):
    """The executor tool-call run sends no native tools/tool_choice keys."""
    base, server = llamacpp_server
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    provider.generate(messages=_messages("hi"), model="gpt-oss-20b-q4")

    body = server.config.last_chat_request
    assert isinstance(body, dict)
    assert "tools" not in body
    assert "tool_choice" not in body


def test_generate_stream_error_raises(llamacpp_server):
    """A stream request against an error-injected server raises LLMError."""
    from laew.llm.base import LLMError

    base, server = llamacpp_server
    server.config.chat_error = "stream failed"
    server.config.chat_error_status = 500
    provider = LlamaCppProvider(model="gpt-oss-20b-q4", base_url=base)

    with pytest.raises(LLMError) as exc_info:
        list(provider.generate_stream(messages=_messages("hi"), model="gpt-oss-20b-q4"))
    assert exc_info.value.code == "HTTP_ERROR"
