"""Fake LLM provider for testing and development."""

from app.llm.base import BaseLLMProvider

FALLBACK_RESPONSE = "\u672a\u5728\u77e5\u8bc6\u5e93\u4e2d\u627e\u5230\u8db3\u591f\u4fe1\u606f\u3002"


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
        return f"\u6839\u636e\u77e5\u8bc6\u5e93\u5185\u5bb9\uff1a{context_summary}"
