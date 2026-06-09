"""Tests for LLM Provider."""

from app.llm.fake import FALLBACK_RESPONSE, FakeLLMProvider


class TestFakeLLMProvider:
    """Tests for FakeLLMProvider."""

    def test_fake_llm_returns_fallback_when_context_empty(self) -> None:
        """Test that FakeLLMProvider returns fallback when context is empty."""
        provider = FakeLLMProvider()
        result = provider.generate("What is AI?", "")
        assert result == FALLBACK_RESPONSE

    def test_fake_llm_returns_fallback_when_context_whitespace(self) -> None:
        """Test that FakeLLMProvider returns fallback when context is whitespace."""
        provider = FakeLLMProvider()
        result = provider.generate("What is AI?", "   ")
        assert result == FALLBACK_RESPONSE

    def test_fake_llm_returns_context_summary_when_context_present(self) -> None:
        """Test that FakeLLMProvider returns context summary when context is present."""
        provider = FakeLLMProvider()
        result = provider.generate("What is AI?", "AI is artificial intelligence.")
        assert "根据知识库内容" in result
        assert "AI is artificial intelligence." in result

    def test_fake_llm_output_stable(self) -> None:
        """Test that FakeLLMProvider output is deterministic."""
        provider = FakeLLMProvider()
        result1 = provider.generate("What is AI?", "AI is artificial intelligence.")
        result2 = provider.generate("What is AI?", "AI is artificial intelligence.")
        assert result1 == result2

    def test_fake_llm_fallback_stable(self) -> None:
        """Test that FakeLLMProvider fallback is deterministic."""
        provider = FakeLLMProvider()
        result1 = provider.generate("What is AI?", "")
        result2 = provider.generate("Different question", "")
        assert result1 == result2
        assert result1 == FALLBACK_RESPONSE

    def test_fake_llm_context_used_in_output(self) -> None:
        """Test that FakeLLMProvider output reflects context usage."""
        provider = FakeLLMProvider()
        context = "The system supports REST API endpoints."
        result = provider.generate("What does the system support?", context)
        # Output should contain part of the context
        assert "根据知识库内容" in result

    def test_fake_llm_truncates_long_context(self) -> None:
        """Test that FakeLLMProvider truncates long context in output."""
        provider = FakeLLMProvider()
        long_context = "A" * 500
        result = provider.generate("Test", long_context)
        # Output should contain truncated context (200 chars)
        assert "根据知识库内容" in result
        assert len(result) < len(long_context) + 20  # Much shorter than raw context

    def test_fallback_response_value(self) -> None:
        """Test the fallback response constant value."""
        assert FALLBACK_RESPONSE == "未在知识库中找到足够信息。"
