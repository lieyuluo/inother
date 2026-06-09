"""Fake LLM provider for testing and development."""

from app.llm.base import BaseLLMProvider

FALLBACK_RESPONSE = "未在知识库中找到足够信息。"


class FakeLLMProvider(BaseLLMProvider):
    """Fake LLM provider that generates deterministic responses without network calls.

    Characteristics:
    - Deterministic: same input always produces same output
    - No network calls: purely local computation
    - Uses context when available, returns stable fallback when not
    """

    def generate(self, query: str, context: str) -> str:  # noqa: ARG002
        """Generate a deterministic response.

        Args:
            query: User question.
            context: RAG context from retrieved documents.

        Returns:
            Response text. If context is empty, returns a stable fallback.
            If context is non-empty, returns a summary referencing the context.
        """
        if not context or not context.strip():
            return FALLBACK_RESPONSE

        # Truncate context summary to keep output reasonable
        context_summary = context[:200].strip()
        return f"根据知识库内容：{context_summary}"
