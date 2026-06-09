"""Embedding providers for generating vector embeddings."""

from abc import ABC, abstractmethod
from typing import Protocol
import hashlib
import struct


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers.

    Defines the interface for embedding generation.
    """

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        ...

    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Number of dimensions in embedding vector
        """
        ...


class BaseEmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Generate embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Number of dimensions in embedding vector
        """
        pass


class FakeEmbeddingProvider(BaseEmbeddingProvider):
    """Fake embedding provider for testing and development.

    This provider generates deterministic embeddings without network calls.

    Characteristics:
    - Deterministic: same text always produces same embedding
    - No network calls: purely local computation
    - Fixed dimension: configurable, default 1536 (matches OpenAI)
    - Different texts produce different embeddings (with high probability)

    Implementation:
    Uses SHA-256 hash of text to generate pseudo-random embedding values.
    The hash is expanded to fill the required dimension.
    """

    def __init__(self, dimension: int = 1536) -> None:
        """Initialize fake embedding provider.

        Args:
            dimension: Embedding dimension (default 1536 to match OpenAI)
        """
        self._dimension = dimension

        if dimension <= 0:
            raise ValueError("dimension must be positive")

    def embed(self, text: str) -> list[float]:
        """Generate deterministic embedding for text.

        Args:
            text: Input text

        Returns:
            Embedding vector with dimension values in range [-1, 1]
        """
        # Generate SHA-256 hash of text
        text_hash = hashlib.sha256(text.encode("utf-8")).digest()

        # Expand hash to required dimension
        # SHA-256 gives 32 bytes (256 bits), we need dimension floats
        embedding: list[float] = []

        # Use hash as seed for pseudo-random generation
        seed = int.from_bytes(text_hash[:8], byteorder="big")

        # Generate dimension values
        for i in range(self._dimension):
            # Create variation based on position and seed
            value_hash = hashlib.sha256(
                struct.pack(">QI", seed, i)
            ).digest()

            # Convert first 4 bytes to float in range [-1, 1]
            int_value = int.from_bytes(value_hash[:4], byteorder="big")
            # Normalize to [-1, 1]
            float_value = (int_value / (2**32 - 1)) * 2 - 1
            embedding.append(float_value)

        return embedding

    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Dimension of embedding vectors
        """
        return self._dimension


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Placeholder for OpenAI embedding provider.

    This is a placeholder for future implementation.
    Phase 3 does not use this provider to avoid network calls.

    Future implementation will:
    - Use OpenAI API (text-embedding-ada-002 or similar)
    - Handle API errors and rate limits
    - Support batch embedding
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-ada-002",
    ) -> None:
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (optional, can use env var)
            model: Embedding model name
        """
        self._api_key = api_key
        self._model = model
        self._dimension = 1536  # Default for ada-002

    def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API.

        NOT IMPLEMENTED in Phase 3.

        Raises:
            NotImplementedError: Always raises in Phase 3
        """
        raise NotImplementedError(
            "OpenAIEmbeddingProvider is not implemented in Phase 3. "
            "Use FakeEmbeddingProvider for testing."
        )

    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Dimension for OpenAI embeddings (1536)
        """
        return self._dimension


def get_embedding_provider(use_fake: bool = True) -> EmbeddingProvider:
    """Get embedding provider based on configuration.

    Args:
        use_fake: Whether to use fake provider (default True for Phase 3)

    Returns:
        Embedding provider instance
    """
    if use_fake:
        return FakeEmbeddingProvider()
    # Future: return OpenAIEmbeddingProvider() when implemented
    raise NotImplementedError("Real embedding provider not available in Phase 3")