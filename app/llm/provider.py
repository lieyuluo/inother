"""LLM provider factory for creating provider instances."""

from app.core.config import Settings
from app.llm.base import BaseLLMProvider
from app.llm.fake import FakeLLMProvider
from app.llm.openai_provider import OpenAILLMProvider


def get_llm_provider(settings: Settings | None = None) -> BaseLLMProvider:
    """Get LLM provider based on configuration.

    Args:
        settings: Application settings. If None, loads from environment.

    Returns:
        LLM provider instance.

    Raises:
        ValueError: If LLM_PROVIDER is not supported.
        ProviderConfigError: If required config is missing for the provider.
    """
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    provider_name = settings.llm_provider.lower()

    if provider_name == "fake":
        return FakeLLMProvider()
    elif provider_name == "openai":
        return OpenAILLMProvider(
            api_key=settings.effective_llm_api_key or None,
            model=settings.openai_llm_model,
            base_url=settings.effective_llm_base_url,
            timeout=settings.provider_timeout_seconds,
            max_retries=settings.provider_max_retries,
        )
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider_name}'. Supported providers: 'fake', 'openai'."
        )
