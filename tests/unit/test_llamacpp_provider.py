"""Unit tests for the llama.cpp OpenAI-compatible chat provider.

These tests mock the HTTP layer (``requests``) so no llama.cpp server is
required.  They cover:

- Base URL normalization (with and without a trailing ``/v1``).
- Non-streaming chat: content and token-usage parsing.
- Absent ``usage`` block -> token counts left ``None``.
- Model listing and availability.
- SSE streaming: chunk yields, ``[DONE]`` termination, usage accumulation.
- HTTP errors and timeouts -> ``LLMError``.
- Invariant: the request body never carries ``tools``/``tool_choice``.
"""

from unittest.mock import MagicMock, Mock, patch

import json
import pytest

import requests

from laew.llm.base import LLMError, LLMMessage, MessageRole
from laew.llm.llamacpp import LlamaCppProvider
from laew.agent.base import Agent, AgentConfig
from laew.agent.executor import AgentExecutor

DEFAULT_BASE_URL = "http://127.0.0.1:8080"


def _chat_completion_payload(content: str, usage: dict) -> dict:
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": usage,
    }


def _list_models_payload(ids: list[str]) -> dict:
    return {"object": "list", "data": [{"id": i} for i in ids]}


# ---------------------------------------------------------------------------
# Base URL normalization
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_generate_normalizes_base_url_without_v1(post_mock):
    """generate resolves identically for a base URL without a trailing /v1."""
    payload = _chat_completion_payload("Hi", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    provider.generate([LLMMessage(role=MessageRole.USER, content="Hello")], model="model")

    expected_url = f"{DEFAULT_BASE_URL}/v1/chat/completions"
    assert post_mock.call_args.args[0] == expected_url


@patch("requests.post")
def test_generate_normalizes_base_url_with_v1(post_mock):
    """generate resolves identically for a base URL already ending in /v1."""
    payload = _chat_completion_payload("Hi", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=f"{DEFAULT_BASE_URL}/v1")
    provider.generate([LLMMessage(role=MessageRole.USER, content="Hello")], model="model")

    expected_url = f"{DEFAULT_BASE_URL}/v1/chat/completions"
    assert post_mock.call_args.args[0] == expected_url


@patch("requests.post")
@patch("requests.get")
def test_generate_and_list_models_resolve_identically(get_mock, post_mock):
    """generate and list_models both normalize the base URL to a /v1 form."""
    chat_payload = _chat_completion_payload("Hi", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    models_payload = _list_models_payload(["a", "b"])

    post_mock.return_value = Mock(
        json=lambda: chat_payload,
        status_code=200,
    )
    LlamaCppProvider("model", base_url=DEFAULT_BASE_URL).generate(
        [LLMMessage(role=MessageRole.USER, content="Hello")], model="model"
    )
    chat_call = post_mock.call_args.args[0]

    post_mock.reset_mock()
    get_mock.reset_mock()
    post_mock.return_value = Mock(json=lambda: models_payload, status_code=200)
    get_mock.return_value = Mock(json=lambda: models_payload, status_code=200)
    LlamaCppProvider("model", base_url=f"{DEFAULT_BASE_URL}/v1").list_models()
    models_call = get_mock.call_args.args[0]

    assert chat_call == f"{DEFAULT_BASE_URL}/v1/chat/completions"
    assert models_call == f"{DEFAULT_BASE_URL}/v1/models"


# ---------------------------------------------------------------------------
# Non-streaming chat
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_generate_parses_content_and_usage(post_mock):
    """generate returns LLMResponse content and token counts from the usage block."""
    payload = _chat_completion_payload("Zażółć gęślą jaźń — 25°C — 🐕 🧬 🤝 🐶", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    response = provider.generate(
        [LLMMessage(role=MessageRole.USER, content="Hi")],
        model="model",
        temperature=0.3,
        max_tokens=20,
        stop=["\n"],
    )

    assert response.content == "Zażółć gęślą jaźń — 25°C — 🐕 🧬 🤝 🐶"
    assert response.model == "model"
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 5
    assert response.total_tokens == 15
    assert response.finish_reason == "stop"


@patch("requests.post")
def test_generate_builds_openai_payload(post_mock):
    """generate posts a top-level OpenAI-compatible payload with converted messages."""
    payload = _chat_completion_payload("Hi", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    provider.generate(
        [
            LLMMessage(role=MessageRole.SYSTEM, content="Be helpful"),
            LLMMessage(role=MessageRole.USER, content="Hi"),
        ],
        model="model",
        temperature=0.5,
        max_tokens=20,
        stop=["END"],
    )

    body = post_mock.call_args.kwargs["json"]
    assert body == {
        "model": "model",
        "messages": [
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hi"},
        ],
        "temperature": 0.5,
        "max_tokens": 20,
        "stop": ["END"],
    }


@patch("requests.post")
def test_generate_never_sends_tools_or_tool_choice(post_mock):
    """generate must not send native OpenAI tools/tool_choice — LAEW is text-based."""
    payload = _chat_completion_payload("Hi", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    provider.generate(
        [LLMMessage(role=MessageRole.USER, content="Use a tool")],
        model="model",
        stop=["END"],
    )

    body = post_mock.call_args.kwargs["json"]
    assert "tools" not in body
    assert "tool_choice" not in body


@patch("requests.post")
def test_generate_without_usage_leaves_token_counts_none(post_mock):
    """A response without a usage block leaves the token counts None."""
    payload = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hi"},
                "finish_reason": "stop",
            }
        ],
    }
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    response = provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")

    assert response.content == "Hi"
    assert response.prompt_tokens is None
    assert response.completion_tokens is None
    assert response.total_tokens is None


# ---------------------------------------------------------------------------
# Model listing
# ---------------------------------------------------------------------------


@patch("requests.get")
def test_list_models_parses_models_endpoint(get_mock):
    """list_models parses the /v1/models endpoint into model IDs."""
    get_mock.return_value = Mock(json=lambda: _list_models_payload(["a", "b"]), status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    assert provider.list_models() == ["a", "b"]


@patch("requests.get")
def test_list_models_requests_models_endpoint(get_mock):
    """list_models requests the models endpoint, not chat."""
    get_mock.return_value = Mock(json=lambda: _list_models_payload(["a"]), status_code=200)

    LlamaCppProvider("model", base_url=DEFAULT_BASE_URL).list_models()

    assert get_mock.call_args.args[0] == f"{DEFAULT_BASE_URL}/v1/models"


@patch("requests.get")
def test_list_models_rejects_malformed_data(get_mock):
    """A /v1/models payload must contain a list of data entries."""
    get_mock.return_value = Mock(json=lambda: {"data": "not-a-list"}, status_code=200)

    with pytest.raises(LLMError) as exc_info:
        LlamaCppProvider("model", base_url=DEFAULT_BASE_URL).list_models()
    assert exc_info.value.code == "INVALID_RESPONSE"


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@patch("requests.get")
def test_is_available_true_on_200(get_mock):
    """is_available returns True on a 200 from /v1/models."""
    get_mock.return_value = Mock(status_code=200)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    assert provider.is_available() is True


@patch("requests.get")
def test_is_available_false_on_connection_error(get_mock):
    """is_available returns False when the server is unreachable."""
    get_mock.side_effect = requests.exceptions.ConnectionError("refused")

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    assert provider.is_available() is False


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------


def _iter_lines(lines):
    return iter(lines)


@patch("requests.post")
def test_stream_decodes_utf8_sse_across_byte_boundaries(post_mock):
    sample = "LAEW UTF-8 test: Zażółć gęślą jaźń — 25°C — 🐕 🧬 🤝 🐶"
    payload = ('data: ' + json.dumps({"choices": [{"delta": {"content": sample}}]}, ensure_ascii=False) + '\n\ndata: [DONE]\n\n').encode('utf-8')
    dog = payload.index('🐕'.encode('utf-8'))
    response = requests.Response()
    response.status_code = 200
    response.encoding = 'ISO-8859-1'
    response.iter_content = MagicMock(return_value=iter([payload[:dog + 1], payload[dog + 1:dog + 3], payload[dog + 3:]]))
    response.close = MagicMock()
    post_mock.return_value = response
    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    assert ''.join(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")) == sample


@patch("requests.post")
def test_generate_stream_yields_chunks_and_terminates(post_mock):
    """generate_stream yields each content chunk, accumulates it, and stops at [DONE]."""
    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{"content":" World"}}]}',
        'data: {"choices":[{"delta":{"content":""},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}',
        '[DONE]',
    ]
    post_mock.return_value = Mock(iter_lines=MagicMock(return_value=_iter_lines(lines)))

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    chunks = list(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="Hi")], model="model"))

    assert "".join(chunks) == "Hello World"
    assert provider._last_stream_response is not None
    assert provider._last_stream_response.prompt_tokens == 10
    assert provider._last_stream_response.completion_tokens == 5
    assert provider._last_stream_response.total_tokens == 15
    assert provider._last_stream_response.finish_reason == "stop"
    assert post_mock.call_args.kwargs["timeout"] == (30, 120)


@patch("requests.post")
def test_streamed_llamacpp_response_reaches_executor_with_usage(post_mock):
    """OpenAI usage dicts are normalized before executor token accounting."""
    post_mock.return_value = Mock(iter_lines=MagicMock(return_value=_iter_lines([
        'data: {"choices":[{"delta":{"content":"Streamed answer"}}]}',
        'data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}',
        'data: [DONE]',
    ])))
    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    provider.is_available = Mock(return_value=True)
    agent = Agent(config=AgentConfig(name="test", model="model"), provider=provider)

    result = AgentExecutor(agent).run("Hello", stream=True)

    assert result.success is True
    assert result.final_response == "Streamed answer"
    assert result.prompt_tokens == 10
    assert result.completion_tokens == 5
    assert result.total_tokens == 15
    assert post_mock.call_count == 1


@patch("requests.post")
def test_generate_stream_handles_empty_delta(post_mock):
    """generate_stream ignores empty deltas and still accumulates content."""
    lines = [
        'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        'data: {"choices":[{"delta":{}}]}',
        'data: {"choices":[{"delta":{"content":"!"},"finish_reason":"length"}],"usage":{"prompt_tokens":1,"completion_tokens":2,"total_tokens":3}}',
        '[DONE]',
    ]
    post_mock.return_value = Mock(iter_lines=MagicMock(return_value=_iter_lines(lines)))

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    chunks = list(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="Hi")], model="model"))

    assert "".join(chunks) == "Hello!"


@patch("requests.post")
def test_generate_stream_ignores_non_data_lines(post_mock):
    """generate_stream skips blank and non-data lines."""
    lines = [
        '',
        'data: {"choices":[{"delta":{"content":"OK"}}]}',
        'event: message',
        '[DONE]',
    ]
    post_mock.return_value = Mock(iter_lines=MagicMock(return_value=_iter_lines(lines)))

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    chunks = list(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="Hi")], model="model"))

    assert "".join(chunks) == "OK"
    assert provider._last_stream_response is not None
    assert provider._last_stream_response.prompt_tokens is None
    assert provider._last_stream_response.completion_tokens is None
    assert provider._last_stream_response.total_tokens is None


@patch("requests.post")
def test_generate_stream_rejects_incomplete_eof(post_mock):
    response = Mock(iter_lines=MagicMock(return_value=iter([
        'data: {"choices":[{"delta":{"content":"partial"}}]}',
    ])))
    post_mock.return_value = response
    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    stream = provider.generate_stream([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert next(stream) == "partial"
    with pytest.raises(LLMError, match="ended before completion"):
        next(stream)
    response.close.assert_called_once()


@patch("requests.post")
def test_generate_stream_reports_idle_timeout_clearly(post_mock):
    response = Mock(iter_lines=MagicMock(side_effect=requests.exceptions.ReadTimeout("idle")))
    post_mock.return_value = response
    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)

    with pytest.raises(LLMError, match="no data for 120s") as exc_info:
        list(provider.generate_stream(
            [LLMMessage(role=MessageRole.USER, content="Hi")], model="model"
        ))

    assert exc_info.value.code == "TIMEOUT"
    response.close.assert_called_once()


# ---------------------------------------------------------------------------
# HTTP errors and timeouts
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_generate_raises_on_404(post_mock):
    """A 404 response raises LLMError."""
    error_response = Mock(status_code=404, text="model not found")
    error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)
    post_mock.return_value = error_response

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    with pytest.raises(LLMError) as exc_info:
        provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert exc_info.value.code == "HTTP_ERROR"


@patch("requests.post")
def test_generate_raises_on_500(post_mock):
    """A 500 response raises LLMError."""
    error_response = Mock(status_code=500, text="internal error")
    error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=error_response)
    post_mock.return_value = error_response

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    with pytest.raises(LLMError) as exc_info:
        provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert exc_info.value.code == "HTTP_ERROR"


@patch("requests.post")
def test_generate_raises_on_malformed_json(post_mock):
    """Malformed JSON raises LLMError."""
    post_mock.return_value = Mock(
        status_code=200,
        text="not json",
        json=MagicMock(side_effect=json.JSONDecodeError("bad json", "not json", -1)),
    )

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    with pytest.raises(LLMError) as exc_info:
        provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert exc_info.value.code == "PARSE_ERROR"


@patch("requests.post")
def test_generate_raises_on_timeout(post_mock):
    """A request timeout raises LLMError."""
    post_mock.side_effect = requests.exceptions.Timeout("timed out")

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    with pytest.raises(LLMError) as exc_info:
        provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert exc_info.value.code == "TIMEOUT"


@patch("requests.post")
def test_generate_raises_on_connection_error(post_mock):
    """A connection error raises LLMError."""
    post_mock.side_effect = requests.exceptions.ConnectionError("refused")

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    with pytest.raises(LLMError) as exc_info:
        provider.generate([LLMMessage(role=MessageRole.USER, content="Hi")], model="model")
    assert exc_info.value.code == "CONNECTION_ERROR"


@patch("requests.get")
def test_is_available_false_on_500(get_mock):
    """is_available returns False on a non-200 status."""
    get_mock.return_value = Mock(status_code=500)

    provider = LlamaCppProvider("model", base_url=DEFAULT_BASE_URL)
    assert provider.is_available() is False
