"""Live Ollama API checks, skipped only when the configured service is offline."""

import os

import pytest

from laew.llm.ollama import OllamaProvider


@pytest.mark.integration
@pytest.mark.ollama
def test_live_ollama_model_list():
    """Exercise Ollama's actual /api/tags endpoint when the service is healthy."""
    base_url = os.environ.get("LAEW_OLLAMA_BASE_URL", "http://localhost:11434")
    provider = OllamaProvider(base_url=base_url, timeout=5)
    if not provider.is_available():
        pytest.skip(f"Ollama is unavailable at {base_url}/api/tags")

    # list_models performs a second real API request and validates the response
    # schema; an empty model inventory is still a healthy Ollama service.
    models = provider.list_models()
    assert isinstance(models, list)
    assert all(isinstance(model, str) for model in models)
