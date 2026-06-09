"""OpenAI LLM provider placeholder for future implementation."""

from app.llm.base import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    """Placeholder for OpenAI LLM provider.

    This is a placeholder for future implementation.
    v0.2 Phase 1 does not use this provider to avoid network calls.

    Future implementation will:
    - Use OpenAI Chat Completions API
    - Handle API errors and rate limits
    - Support streaming responses
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-3.5-turbo",
    ) -> None:
        """Initialize OpenAI LLM provider.

        Args:
            api_key: OpenAI API key (optional, can use env var)
            model: LLM model name
        """
        self._api_key = api_key
        self._model = model

    def generate(self, query: str, context: str) -> str:
        """Generate a response using OpenAI API.

        NOT IMPLEMENTED in v0.2 Phase 1.

        Raises:
            NotImplementedError: Always raises in v0.2 Phase 1
        """
        raise NotImplementedError(
            "OpenAILLMProvider is not implemented in v0.2 Phase 1. Use FakeLLMProvider for testing."
        )
