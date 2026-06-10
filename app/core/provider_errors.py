"""Unified provider error types.

These errors are raised by LLM and Embedding providers.
They never contain API keys or sensitive credentials.
"""


class ProviderError(Exception):
    """Base error for all provider operations."""

    def __init__(self, message: str, provider: str = "unknown") -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {message}")


class ProviderConfigError(ProviderError):
    """Raised when provider configuration is invalid or missing.

    Examples:
    - Missing API key
    - Invalid base URL
    - Unsupported model
    """

    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message, provider)


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""

    def __init__(self, message: str = "Request timed out", provider: str = "unknown") -> None:
        super().__init__(message, provider)


class ProviderResponseError(ProviderError):
    """Raised when a provider returns an unexpected or invalid response.

    Examples:
    - Invalid JSON in response
    - Missing required fields
    - Unexpected status code
    - Dimension mismatch in embeddings
    """

    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message, provider)
