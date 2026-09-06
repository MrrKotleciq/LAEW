"""Tests for LLM provider abstraction and Ollama implementation (ADR-001)."""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from laew.llm import (
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    OllamaProvider,
)
from laew.llm.base import MessageRole


class TestLLMBase:
    """Tests for LLM base classes."""

    def test_message_creation(self):
        """Test creating LLM messages."""
        msg = LLMMessage(role=MessageRole.USER, content="Hello")
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello"
        assert msg.to_dict() == {"role": "user", "content": "Hello"}

    def test_system_message(self):
        """Test system message creation."""
        msg = LLMMessage(role=MessageRole.SYSTEM, content="You are a helpful assistant")
        assert msg.role == MessageRole.SYSTEM
        assert msg.content == "You are a helpful assistant"

    def test_response_creation(self):
        """Test creating LLM response."""
        resp = LLMResponse(
            content="Generated answer",
            model="llama3.1",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            finish_reason="stop",
        )
        assert resp.content == "Generated answer"
        assert resp.model == "llama3.1"
        assert resp.total_tokens == 30
        assert resp.to_dict()["finish_reason"] == "stop"


class TestOllamaProvider:
    """Tests for Ollama provider."""

    @pytest.fixture
    def provider(self):
        """Create Ollama provider instance for testing."""
        return OllamaProvider(base_url="http://localhost:11434")

    @patch("requests.post")
    def test_generate_success(self, mock_post, provider):
        """Test successful text generation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "model": "llama3.1",
            "message": {
                "role": "assistant",
                "content": "This is a response from Ollama",
            },
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 15,
            "eval_count": 25,
        }
        mock_post.return_value = mock_response

        messages = [
            LLMMessage(role=MessageRole.SYSTEM, content="System prompt"),
            LLMMessage(role=MessageRole.USER, content="User question"),
        ]

        response = provider.generate(
            messages=messages,
            model="llama3.1",
            temperature=0.5,
        )

        assert response.content == "This is a response from Ollama"
        assert response.model == "llama3.1"
        assert response.prompt_tokens == 15
        assert response.completion_tokens == 25
        assert response.total_tokens == 40
        assert response.finish_reason == "stop"

        # Verify request payload
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/chat"
        payload = kwargs["json"]
        assert payload["model"] == "llama3.1"
        assert len(payload["messages"]) == 2
        assert payload["options"]["temperature"] == 0.5

    @patch("requests.post")
    def test_generate_connection_error(self, mock_post, provider):
        """Test error when Ollama is not reachable."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        messages = [LLMMessage(role=MessageRole.USER, content="Hello")]

        with pytest.raises(LLMError) as exc_info:
            provider.generate(messages=messages, model="llama3.1")

        assert "Failed to connect to Ollama" in str(exc_info.value)
        assert exc_info.value.code == "CONNECTION_ERROR"

    @patch("requests.post")
    def test_generate_timeout(self, mock_post, provider):
        """Test error when request times out."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        messages = [LLMMessage(role=MessageRole.USER, content="Hello")]

        with pytest.raises(LLMError) as exc_info:
            provider.generate(messages=messages, model="llama3.1")

        assert "timed out" in str(exc_info.value)
        assert exc_info.value.code == "TIMEOUT"

    @patch("requests.post")
    def test_generate_http_error(self, mock_post, provider):
        """Test error when Ollama returns an HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "model not found"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_post.return_value = mock_response

        messages = [LLMMessage(role=MessageRole.USER, content="Hello")]

        with pytest.raises(LLMError) as exc_info:
            provider.generate(messages=messages, model="nonexistent_model")

        assert "Ollama API error" in str(exc_info.value)
        assert exc_info.value.code == "HTTP_ERROR"

    @patch("requests.get")
    def test_list_models_success(self, mock_get, provider):
        """Test listing available models."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "models": [
                {"name": "llama3.1:latest", "size": 4700000000},
                {"name": "mistral:latest", "size": 4100000000},
                {"name": "nomic-embed-text:latest", "size": 274000000},
            ]
        }
        mock_get.return_value = mock_response

        models = provider.list_models()

        assert len(models) == 3
        assert "llama3.1:latest" in models
        assert "mistral:latest" in models
        assert "nomic-embed-text:latest" in models

    @patch("requests.get")
    def test_is_available_true(self, mock_get, provider):
        """Test availability check when Ollama is running."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        assert provider.is_available() is True

    @patch("requests.get")
    def test_is_available_false(self, mock_get, provider):
        """Test availability check when Ollama is unreachable."""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        assert provider.is_available() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
