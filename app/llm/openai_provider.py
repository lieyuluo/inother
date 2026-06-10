"""OpenAI-compatible LLM provider using httpx.

This provider calls OpenAI Chat Completions API (or any compatible endpoint).
It supports configurable base_url, model, timeout, and retries.

Tests must use mock HTTP clients - no real network access.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.provider_errors import (
    ProviderConfigError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.llm.base import BaseLLMProvider

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI-compatible LLM provider.

    Uses httpx.Client to call Chat Completions API synchronously.
    Supports configurable base_url for compatible services.

    This provider requires an API key. If not provided,
    ProviderConfigError is raised on initialization.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        client: httpx.Client | None = None,
    ) -> None:
        """Initialize OpenAI-compatible LLM provider.

        Args:
            api_key: API key for authentication.
            model: LLM model name.
            base_url: API base URL (default: OpenAI).
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retries on server errors.
            client: Optional httpx.Client (for testing/mocking).

        Raises:
            ProviderConfigError: If api_key is not provided.
        """
        if not api_key:
            raise ProviderConfigError(
                "OPENAI_API_KEY is required when using OpenAI LLM provider. "
                "Set LLM_PROVIDER=fake or provide a valid API key.",
                provider="openai_llm",
            )

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = client

    def _get_client(self) -> httpx.Client:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def generate(self, query: str, context: str) -> str:
        """Generate a response using OpenAI Chat Completions API.

        Args:
            query: User question.
            context: RAG context from retrieved documents.

        Returns:
            Generated response text.

        Raises:
            ProviderTimeoutError: If request times out.
            ProviderResponseError: If response is invalid or server error.
        """
        messages: list[dict[str, str]] = []

        if context:
            messages.append(
                {
                    "role": "system",
                    "content": f"Use the following context to answer the question:\n\n{context}",
                }
            )

        messages.append({"role": "user", "content": query})

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }

        url = f"{self._base_url}/chat/completions"
        last_error: ProviderResponseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                client = self._get_client()
                response = client.post(url, json=payload)

                if response.status_code >= 500:
                    last_error = ProviderResponseError(
                        f"Server error: HTTP {response.status_code}",
                        provider="openai_llm",
                    )
                    if attempt < self._max_retries:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    raise last_error

                if response.status_code >= 400:
                    raise ProviderResponseError(
                        f"Client error: HTTP {response.status_code} - {response.text[:200]}",
                        provider="openai_llm",
                    )

                data = response.json()

                if "choices" not in data or not data["choices"]:
                    raise ProviderResponseError(
                        "Invalid response: missing 'choices' field",
                        provider="openai_llm",
                    )

                choice = data["choices"][0]
                if "message" not in choice or "content" not in choice["message"]:
                    raise ProviderResponseError(
                        "Invalid response: missing 'message.content' field",
                        provider="openai_llm",
                    )

                return str(choice["message"]["content"])

            except httpx.TimeoutException as e:
                raise ProviderTimeoutError(
                    f"Request timed out after {self._timeout}s",
                    provider="openai_llm",
                ) from e
            except httpx.HTTPError as e:
                raise ProviderResponseError(
                    f"HTTP error: {e}",
                    provider="openai_llm",
                ) from e

        if last_error:
            raise last_error
        raise ProviderResponseError("Unexpected error in generate()", provider="openai_llm")
