"""Tests for Provider architecture: LLM and Embedding providers and factories."""

import pytest

from app.core.config import Settings, clear_settings_cache
from app.llm.base import BaseLLMProvider
from app.llm.external import OpenAILLMProvider
from app.llm.fake import FALLBACK_RESPONSE, FakeLLMProvider
from app.llm.provider import get_llm_provider
from app.rag.embeddings import (
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)


class TestLLMProviderFactory:
    """Tests for LLM provider factory function."""

    def test_default_llm_provider_is_fake(self) -> None:
        """Test that default LLM provider is FakeLLMProvider."""
        settings = Settings(llm_provider="fake")
        provider = get_llm_provider(settings)
        assert isinstance(provider, FakeLLMProvider)

    def test_get_llm_provider_returns_fake(self) -> None:
        """Test that get_llm_provider with 'fake' returns FakeLLMProvider."""
        settings = Settings(llm_provider="fake")
        provider = get_llm_provider(settings)
        assert isinstance(provider, FakeLLMProvider)

    def test_get_llm_provider_returns_openai_placeholder(self) -> None:
        """Test that get_llm_provider with 'openai' returns OpenAILLMProvider."""
        settings = Settings(llm_provider="openai")
        provider = get_llm_provider(settings)
        assert isinstance(provider, OpenAILLMProvider)

    def test_unsupported_llm_provider_raises_error(self) -> None:
        """Test that unsupported LLM provider raises ValueError."""
        settings = Settings(llm_provider="unsupported_provider")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_provider(settings)

    def test_unsupported_llm_provider_error_message(self) -> None:
        """Test that unsupported LLM provider error message is clear."""
        settings = Settings(llm_provider="anthropic")
        with pytest.raises(ValueError, match="'anthropic'"):
            get_llm_provider(settings)

    def test_get_llm_provider_case_insensitive(self) -> None:
        """Test that provider name is case insensitive."""
        settings = Settings(llm_provider="Fake")
        provider = get_llm_provider(settings)
        assert isinstance(provider, FakeLLMProvider)

    def test_get_llm_provider_without_settings(self) -> None:
        """Test that get_llm_provider works without explicit settings."""
        clear_settings_cache()
        provider = get_llm_provider()
        assert isinstance(provider, FakeLLMProvider)


class TestEmbeddingProviderFactory:
    """Tests for Embedding provider factory function."""

    def test_default_embedding_provider_is_fake(self) -> None:
        """Test that default embedding provider is FakeEmbeddingProvider."""
        provider = get_embedding_provider(provider_name="fake")
        assert isinstance(provider, FakeEmbeddingProvider)

    def test_get_embedding_provider_returns_fake(self) -> None:
        """Test that get_embedding_provider with 'fake' returns FakeEmbeddingProvider."""
        provider = get_embedding_provider(provider_name="fake", dimension=1536)
        assert isinstance(provider, FakeEmbeddingProvider)

    def test_get_embedding_provider_returns_openai_placeholder(self) -> None:
        """Test that get_embedding_provider with 'openai' returns OpenAIEmbeddingProvider."""
        provider = get_embedding_provider(provider_name="openai")
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_unsupported_embedding_provider_raises_error(self) -> None:
        """Test that unsupported embedding provider raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            get_embedding_provider(provider_name="unsupported_provider")

    def test_unsupported_embedding_provider_error_message(self) -> None:
        """Test that unsupported embedding provider error message is clear."""
        with pytest.raises(ValueError, match="'huggingface'"):
            get_embedding_provider(provider_name="huggingface")

    def test_get_embedding_provider_default_dimension(self) -> None:
        """Test that default dimension is 1536."""
        provider = get_embedding_provider(provider_name="fake")
        assert provider.get_dimension() == 1536

    def test_get_embedding_provider_custom_dimension(self) -> None:
        """Test that custom dimension is respected."""
        provider = get_embedding_provider(provider_name="fake", dimension=384)
        assert provider.get_dimension() == 384


class TestOpenAILLMProviderPlaceholder:
    """Tests for OpenAI LLM provider placeholder."""

    def test_openai_llm_raises_not_implemented(self) -> None:
        """Test that OpenAI LLM provider raises NotImplementedError."""
        provider = OpenAILLMProvider()
        with pytest.raises(NotImplementedError, match="v0.2 Phase 1"):
            provider.generate("test query", "test context")

    def test_openai_llm_no_network_access(self) -> None:
        """Test that OpenAI LLM provider does not access network."""
        provider = OpenAILLMProvider(api_key="test-key")
        # Should raise NotImplementedError, not attempt network call
        with pytest.raises(NotImplementedError):
            provider.generate("test", "context")

    def test_openai_llm_error_message_clear(self) -> None:
        """Test that OpenAI LLM provider error message is clear."""
        provider = OpenAILLMProvider()
        with pytest.raises(NotImplementedError, match="OpenAILLMProvider"):
            provider.generate("test", "context")

    def test_openai_llm_is_base_provider(self) -> None:
        """Test that OpenAILLMProvider is a BaseLLMProvider."""
        provider = OpenAILLMProvider()
        assert isinstance(provider, BaseLLMProvider)


class TestOpenAIEmbeddingProviderPlaceholder:
    """Tests for OpenAI Embedding provider placeholder."""

    def test_openai_embedding_raises_not_implemented(self) -> None:
        """Test that OpenAI Embedding provider raises NotImplementedError."""
        provider = OpenAIEmbeddingProvider()
        with pytest.raises(NotImplementedError, match="v0.2 Phase 1"):
            provider.embed("test text")

    def test_openai_embedding_no_network_access(self) -> None:
        """Test that OpenAI Embedding provider does not access network."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        # Should raise NotImplementedError, not attempt network call
        with pytest.raises(NotImplementedError):
            provider.embed("test")

    def test_openai_embedding_error_message_clear(self) -> None:
        """Test that OpenAI Embedding provider error message is clear."""
        provider = OpenAIEmbeddingProvider()
        with pytest.raises(NotImplementedError, match="OpenAIEmbeddingProvider"):
            provider.embed("test")

    def test_openai_embedding_get_dimension_works(self) -> None:
        """Test that get_dimension works for OpenAI Embedding provider."""
        provider = OpenAIEmbeddingProvider()
        assert provider.get_dimension() == 1536


class TestFakeLLMProviderCompatibility:
    """Tests that FakeLLMProvider remains compatible with v0.1 behavior."""

    def test_fake_llm_returns_fallback_when_context_empty(self) -> None:
        """Test that FakeLLMProvider returns fallback when context is empty."""
        provider = FakeLLMProvider()
        result = provider.generate("What is AI?", "")
        assert result == FALLBACK_RESPONSE

    def test_fake_llm_returns_context_summary(self) -> None:
        """Test that FakeLLMProvider returns context summary when context is present."""
        provider = FakeLLMProvider()
        result = provider.generate("What is AI?", "AI is artificial intelligence.")
        assert "根据知识库内容" in result

    def test_fake_llm_output_stable(self) -> None:
        """Test that FakeLLMProvider output is deterministic."""
        provider = FakeLLMProvider()
        result1 = provider.generate("What is AI?", "AI is artificial intelligence.")
        result2 = provider.generate("What is AI?", "AI is artificial intelligence.")
        assert result1 == result2

    def test_fake_llm_is_base_provider(self) -> None:
        """Test that FakeLLMProvider is a BaseLLMProvider."""
        provider = FakeLLMProvider()
        assert isinstance(provider, BaseLLMProvider)


class TestFakeEmbeddingProviderCompatibility:
    """Tests that FakeEmbeddingProvider remains compatible with v0.1 behavior."""

    def test_embedding_deterministic(self) -> None:
        """Test that same text produces same embedding."""
        provider = FakeEmbeddingProvider(dimension=1536)
        text = "Test text for embedding"
        embedding1 = provider.embed(text)
        embedding2 = provider.embed(text)
        assert embedding1 == embedding2

    def test_embedding_dimension_correct(self) -> None:
        """Test that embedding dimension is correct."""
        provider = FakeEmbeddingProvider(dimension=1536)
        embedding = provider.embed("Test text")
        assert len(embedding) == 1536

    def test_different_text_different_embedding(self) -> None:
        """Test that different texts produce different embeddings."""
        provider = FakeEmbeddingProvider(dimension=1536)
        embedding1 = provider.embed("First text")
        embedding2 = provider.embed("Second text")
        assert embedding1 != embedding2


class TestDatetimeUtcnowFix:
    """Tests that datetime.utcnow() has been replaced with timezone-aware version."""

    def test_no_utcnow_in_repositories(self) -> None:
        """Test that repositories.py no longer uses datetime.utcnow()."""
        import inspect

        from app.db import repositories

        source = inspect.getsource(repositories)
        assert "datetime.utcnow()" not in source
        assert "datetime.now(UTC)" in source

    def test_no_utcnow_in_project(self) -> None:
        """Test that no Python source in app/ uses datetime.utcnow()."""
        import os
        import pathlib

        app_dir = pathlib.Path(__file__).parent.parent / "app"
        for root, _dirs, files in os.walk(app_dir):
            for fname in files:
                if fname.endswith(".py"):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read()
                    assert "datetime.utcnow()" not in content, f"Found datetime.utcnow() in {fpath}"
