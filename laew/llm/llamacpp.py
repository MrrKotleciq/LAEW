"""
llama.cpp LLM provider (OpenAI-compatible chat adapter).

Implements :class:`~laew.llm.base.LLMProvider` against a llama.cpp server
exposing its OpenAI-compatible routes (``/v1/chat/completions``,
``/v1/models``).  llama.cpp is an explicit, self-contained server with no
Ollama registry; the provider receives a concrete llama.cpp server ID and
talks to it directly.

Design notes
------------
- Base URLs are normalized with :func:`laew.llm.base.normalize_llamacpp_base_url`
  so inputs with or without a trailing ``/v1`` resolve identically.
- The request payload uses **top-level** OpenAI-compatible parameters
  (``model``, ``messages``, ``temperature``, ``max_tokens``, ``stop``).
- LAEW's tool-calling protocol is **text-based**: the executor parses a fenced
  ``tool_call`` JSON block emitted in the response text.  This provider does
  **not** send native OpenAI ``tools``/``tool_choice`` — native tool calling is
  out of scope and would break LAEW's existing format.
"""

import json
from typing import Iterator, Optional

import requests

from laew.llm.base import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
    normalize_llamacpp_base_url,
)


class LlamaCppProvider(LLMProvider):
    """
    llama.cpp OpenAI-compatible chat provider.

    Talks to a llama.cpp server's OpenAI-compatible routes.  The server runs
    as ``llama-server -m <server-id> --host --port`` (default port 8080).

    Args:
        model: Explicit llama.cpp server model ID (a ``.gguf`` server model),
            not an Ollama tag.
        base_url: llama.cpp base URL.  Normalized to end in ``/v1``.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8080",
        timeout: int = 30,
        stream_timeout: int = 120,
    ):
        """
        Initialize the llama.cpp provider.

        Args:
            model: Explicit llama.cpp server model ID.
            base_url: llama.cpp base URL (normalized to end in ``/v1``).
            timeout: HTTP request timeout in seconds.
        """
        self.model = model
        self.base_url = normalize_llamacpp_base_url(base_url)
        self._timeout = timeout
        # Streaming allows longer idle generation phases while bounding an
        # actually stalled server. Ordinary requests retain the shorter limit.
        self._stream_timeout = stream_timeout
        # Carries the normalized final stream response for token accounting,
        # matching the contract exposed by OllamaProvider.
        self._last_stream_response: Optional[LLMResponse] = None

    def _build_payload(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        stop: Optional[list[str]],
    ) -> dict:
        """
        Build the OpenAI-compatible chat payload.

        Args:
            messages: Conversation history
            model: Model/server ID
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            Request body as a dictionary.

        Notes:
            Parameters are top-level (not nested under ``options``).  No
            ``tools``/``tool_choice`` keys are added — LAEW uses its own
            text-based tool-call protocol.
        """
        payload: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stop is not None:
            payload["stop"] = stop
        return payload

    def _request(
        self,
        url: str,
        payload: dict,
        *,
        method: str = "post",
        timeout: Optional[int | tuple[int, int]] = None,
        stream: bool = False,
    ) -> requests.Response:
        """
        Perform a llama.cpp HTTP request with error handling.

        Args:
            url: Absolute request URL
            payload: JSON request body
            method: HTTP verb (``post`` or ``get``)
            timeout: Timeout in seconds (defaults to the provider timeout)
            stream: Whether to stream the response body

        Raises:
            LLMError: If the request fails
        """
        http_method = getattr(requests, method)
        try:
            response = http_method(
                url,
                json=payload,
                timeout=timeout if timeout is not None else self._timeout,
                stream=method == "post" and stream,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to llama.cpp at {self.base_url}",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"llama.cpp request timed out after {self._timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"llama.cpp API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"llama.cpp request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e
        return response

    def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> LLMResponse:
        """
        Generate a completion via llama.cpp's ``/v1/chat/completions``.

        Args:
            messages: Conversation history
            model: llama.cpp server model ID
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content and metadata.

        Raises:
            LLMError: If generation fails
        """
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(
            messages, model, temperature, max_tokens, stop
        )

        response = self._request(url, payload)

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse llama.cpp response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        if (
            not isinstance(data, dict)
            or "choices" not in data
            or not data["choices"]
            or "message" not in data["choices"][0]
        ):
            raise LLMError(
                f"Unexpected llama.cpp response format: {data}",
                code="INVALID_RESPONSE",
            )

        content = data["choices"][0]["message"].get("content", "")

        usage = data.get("usage")
        prompt_tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        total_tokens = usage.get("total_tokens") if isinstance(usage, dict) else None

        finish_reason = data["choices"][0].get("finish_reason")

        return LLMResponse(
            content=content,
            model=data.get("model", model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
        )

    def generate_stream(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> Iterator[dict]:
        """
        Stream a completion via llama.cpp SSE (``/v1/chat/completions``).

        Yields each content delta as it arrives.  The stream terminates on the
        ``[DONE]`` terminator and stores a normalized :class:`LLMResponse` on
        ``_last_stream_response`` for token accounting, matching the shared
        provider contract used by the executor.

        Args:
            messages: Conversation history
            model: llama.cpp server model ID
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Yields:
            str: Incremental content chunks.

        Raises:
            LLMError: If the request fails or the stream is interrupted
        """
        url = f"{self.base_url}/chat/completions"
        payload = self._build_payload(
            messages, model, temperature, max_tokens, stop
        )
        # Signal the server to stream SSE frames (like Ollama's /api/chat does
        # explicitly). The llama.cpp server branches on the payload flag, not
        # the requests kwarg, so without this it requests JSON and the SSE
        # parser finds nothing.
        payload["stream"] = True

        response = self._request(
            url, payload, timeout=(self._timeout, self._stream_timeout), stream=True
        )

        self._last_stream_response = None
        last_usage: Optional[dict] = None
        finish_reason: Optional[str] = "stop"
        completed = False
        try:
            for raw_line in response.iter_lines(decode_unicode=False):
                if raw_line is None:
                    continue
                # SSE is UTF-8. Requests may otherwise infer ISO-8859-1 for
                # text/event-stream without a charset. iter_lines assembles
                # byte fragments into complete lines before decoding.
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8")
                stripped = raw_line.strip()
                if stripped == "[DONE]":
                    completed = True
                    break
                if not stripped or not stripped.startswith("data:"):
                    continue
                payload_line = stripped[len("data:"):].strip()
                if payload_line == "[DONE]":
                    completed = True
                    break
                try:
                    data = json.loads(payload_line)
                except json.JSONDecodeError:
                    continue
                choice = (data.get("choices", [{}])[0] or {})
                delta = choice.get("delta", {})
                # Yield only non-empty content deltas, matching the Ollama
                # provider.  Empty deltas (``{"delta": {}}`` or a zero-length
                # ``content``) carry nothing and are skipped.
                if delta.get("content"):
                    yield delta["content"]
                if choice.get("finish_reason") is not None:
                    finish_reason = choice["finish_reason"]
                    completed = True
                usage = data.get("usage")
                if isinstance(usage, dict):
                    last_usage = usage
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Stream interrupted: {str(e)}",
                code="STREAM_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"llama.cpp stream produced no data for {self._stream_timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Stream request failed: {str(e)}",
                code="STREAM_ERROR",
            ) from e
        finally:
            response.close()

        if not completed:
            raise LLMError("llama.cpp stream ended before completion; retry the request.", code="STREAM_ERROR")

        self._last_stream_response = LLMResponse(
            content="",
            model=model,
            prompt_tokens=(last_usage or {}).get("prompt_tokens"),
            completion_tokens=(last_usage or {}).get("completion_tokens"),
            total_tokens=(last_usage or {}).get("total_tokens"),
            finish_reason=finish_reason,
        )

    def list_models(self) -> list[str]:
        """
        List available llama.cpp server models.

        Returns:
            List of model IDs

        Raises:
            LLMError: If listing fails
        """
        url = f"{self.base_url}/models"

        response = self._request(url, {}, method="get", timeout=10)

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse llama.cpp models response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        if not isinstance(data, dict) or not isinstance(data.get("data"), list):
            raise LLMError(
                f"Unexpected llama.cpp models response format: {data}",
                code="INVALID_RESPONSE",
            )

        models = []
        for model_info in data["data"]:
            if isinstance(model_info, dict) and model_info.get("id"):
                models.append(model_info["id"])

        return models

    def is_available(self) -> bool:
        """
        Check if the llama.cpp server is available and healthy.

        Returns:
            True if the server responds with a 200 on ``/v1/models``
        """
        try:
            response = requests.get(
                f"{self.base_url}/models",
                timeout=5,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
