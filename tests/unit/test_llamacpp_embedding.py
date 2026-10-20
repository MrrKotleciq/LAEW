"""Unit tests for the llama.cpp embedding adapter.

These tests mock the HTTP layer (``requests``) so no llama.cpp server is
required.  They cover:

- Base URL normalization (with and without a trailing ``/v1``).
- Single embed: posts one input, reads ``data[0].embedding``.
- Batch embed: posts all inputs in **one** request and returns vectors in
  input order, regardless of server-side index order.
- Response validation: one vector per input, unique+complete ``0..N-1``
  indexes, and ``target_dimensions`` length — any violation raises
  :class:`~laew.llm.base.LLMError`.
- Dimension mismatch raises on the first real request; no hidden probe.
- ``dimensions`` returns ``target_dimensions`` with no network probe; the
  ``eager`` variant discovers dimensions from the first real request.
- Model-listing availability, HTTP errors and timeouts -> ``LLMError``.
- The ``build_llamacpp_embedding`` factory and construction guards.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

import requests

from laew.llm.base import LLMError
from laew.llm.llamacpp import LlamaCppProvider  # noqa: F41B — same module, chat-only
from laew.rag.llamacpp import LlamaCppEmbedding, build_llamacpp_embedding

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DIM = 768


def _embeddings_response(vectors: list[list[float]], *, indices=None) -> dict:
    """Build an OpenAI-style embeddings payload, optionally reordering by index."""
    if indices is None:
        indices = list(range(len(vectors)))
    return {
        "object": "list",
        "data": [
            {"index": i, "embedding": vec, "object": "embedding"}
            for i, vec in zip(indices, vectors)
        ],
    }


def _vector(dim: int, value: float = 1.0) -> list[float]:
    return [value] * dim


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_build_llamacpp_embedding_factory():
    """build_llamacpp_embedding produces a LlamaCppEmbedding with normalized URL."""
    service = build_llamacpp_embedding(
        model="nomic-embed-text",
        base_url="http://localhost:9931",
        target_dimensions=DIM,
    )
    assert isinstance(service, LlamaCppEmbedding)
    assert service.model == "nomic-embed-text"
    assert service.base_url == "http://localhost:9931/v1"
    assert service.target_dimensions == DIM


def test_build_llamacpp_embedding_default_base_url():
    """The factory defaults to the llama.cpp OpenAI-compatible address."""
    service = build_llamacpp_embedding(
        model="nomic-embed-text",
        target_dimensions=DIM,
    )
    assert service.base_url == f"{DEFAULT_BASE_URL}/v1"


def test_requires_target_dimensions_or_eager():
    """Construction without target_dimensions or eager=True raises LLMError."""
    with pytest.raises(LLMError) as exc_info:
        LlamaCppEmbedding(model="m", target_dimensions=None)
    assert exc_info.value.code == "MISSING_DIMENSIONS"


def test_eager_allows_missing_dimensions():
    """eager=True constructs without target_dimensions (dimensions discovered lazily)."""
    service = LlamaCppEmbedding(model="m", target_dimensions=None, eager=True)
    assert service.target_dimensions is None
    assert service.eager is True


# ---------------------------------------------------------------------------
# Base URL normalization
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_embed_normalizes_base_url_without_v1(post_mock):
    """embed resolves identically for a base URL without a trailing /v1."""
    payload = _embeddings_response([_vector(DIM)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    LlamaCppEmbedding("m", base_url=DEFAULT_BASE_URL, target_dimensions=DIM).embed(
        "hello"
    )

    assert post_mock.call_args.args[0] == f"{DEFAULT_BASE_URL}/v1/embeddings"


@patch("requests.post")
def test_embed_normalizes_base_url_with_v1(post_mock):
    """embed resolves identically for a base URL already ending in /v1."""
    payload = _embeddings_response([_vector(DIM)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    LlamaCppEmbedding(
        "m", base_url=f"{DEFAULT_BASE_URL}/v1", target_dimensions=DIM
    ).embed("hello")

    assert post_mock.call_args.args[0] == f"{DEFAULT_BASE_URL}/v1/embeddings"


# ---------------------------------------------------------------------------
# Single embed
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_embed_posts_single_input_and_reads_embedding(post_mock):
    """embed posts a single input and returns the one entry's embedding."""
    payload = _embeddings_response([_vector(DIM)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    vec = service.embed("hello world")

    body = post_mock.call_args.kwargs["json"]
    assert body == {"model": "m", "input": "hello world"}
    assert vec == [1.0] * DIM


@patch("requests.post")
def test_embed_reads_data_index_embedding(post_mock):
    """embed reads each entry's 'embedding' field (not 'data.embedding')."""
    payload = _embeddings_response([_vector(DIM)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    service.embed("x")

    body = post_mock.call_args.kwargs["json"]
    assert body == {"model": "m", "input": "x"}


# ---------------------------------------------------------------------------
# Batch embed
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_embed_batch_posts_all_inputs_in_one_request(post_mock):
    """embed_batch posts all inputs in a single request (OpenAI batch form)."""
    payload = _embeddings_response([_vector(DIM) for _ in range(3)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    service.embed_batch(["one", "two", "three"])

    body = post_mock.call_args.kwargs["json"]
    assert body["input"] == ["one", "two", "three"]
    # A single request, not one per text.
    assert post_mock.call_count == 1


@patch("requests.post")
def test_embed_batch_returns_vectors_in_input_order(post_mock):
    """embed_batch returns vectors in input order regardless of server index."""
    # Server returns them out of input order (indexes 0, 2, 1), embeddings
    # 0.0, 0.9, 0.5 respectively.  The result must be ordered by input index:
    # a->index 0->0.0, b->index 1->0.5, c->index 2->0.9.
    vectors = [_vector(DIM, 0.0), _vector(DIM, 0.9), _vector(DIM, 0.5)]
    payload = _embeddings_response(vectors, indices=[0, 2, 1])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    result = service.embed_batch(["a", "b", "c"])

    # Reordered to input order: a->index 0->0.0, b->index 1->0.5, c->index 2->0.9
    assert result[0] == [0.0] * DIM
    assert result[1] == [0.5] * DIM
    assert result[2] == [0.9] * DIM


@patch("requests.post")
def test_embed_batch_reorders_when_indexes_out_of_order(post_mock):
    """embed_batch reorders by the reported index, not server response order."""
    # Server returns them out of input order (indexes 2, 1, 0).
    payload = _embeddings_response(
        [_vector(DIM, 3.0), _vector(DIM, 2.0), _vector(DIM, 1.0)],
        indices=[2, 1, 0],
    )
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    result = service.embed_batch(["first", "second", "third"])

    # Server returned [3.0, 2.0, 1.0] (by index 2, 1, 0) but the result is
    # ordered by input index: first->0->1.0, second->1->2.0, third->2->3.0.
    assert result[0] == [1.0] * DIM
    assert result[1] == [2.0] * DIM
    assert result[2] == [3.0] * DIM


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_embed_batch_rejects_wrong_vector_count(post_mock):
    """embed_batch with len(data) != len(texts) raises LLMError."""
    payload = _embeddings_response([_vector(DIM), _vector(DIM)])  # 2 for 3 inputs
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a", "b", "c"])
    assert exc_info.value.code == "INVALID_RESPONSE"


@patch("requests.post")
def test_embed_batch_rejects_missing_index(post_mock):
    """A batch response missing an index for an input raises LLMError."""
    payload = _embeddings_response([_vector(DIM), _vector(DIM)])  # missing index 2
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a", "b", "c"])
    assert exc_info.value.code == "INVALID_RESPONSE"


@patch("requests.post")
def test_embed_batch_rejects_duplicate_index(post_mock):
    """A batch response with a duplicate index raises LLMError."""
    payload = _embeddings_response(
        [_vector(DIM), _vector(DIM)],
        indices=[0, 0],  # duplicate
    )
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a", "b"])
    assert exc_info.value.code == "INVALID_RESPONSE"


@patch("requests.post")
def test_embed_batch_rejects_non_integer_index(post_mock):
    """A non-integer index (e.g. a float) raises LLMError."""
    payload = {
        "object": "list",
        "data": [{"index": 1.0, "embedding": _vector(DIM)}],
    }
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a"])
    assert exc_info.value.code == "INVALID_RESPONSE"


@patch("requests.post")
def test_embed_batch_rejects_dimension_mismatch(post_mock):
    """A vector whose length != target_dimensions raises LLMError."""
    payload = _embeddings_response([_vector(DIM + 1)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a"])
    assert exc_info.value.code == "INVALID_RESPONSE"


@patch("requests.post")
def test_embed_batch_rejects_non_object_entry(post_mock):
    """A non-dict entry in the batch response raises LLMError."""
    payload = _embeddings_response([_vector(DIM)], indices=[0])
    payload["data"][0] = "not an object"
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed_batch(["a"])
    assert exc_info.value.code == "INVALID_RESPONSE"


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------


@patch("requests.get")
def test_dimensions_returns_target_with_no_probe(get_mock):
    """dimensions returns target_dimensions without any network request."""
    get_mock.assert_not_called()

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    assert service.dimensions == DIM


@patch("requests.post")
def test_eager_dimensions_observed_from_first_request(post_mock):
    """eager mode discovers dimensions from the first real request; no probe.

    Before the first request, ``dimensions`` is unknown and raises
    ``LLMError`` (fail-loud) rather than issuing a network probe.  After the
    first real request, the observed dimension is remembered.
    """
    payload = _embeddings_response([_vector(256)])
    post_mock.return_value = Mock(json=lambda: payload, status_code=200)

    service = LlamaCppEmbedding("m", target_dimensions=None, eager=True)

    with pytest.raises(LLMError) as exc_info:
        service.dimensions
    assert exc_info.value.code == "UNKNOWN_DIMENSIONS"
    post_mock.assert_not_called()  # no probe before the first real request

    service.embed("x")
    assert service.dimensions == 256


@patch("requests.get")
def test_eager_dimensions_no_probe(get_mock):
    """eager dimensions are not probed before the first real request.

    ``dimensions`` raises ``LLMError`` when dimensions are unknown; it never
    issues a GET probe to discover them.  After the first real request, the
    observed dimension is remembered and returned.
    """
    get_mock.assert_not_called()
    service = LlamaCppEmbedding("m", target_dimensions=None, eager=True)
    with pytest.raises(LLMError) as exc_info:
        service.dimensions
    assert exc_info.value.code == "UNKNOWN_DIMENSIONS"
    assert get_mock.call_count == 0


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@patch("requests.get")
def test_is_available_true_on_200(get_mock):
    """is_available returns True on a 200 from /v1/models."""
    get_mock.return_value = Mock(status_code=200)
    assert LlamaCppEmbedding("m", target_dimensions=DIM).is_available() is True


@patch("requests.get")
def test_is_available_false_on_connection_error(get_mock):
    """is_available returns False when the server is unreachable."""
    get_mock.side_effect = requests.exceptions.ConnectionError("refused")
    assert LlamaCppEmbedding("m", target_dimensions=DIM).is_available() is False


# ---------------------------------------------------------------------------
# HTTP errors and timeouts
# ---------------------------------------------------------------------------


@patch("requests.post")
def test_embed_raises_on_404(post_mock):
    """A 404 response raises LLMError."""
    error_response = Mock(status_code=404, text="model not found")
    error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=error_response
    )
    post_mock.return_value = error_response

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed("x")
    assert exc_info.value.code == "HTTP_ERROR"


@patch("requests.post")
def test_embed_raises_on_timeout(post_mock):
    """A request timeout raises LLMError."""
    post_mock.side_effect = requests.exceptions.Timeout("timed out")

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed("x")
    assert exc_info.value.code == "TIMEOUT"


@patch("requests.post")
def test_embed_raises_on_connection_error(post_mock):
    """A connection error raises LLMError."""
    post_mock.side_effect = requests.exceptions.ConnectionError("refused")

    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed("x")
    assert exc_info.value.code == "CONNECTION_ERROR"


@patch("requests.post")
def test_embed_raises_on_malformed_json(post_mock):
    """Malformed JSON raises LLMError."""
    post_mock.return_value = Mock(
        status_code=200,
        text="not json",
        json=MagicMock(side_effect=__import__("json").JSONDecodeError("bad", "n", -1)),
    )
    service = LlamaCppEmbedding("m", target_dimensions=DIM)
    with pytest.raises(LLMError) as exc_info:
        service.embed("x")
    assert exc_info.value.code == "PARSE_ERROR"
