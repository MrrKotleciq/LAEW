"""Ollama LLM provider implementation."""

import json
from typing import Optional

import requests

from laew.llm.base import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    MessageRole,
)


class OllamaProvider(LLMProvider):
    """
    Ollama local LLM provider.

    Connects to Ollama API for local model inference.
    Default endpoint: http://localhost:11434

    Ollama API documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama provider.

        Args:
            base_url: Ollama API base URL
        """
        self.base_url = base_url.rstrip("/")
        self._timeout = 120  # seconds

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
        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
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
