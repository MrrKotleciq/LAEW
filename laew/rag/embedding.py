"""Embedding service interface and implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional

import requests


class EmbeddingService(ABC):
    """Abstract interface for embedding generation services."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return embedding vector dimensionality."""
        pass


class OllamaEmbedding(EmbeddingService):
    """
    Ollama embedding service using /api/embeddings endpoint.

    Supports models like nomic-embed-text, all-minilm, etc.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        timeout: int = 30,
    ):
        """
        Initialize Ollama embedding service.

        Args:
            model: Embedding model name
            base_url: Ollama API base URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._dimensions: Optional[int] = None

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Input text to embed

        Returns:
            Embedding vector as list of floats

        Raises:
            RuntimeError: If embedding generation fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data.get("embedding", [])

            if not embedding:
                raise RuntimeError(f"No embedding returned from Ollama for model {self.model}")

            # Cache dimensions on first call
            if self._dimensions is None:
                self._dimensions = len(embedding)

            return embedding

        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama embedding request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Ollama API error: {e}")

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.

        Note: Ollama doesn't have a batch endpoint, so we call embed() for each text.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        return [self.embed(text) for text in texts]

    @property
    def dimensions(self) -> int:
        """Return embedding vector dimensionality."""
        if self._dimensions is None:
            # Generate a dummy embedding to get dimensions
            self.embed("test")
        return self._dimensions or 768  # Fallback default

    def is_available(self) -> bool:
        """
        Check if Ollama embedding service is available.

        Returns:
            True if service is reachable
        """
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False
