"""llama.cpp embedding adapter (OpenAI-compatible `/v1/embeddings`).

Complements :class:`~laew.llm.llamacpp.LlamaCppProvider` (chat) with an
embedding service that talks to a llama.cpp server's OpenAI-compatible
``/v1/embeddings`` route.

Embeddings require a llama.cpp model with pooling != ``none`` (e.g. ``bge-m3``
or ``nomic-embed-text``).  The adapter is opt-in: it is selected via
``models.roles.embedding.type: "llamacpp"`` and never used for the Ollama
default.

Design notes
------------
- ``target_dimensions`` is the authoritative, user-declared vector size.  It is
  validated against the real response length on every request (fail-loud) and
  never probed with a hidden empty-text request.
- ``embed_batch`` posts all inputs in **one** request (the OpenAI batch form)
  and returns vectors in input order, keyed by each entry's ``index`` field.
- Responses are validated: exactly one vector per input, unique and complete
  ``0..N-1`` indexes, and every vector of length ``target_dimensions``.  Any
  violation raises :class:`~laew.llm.base.LLMError`.
"""

import json
from typing import List, Optional

import requests

from laew.llm.base import LLMError, normalize_llamacpp_base_url
from laew.rag.embedding import EmbeddingService


def _validate_embeddings(
    data: list,
    texts: list[str],
    target_dimensions: Optional[int],
) -> List[List[float]]:
    """Validate a llama.cpp embeddings response and return vectors in input order.

    Requires one entry per input, unique and complete ``0..N-1`` indexes, and
    each embedding of length ``target_dimensions`` (when set).  Returns the
    vectors reordered to input order, keyed by each entry's ``index`` field.
    """
    n = len(texts)
    if not isinstance(data, list) or len(data) != n:
        raise LLMError(
            f"llama.cpp returned {len(data)} embedding(s) for {n} input(s)",
            code="INVALID_RESPONSE",
        )

    by_index: dict = {}
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise LLMError(
                f"llama.cpp embedding entry {i} is not an object: {entry!r}",
                code="INVALID_RESPONSE",
            )
        index = entry.get("index")
        # JSON booleans are ints in Python; reject them explicitly.
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise LLMError(
                f"llama.cpp embedding entry {i} has invalid index: {index!r}",
                code="INVALID_RESPONSE",
            )
        if index in by_index:
            raise LLMError(
                f"llama.cpp returned duplicate embedding index {index}",
                code="INVALID_RESPONSE",
            )
        embedding = entry.get("embedding")
        if not isinstance(embedding, list):
            raise LLMError(
                f"llama.cpp embedding for index {index} is not a list: {entry!r}",
                code="INVALID_RESPONSE",
            )
        if target_dimensions is not None and len(embedding) != target_dimensions:
            raise LLMError(
                f"llama.cpp embedding for index {index} has length "
                f"{len(embedding)}, expected {target_dimensions}",
                code="INVALID_RESPONSE",
            )
        by_index[index] = embedding

    for i in range(n):
        if i not in by_index:
            raise LLMError(
                f"llama.cpp embedding response is missing index {i}",
                code="INVALID_RESPONSE",
            )

    return [by_index[i] for i in range(n)]


class LlamaCppEmbedding(EmbeddingService):
    """
    llama.cpp embedding service using the OpenAI-compatible ``/v1/embeddings``.

    Supports models with pooling != ``none`` (e.g. ``bge-m3``, ``nomic-embed-text``).
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://127.0.0.1:8080",
        target_dimensions: Optional[int] = None,
        *,
        timeout: int = 30,
        eager: bool = False,
    ):
        """
        Initialize the llama.cpp embedding service.

        Args:
            model: Embedding model name (server-side model ID).
            base_url: llama.cpp base URL (normalized to end in ``/v1``).
            target_dimensions: Authoritative embedding vector dimensionality.
                Required unless ``eager`` is set (dimensions are then observed
                from the first real request).
            timeout: Request timeout in seconds.
            eager: If true, allow construction without ``target_dimensions``;
                dimensions are discovered lazily from the first request.  No
                hidden probe is ever issued.
        """
        self.model = model
        self.base_url = normalize_llamacpp_base_url(base_url)
        self.timeout = timeout
        self.eager = eager
        if target_dimensions is None and not eager:
            raise LLMError(
                "LlamaCppEmbedding requires target_dimensions "
                "(or set eager=True to discover dimensions lazily)",
                code="MISSING_DIMENSIONS",
            )
        self.target_dimensions = target_dimensions
        self._dimensions: Optional[int] = None

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for a single text.

        Posts a single input to ``/v1/embeddings`` and returns the one vector,
        validated against ``target_dimensions``.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            LLMError: If the request fails or the response is invalid
        """
        url = f"{self.base_url}/embeddings"
        try:
            response = self._request(url, {"model": self.model, "input": text})
        except LLMError:
            raise
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"llama.cpp embedding request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        try:
            data = response.json().get("data", [])
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse llama.cpp embeddings response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        if not isinstance(data, list) or len(data) != 1:
            raise LLMError(
                f"expected exactly one embedding entry, got {len(data)}",
                code="INVALID_RESPONSE",
            )

        entry = data[0]
        if not isinstance(entry, dict):
            raise LLMError(
                f"unexpected llama.cpp embedding entry: {entry!r}",
                code="INVALID_RESPONSE",
            )
        embedding = entry.get("embedding")
        if not isinstance(embedding, list):
            raise LLMError(
                f"llama.cpp embedding for entry 0 is not a list: {entry!r}",
                code="INVALID_RESPONSE",
            )
        if self.target_dimensions is not None:
            if len(embedding) != self.target_dimensions:
                raise LLMError(
                    f"llama.cpp embedding has length {len(embedding)}, "
                    f"expected {self.target_dimensions}",
                    code="INVALID_RESPONSE",
                )
            return embedding
        # eager: observe dimensions from the first real response (no probe).
        self._dimensions = len(embedding)
        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in a single request.

        Posts all inputs in the OpenAI batch form (``{"input": texts}``) and
        returns vectors in input order.  The response is validated for one
        vector per input, unique and complete ``0..N-1`` indexes, and
        ``target_dimensions`` length.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors, in input order

        Raises:
            LLMError: If the request fails or the response is invalid
        """
        url = f"{self.base_url}/embeddings"
        try:
            response = self._request(
                url, {"model": self.model, "input": texts}
            )
        except LLMError:
            raise
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"llama.cpp embedding request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e

        try:
            data = response.json().get("data", [])
        except json.JSONDecodeError as e:
            raise LLMError(
                f"Failed to parse llama.cpp embeddings response: {response.text}",
                code="PARSE_ERROR",
            ) from e

        return _validate_embeddings(data, texts, self.target_dimensions)

    @property
    def dimensions(self) -> int:
        """Return embedding vector dimensionality.

        Returns the authoritative ``target_dimensions`` when set (no network
        probe).  Otherwise returns the dimension observed from the first real
        request (eager mode).
        """
        if self.target_dimensions is not None:
            return self.target_dimensions
        if self._dimensions is not None:
            return self._dimensions
        raise LLMError(
            "LlamaCppEmbedding dimensions are unknown; specify target_dimensions",
            code="UNKNOWN_DIMENSIONS",
        )

    def _request(self, url: str, payload: dict, *, timeout: Optional[int] = None) -> requests.Response:
        """Perform a llama.cpp HTTP request with error handling.

        Args:
            url: Absolute request URL
            payload: JSON request body
            timeout: Timeout in seconds (defaults to the provider timeout)

        Raises:
            LLMError: If the request fails
        """
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=timeout if timeout is not None else self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise LLMError(
                f"Failed to connect to llama.cpp at {self.base_url}",
                code="CONNECTION_ERROR",
            ) from e
        except requests.exceptions.Timeout as e:
            raise LLMError(
                f"llama.cpp embedding request timed out after {self.timeout}s",
                code="TIMEOUT",
            ) from e
        except requests.exceptions.HTTPError as e:
            raise LLMError(
                f"llama.cpp API error: {e.response.status_code} - {e.response.text}",
                code="HTTP_ERROR",
            ) from e
        except requests.exceptions.RequestException as e:
            raise LLMError(
                f"llama.cpp embedding request failed: {str(e)}",
                code="REQUEST_ERROR",
            ) from e
        return response

    def is_available(self) -> bool:
        """
        Check if the llama.cpp embedding service is available.

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


def build_llamacpp_embedding(
    model: str,
    base_url: Optional[str] = None,
    target_dimensions: Optional[int] = None,
    *,
    timeout: Optional[int] = None,
) -> LlamaCppEmbedding:
    """Create a :class:`LlamaCppEmbedding` from resolved embedding params.

    Used by :func:`laew.runtime.build_embedding_service` for the
    ``models.roles.embedding.type: "llamacpp"`` opt-in.  ``base_url`` is
    normalized to end in ``/v1``; ``target_dimensions`` is passed through
    unchanged so the adapter validates it against the real response.

    Args:
        model: Embedding model name (server-side model ID).
        base_url: llama.cpp base URL (normalized to end in ``/v1``).
        target_dimensions: Embedding vector dimensionality.
        timeout: Request timeout in seconds.
    """
    return LlamaCppEmbedding(
        model=model,
        base_url=base_url or "http://127.0.0.1:8080",
        target_dimensions=target_dimensions,
        timeout=timeout if timeout is not None else 30,
    )
