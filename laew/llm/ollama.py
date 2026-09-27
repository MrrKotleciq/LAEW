"""Ollama LLM provider implementation."""

import json
from typing import Iterator, Optional

import requests

from laew.llm.base import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)
from laew.prompts.context_budget import TokenCalibrator


class OllamaProvider(LLMProvider):
    """
    Ollama local LLM provider.

    Connects to Ollama API for local model inference.
    Default endpoint: http://localhost:11434

    Ollama API documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: int = 120):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL
            timeout: HTTP request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout  # seconds
        # Carries the final LLMResponse after a streaming call completes.
        self._last_stream_response: Optional[LLMResponse] = None

    def generate(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop: Optional[list[str]] = None,
    ) -> LLMResponse:
        """
        Generate completion using Ollama chat API.

        Args:
            messages: Conversation history
            model: Ollama model name (e.g., 'llama3.1', 'mistral')
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated content

        Raises:
            LLMError: If generation fails
        """
        url = f"{self.base_url}/api/chat"

        # Convert messages to Ollama format
        ollama_messages = [msg.to_dict() for msg in messages]

        # Build request payload
        options: Dict[str, Any] = {
            "temperature": temperature,
        }
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if stop is not None:
            options["stop"] = stop

        payload: dict[str, Any] = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": options,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to Ollama at {self.base_url}. Is Ollama running?",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"Ollama request timed out after {self._timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse Ollama response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        # Extract response content
        if "message" not in data or "content" not in data["message"]:
            raise LLMError(
                f"Unexpected Ollama response format: {data}",
                code="INVALID_RESPONSE",
            )

        content = data["message"]["content"]

        # Extract token counts if available
        prompt_tokens = data.get("prompt_eval_count")
        completion_tokens = data.get("eval_count")
        total_tokens = None
        if prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        # Extract finish reason
        finish_reason = "stop"  # Ollama doesn't always provide this
        if data.get("done_reason"):
            finish_reason = data["done_reason"]

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
    ) -> Iterator[str]:
        """
        Stream a completion as content chunks via Ollama's NDJSON streaming.

        Posts to ``/api/chat`` with ``stream: True`` and yields each
        ``data["message"]["content"]`` chunk as it arrives.  The final ``done``
        frame carries the complete token counts; callers who need the
        ``LLMResponse`` (e.g. for token accounting) may use
        ``generate()`` or read the accumulated attributes set on
        ``self._last_stream_response`` after iteration completes.

        Args:
            messages: Conversation history
            model: Ollama model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Yields:
            str: Incremental content chunks

        Raises:
            LLMError: If the request fails or the stream is interrupted
        """
        url = f"{self.base_url}/api/chat"
        ollama_messages = [msg.to_dict() for msg in messages]

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if stop is not None:
            payload["options"]["stop"] = stop

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self._timeout,
                stream=True,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to Ollama at {self.base_url}. Is Ollama running?",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"Ollama request timed out after {self._timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        # Accumulate token counts from the stream; exposed via
        # ``self._last_stream_response`` after the generator is consumed.
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        done_reason: str = "stop"

        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                try:
                    frame = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                message = frame.get("message", {})
                content = message.get("content")
                if content:
                    yield content

                if frame.get("done"):
                    prompt_tokens = frame.get("prompt_eval_count")
                    completion_tokens = frame.get("eval_count")
                    if frame.get("done_reason"):
                        done_reason = frame["done_reason"]
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Stream interrupted: {str(e)}",
                code="STREAM_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Stream request failed: {str(e)}",
                code="STREAM_ERROR",
            ) from e
        finally:
            response.close()

        # Attach the final LLMResponse so callers can read token counts
        # without requiring a separate generate() call.
        self._last_stream_response = LLMResponse(
            content="",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(
                (prompt_tokens + completion_tokens)
                if prompt_tokens is not None and completion_tokens is not None
                else None
            ),
            finish_reason=done_reason,
        )

    def list_models(self) -> list[str]:
        """
        List available Ollama models.

        Returns:
            List of model names

        Raises:
            LLMError: If listing fails
        """
        url = f"{self.base_url}/api/tags"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to Ollama at {self.base_url}",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"Ollama API error: {e.response.status_code}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                "Failed to parse Ollama models response",
                code="PARSE_ERROR",
            ) from e

        if "models" not in data:
            raise LLMError(
                f"Unexpected Ollama response format: {data}",
                code="INVALID_RESPONSE",
            )

        # Extract model names
        models = []
        for model_info in data["models"]:
            if "name" in model_info:
                models.append(model_info["name"])

        return models

    def is_available(self) -> bool:
        """
        Check if Ollama is available.

        Returns:
            True if Ollama is reachable and healthy
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5,
            )
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def pull_model(self, model: str) -> None:
        """
        Pull a model from Ollama library.

        Args:
            model: Model name to pull

        Raises:
            LLMError: If pull fails
        """
        url = f"{self.base_url}/api/pull"

        payload = {
            "name": model,
            "stream": False,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=600,  # Model pulls can take a while
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to Ollama at {self.base_url}",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                "Model pull timed out",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

    def tokenize_count(self, text: str, model: str) -> int:
        """
        Ask Ollama to tokenize a string and report the exact token count.

        Uses the ``/api/tokenize`` endpoint (a lightweight, deterministic
        operation — no generation).  Returns the tokenizer's exact ``count``.

        Args:
            text: Text to tokenize
            model: Ollama model name whose tokenizer should be used

        Returns:
            Exact token count for ``text``

        Raises:
            LLMError: If the request fails
        """
        url = f"{self.base_url}/api/tokenize"
        payload = {"model": model, "prompt": text}

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to Ollama at {self.base_url}. Is Ollama running?",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"Ollama request timed out after {self._timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"Ollama API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"Request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse Ollama response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        count = data.get("count")
        if count is None:
            raise LLMError(
                f"Unexpected Ollama tokenize response format: {data}",
                code="INVALID_RESPONSE",
            )
        return int(count)

    def calibrate_with_ollama(
        self,
        model: str,
        probe_texts: Optional[list[str]] = None,
    ) -> TokenCalibrator:
        """
        Calibrate the characters-per-token ratio against a real Ollama tokenizer.

        Tokenizes each probe text via ``/api/tokenize``, records the observed
        (char_count, actual_tokens) pairs in a fresh :class:`TokenCalibrator`,
        and returns it.  The calibrated ratio feeds ``TokenEstimator`` for
        budget enforcement (stream B of Milestone 14).

        Offline note: this performs a network request and raises ``LLMError``
        when Ollama is unreachable — callers (e.g. the console "budget"
        handler) should gate on ``is_available()`` first so the feature works
        offline, matching the console's offline-first convention.

        Args:
            model: Ollama model name whose tokenizer to calibrate against
            probe_texts: Strings of increasing length; defaults to a standard
                code-heavy English probe corpus sized to approximate LAEW
                prompt mixes (short code lines + long prose).

        Returns:
            A ``TokenCalibrator`` populated with one sample per probe.

        Raises:
            LLMError: If tokenization of any probe text fails
        """
        if probe_texts is None:
            probe_texts = [
                "def helper():\n    return 42\n",
                "LAEW is a local-first AI Engineering Workspace.",
                (
                    "The agent executor orchestrates a Thought -> Action -> "
                    "Observation -> Response loop, parsing tool calls from "
                    "fenced JSON blocks and feeding malformed attempts back to "
                    "the model for correction before forcing a final answer."
                ),
                (
                    "Context budgeting allocates system, conversation, rag, and "
                    "tools segments against a fixed total. Token estimation "
                    "divides character count by a calibrated characters-per-token "
                    "ratio to keep every request within the configured window "
                    "without truncation or provisioning failures."
                ),
            ]

        calibrator = TokenCalibrator()
        for probe in probe_texts:
            actual = self.tokenize_count(probe, model)
            calibrator.record(len(probe), actual)
        return calibrator
