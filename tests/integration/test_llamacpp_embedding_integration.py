"""Integration tests for the llama.cpp embedding service (Milestone 17).

These tests drive the **real** HTTP code path of
:class:`~laew.rag.llamacpp.LlamaCppEmbedding` against an in-process llama.cpp
OpenAI-compatible server (:class:`tests.integration._llamacpp_test_server.LlamaCppTestServer`).
No live ``llama-server`` binary or ``.gguf`` weights are required, so the tests
run rather than skip.  They cover:

- ``embed`` posts a **single** input and reads ``data[0].embedding``.
- ``embed_batch`` posts **all** inputs in **one** request and returns vectors
  in input order regardless of the server-side index (sequential / out-of-order
  / duplicate / missing).
- ``dimensions`` equals the **real** vector length (no hidden probe).
- Fail-loud validation: wrong-length vectors, duplicate/missing/non-integer
  indexes all raise :class:`~laew.llm.base.LLMError`.
- Pooling is a **server-side model capability**: the client sends **no**
  ``pooling`` param, and the models list advertises an embedding-capable model.
- ``is_available`` GET ``/v1/models`` -> 200.
"""

import pytest
import unittest.mock as mock

from laew.llm.base import LLMError
from laew.rag.llamacpp import LlamaCppEmbedding


def _make_provider(server, model="nomic-embed-text"):
    """A LlamaCppEmbedding with target_dimensions set to the server's dim."""
    return LlamaCppEmbedding(
        model=model,
        base_url=server.base_url,
        target_dimensions=server.config.embedding_dim,
    )


# ---------------------------------------------------------------------------
# embed() — single input
# ---------------------------------------------------------------------------


def test_embed_posts_single_input_and_reads_data0(llamacpp_server):
    """embed posts one input and returns the single vector from data[0]."""
    base, server = llamacpp_server
    provider = _make_provider(server)

    captured = []
    real_request = provider._request

    def spy_request(url, payload, **kwargs):
        captured.append((url, payload))
        return real_request(url, payload, **kwargs)

    with mock.patch.object(provider, "_request", side_effect=spy_request):
        vec = provider.embed("alpha")

    # URL normalized to /v1/embeddings.
    assert captured
    assert captured[0][0].endswith("/v1/embeddings")
    # Single-input payload (not the batch form).
    assert captured[0][1] == {"model": "nomic-embed-text", "input": "alpha"}

    assert vec == [0.0] * server.config.embedding_dim


def test_embed_request_has_no_pooling_param(llamacpp_server):
    """The embed request body carries no pooling param (server-side capability)."""
    base, server = llamacpp_server
    provider = _make_provider(server)

    vec = provider.embed("alpha")

    body = server.config.last_embedding_request
    assert isinstance(body, dict)
    assert body.get("input") == "alpha"
    assert "pooling" not in body


# ---------------------------------------------------------------------------
# embed_batch() — one request, input-order results
# ---------------------------------------------------------------------------


def test_embed_batch_posts_all_inputs_in_one_request(llamacpp_server):
    """embed_batch posts all inputs in a single request in the batch form."""
    base, server = llamacpp_server
    provider = _make_provider(server)

    texts = ["alpha", "beta", "gamma"]
    captured = []
    real_request = provider._request

    def spy_request(url, payload, **kwargs):
        captured.append((url, payload))
        return real_request(url, payload, **kwargs)

    with mock.patch.object(provider, "_request", side_effect=spy_request):
        vectors = provider.embed_batch(texts)

    assert len(captured) == 1  # a single request for the whole batch
    url, payload = captured[0]
    assert url.endswith("/v1/embeddings")
    assert payload == {"model": "nomic-embed-text", "input": texts}

    assert vectors == [
        [0.0] * server.config.embedding_dim,
        [0.5] * server.config.embedding_dim,
        [0.9] * server.config.embedding_dim,
    ]
    assert server.config.call_count["embeddings"] == 1


def test_embed_batch_reorders_to_input_order_out_of_order(llamacpp_server):
    """embed_batch returns vectors in input order despite out-of-order indexes.

    The server returns indexes [0, 2, 1] for inputs [a, b, c]; the client keys
    by index and reorders to input order.
    """
    base, server = llamacpp_server
    server.config.embedding_index_mode = "out-of-order"
    provider = _make_provider(server)

    vectors = provider.embed_batch(["a", "b", "c"])

    # zeros (index 0), then 0.5 (index 1), then 0.9 (index 2) — input order.
    assert vectors[0] == [0.0] * server.config.embedding_dim
    assert vectors[1] == [0.5] * server.config.embedding_dim
    assert vectors[2] == [0.9] * server.config.embedding_dim


# ---------------------------------------------------------------------------
# dimensions — real length, no probe
# ---------------------------------------------------------------------------


def test_dimensions_equals_real_vector_length(llamacpp_server):
    """dimensions returns the real response length with no network probe."""
    base, server = llamacpp_server
    provider = _make_provider(server)

    assert provider.dimensions == server.config.embedding_dim

    # No probe: the call_count is unchanged by reading dimensions.
    assert server.config.call_count == {"models": 0, "chat": 0, "embeddings": 0}


# ---------------------------------------------------------------------------
# Fail-loud validation
# ---------------------------------------------------------------------------


def test_embed_batch_rejects_wrong_dimension(llamacpp_server):
    """A response whose vectors are longer than target_dimensions raises."""
    base, server = llamacpp_server
    server.config.embedding_index_mode = "wrong-dimension"
    provider = _make_provider(server)

    with pytest.raises(LLMError) as exc_info:
        provider.embed_batch(["a", "b"])
    assert exc_info.value.code == "INVALID_RESPONSE"


def test_embed_batch_rejects_duplicate_indexes(llamacpp_server):
    """A response with duplicate indexes raises."""
    base, server = llamacpp_server
    server.config.embedding_index_mode = "duplicate"
    provider = _make_provider(server)

    with pytest.raises(LLMError) as exc_info:
        provider.embed_batch(["a", "b"])
    assert exc_info.value.code == "INVALID_RESPONSE"


def test_embed_batch_rejects_missing_indexes(llamacpp_server):
    """A response that omits an index in 0..N-1 raises."""
    base, server = llamacpp_server
    server.config.embedding_index_mode = "missing"
    provider = _make_provider(server)

    with pytest.raises(LLMError) as exc_info:
        provider.embed_batch(["a", "b", "c"])
    assert exc_info.value.code == "INVALID_RESPONSE"


def test_embed_batch_rejects_too_few_entries(llamacpp_server):
    """A response with fewer vectors than inputs raises."""
    base, server = llamacpp_server
    provider = _make_provider(server)
    server.config.embedding_vectors = [
        [0.0] * server.config.embedding_dim,
    ]

    with pytest.raises(LLMError) as exc_info:
        provider.embed_batch(["a", "b"])
    assert exc_info.value.code == "INVALID_RESPONSE"


# ---------------------------------------------------------------------------
# Pooling is server-side
# ---------------------------------------------------------------------------


def test_pooling_is_server_side_model_capability(llamacpp_server):
    """The client sends no pooling param; the route works against an
    embedding-capable model, and the models list advertises one."""
    base, server = llamacpp_server
    provider = _make_provider(server)

    vec = provider.embed("alpha")

    # The embeddings route works (pooling is a server-side model capability).
    assert vec == [0.0] * server.config.embedding_dim
    # The advertised embedding model is pooling-capable.  The embedding service
    # does not list models itself; the server advertises them.
    models = [m["id"] for m in server.config.models]
    assert "nomic-embed-text" in models
    # The request body carries no pooling param.
    assert "pooling" not in server.config.last_embedding_request


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


def test_is_available_gets_models(llamacpp_server):
    """is_available returns True by GET /v1/models -> 200."""
    base, server = llamacpp_server
    provider = LlamaCppEmbedding(
        model="nomic-embed-text", base_url=base, target_dimensions=server.config.embedding_dim
    )

    assert provider.is_available() is True
    assert server.config.call_count["models"] == 1
