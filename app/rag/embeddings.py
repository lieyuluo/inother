"""Embedding providers for generating vector embeddings."""

import asyncio
import hashlib
import struct
from abc import ABC, abstractmethod
from typing import Any, Protocol

import httpx

from app.core.provider_errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderTimeoutError,
)

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


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
            value_hash = hashlib.sha256(struct.pack(">QI", seed, i)).digest()

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
    """OpenAI-compatible embedding provider.

    Uses httpx.AsyncClient to call Embeddings API.
    Supports configurable base_url for compatible services.

    This provider requires an API key. If not provided,
    ProviderConfigError is raised.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        base_url: str = _DEFAULT_BASE_URL,
        dimension: int = 1536,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialize OpenAI-compatible embedding provider.

        Args:
            api_key: API key for authentication.
            model: Embedding model name.
            base_url: API base URL (default: OpenAI).
            dimension: Expected embedding dimension.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries on server errors.
            client: Optional httpx.AsyncClient (for testing/mocking).

        Raises:
            ProviderConfigError: If api_key is not provided.
        """
        if not api_key:
            raise ProviderConfigError(
                "OPENAI_API_KEY is required when using OpenAI Embedding provider. "
                "Set EMBEDDING_PROVIDER=fake or provide a valid API key.",
                provider="openai_embedding",
            )

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._dimension = dimension
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = client

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API (synchronous wrapper).

        Note: This is a sync wrapper around the async implementation.
        For production use, prefer calling _async_embed directly.

        Args:
            text: Input text.

        Returns:
            Embedding vector.

        Raises:
            ProviderTimeoutError: If request times out.
            ProviderResponseError: If response is invalid.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context, use a new event loop
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._async_embed(text))
                return future.result()
        else:
            return asyncio.run(self._async_embed(text))

    async def _async_embed(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API (async).

        Args:
            text: Input text.

        Returns:
            Embedding vector.

        Raises:
            ProviderTimeoutError: If request times out.
            ProviderResponseError: If response is invalid.
        """
        payload: dict[str, Any] = {
            "model": self._model,
            "input": text,
        }

        url = f"{self._base_url}/embeddings"
        last_error: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_client()
                response = await client.post(url, json=payload)

                if response.status_code >= 500:
                    last_error = ProviderResponseError(
                        f"Server error: HTTP {response.status_code}",
                        provider="openai_embedding",
                    )
                    if attempt < self._max_retries:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    raise last_error

                if response.status_code >= 400:
                    raise ProviderResponseError(
                        f"Client error: HTTP {response.status_code} - {response.text[:200]}",
                        provider="openai_embedding",
                    )

                data = response.json()

                # Validate response structure
                if "data" not in data or not data["data"]:
                    raise ProviderResponseError(
                        "Invalid response: missing 'data' field",
                        provider="openai_embedding",
                    )

                embedding_data = data["data"][0]
                if "embedding" not in embedding_data:
                    raise ProviderResponseError(
                        "Invalid response: missing 'embedding' field",
                        provider="openai_embedding",
                    )

                embedding: list[float] = embedding_data["embedding"]

                # Validate dimension
                if len(embedding) != self._dimension:
                    raise ProviderResponseError(
                        f"Embedding dimension mismatch: expected {self._dimension}, "
                        f"got {len(embedding)}. "
                        f"Update EMBEDDING_DIMENSION or use a different model.",
                        provider="openai_embedding",
                    )

                return embedding

            except httpx.TimeoutException as e:
                raise ProviderTimeoutError(
                    f"Request timed out after {self._timeout}s",
                    provider="openai_embedding",
                ) from e
            except httpx.HTTPError as e:
                raise ProviderResponseError(
                    f"HTTP error: {e}",
                    provider="openai_embedding",
                ) from e

        if last_error:
            raise last_error
        raise ProviderResponseError("Unexpected error in embed()", provider="openai_embedding")

    def get_dimension(self) -> int:
        """Get embedding dimension.

        Returns:
            Expected dimension for embeddings.
        """
        return self._dimension


def get_embedding_provider(
    provider_name: str = "fake",
    dimension: int = 1536,
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
    max_retries: int = _DEFAULT_MAX_RETRIES,
) -> BaseEmbeddingProvider:
    """Get embedding provider based on configuration.

    Args:
        provider_name: Provider name ('fake' or 'openai').
        dimension: Embedding dimension.
        api_key: API key for external providers.
        model: Model name for external providers.
        base_url: Base URL for external providers.
        timeout: Request timeout in seconds.
        max_retries: Maximum number of retries.

    Returns:
        Embedding provider instance.

    Raises:
        ValueError: If provider_name is not supported.
        ProviderConfigError: If required config is missing.
    """
    if provider_name == "fake":
        return FakeEmbeddingProvider(dimension=dimension)
    elif provider_name == "openai":
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=model or "text-embedding-3-small",
            base_url=base_url or _DEFAULT_BASE_URL,
            dimension=dimension,
            timeout=timeout,
            max_retries=max_retries,
        )
    else:
        raise ValueError(
            f"Unsupported embedding provider: '{provider_name}'. "
            f"Supported providers: 'fake', 'openai'."
        )
