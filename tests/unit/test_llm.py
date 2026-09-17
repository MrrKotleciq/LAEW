"""Tests for LLM provider abstraction and Ollama implementation (ADR-001)."""

import json
from io import BytesIO
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


class TestOllamaStreaming:
    """Tests for Ollama streaming and tokenization endpoints."""

    @pytest.fixture
    def provider(self):
        """Create Ollama provider instance for testing."""
        return OllamaProvider(base_url="http://localhost:11434")

    @patch("requests.post")
    def test_tokenize_count_success(self, mock_post, provider):
        """Successful tokenize request returns exact count."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"count": 7}
        mock_post.return_value = mock_response

        count = provider.tokenize_count("hello world", "llama3.1")
        assert count == 7

        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://localhost:11434/api/tokenize"
        payload = kwargs["json"]
        assert payload["model"] == "llama3.1"
        assert payload["prompt"] == "hello world"

    @patch("requests.post")
    def test_tokenize_count_error(self, mock_post, provider):
        """Tokenize errors map to LLMError with proper codes."""
        mock_post.side_effect = requests.exceptions.ConnectionError("boom")
        with pytest.raises(LLMError) as exc_info:
            provider.tokenize_count("hi", "llama3.1")
        assert exc_info.value.code == "CONNECTION_ERROR"

    @patch("requests.post")
    def test_calibrate_with_ollama(self, mock_post, provider):
        """calibrate_with_ollama returns TokenCalibrator with recorded samples."""
        # Mock responses for four probe texts
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {"count": 2},   # "def helper():\n    return 42\n" -> len 24, 2 tokens -> ratio 12
            {"count": 4},   # short probe
            {"count": 8},   # medium probe
            {"count": 16},  # long probe
        ]
        mock_post.return_value = mock_response

        calibrator = provider.calibrate_with_ollama("llama3.1")
        assert calibrator.sample_count == 4
        # best_chars_per_token() is mean of ratios; we can't assert exact because
        # probe lengths vary, but it should be positive and sane
        ratio = calibrator.best_chars_per_token()
        assert ratio > 0

    @patch("requests.post")
    def test_generate_stream_yields_chunks_and_sets_last_response(self, mock_post, provider):
        """Streaming yields chunks and sets _last_stream_response with final counts."""
        # Simulate NDJSON stream: three content chunks then done
        stream_lines = [
            b'{"message": {"content": "Hello"}, "done": false}\n',
            b'{"message": {"content": " "}, "done": false}\n',
            b'{"message": {"content": "world!"}, "done": false}\n',
            b'{"message": {}, "done": true, "prompt_eval_count": 5, "eval_count": 3, "done_reason": "stop"}\n',
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        # make iter_lines return the lines
        mock_response.iter_lines.return_value = stream_lines
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        messages = [LLMMessage(role=MessageRole.USER, content="Say hi")]
        chunks = list(provider.generate_stream(messages, "llama3.1"))
        assert chunks == ["Hello", " ", "world!"]

        # final aggregated response should be stored
        last = provider._last_stream_response
        assert last is not None
        assert last.content == ""  # content is empty; we don't reassemble
        assert last.model == "llama3.1"
        assert last.prompt_tokens == 5
        assert last.completion_tokens == 3
        assert last.total_tokens == 8
        assert last.finish_reason == "stop"

    @patch("requests.post")
    def test_generate_stream_connection_error_midstream_raises(self, mock_post, provider):
        """ConnectionError mid-stream maps to LLMError STREAM_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        def iter_lines(decode_unicode=False):
            """Yield one content frame, then die mid-stream."""
            yield b'{"message": {"content": "ok"}, "done": false}\n'
            raise requests.exceptions.ConnectionError("died")

        mock_response.iter_lines = iter_lines
        mock_post.return_value = mock_response

        with pytest.raises(LLMError) as exc_info:
            list(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="hi")], "llama3.1"))
        assert exc_info.value.code == "STREAM_ERROR"
        assert "Stream interrupted" in str(exc_info.value)

    @patch("requests.post")
    def test_generate_stream_request_exception_midstream_raises(self, mock_post, provider):
        """RequestException mid-stream maps to LLMError STREAM_ERROR."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        def iter_lines(decode_unicode=False):
            """Yield one content frame, then die mid-stream."""
            yield b'{"message": {"content": "ok"}, "done": false}\n'
            raise requests.exceptions.RequestException("timeout")

        mock_response.iter_lines = iter_lines
        mock_post.return_value = mock_response

        with pytest.raises(LLMError) as exc_info:
            list(provider.generate_stream([LLMMessage(role=MessageRole.USER, content="hi")], "llama3.1"))
        assert exc_info.value.code == "STREAM_ERROR"
        assert "Stream request failed" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
