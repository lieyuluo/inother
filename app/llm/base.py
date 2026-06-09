"""Base LLM provider interface."""

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, query: str, context: str) -> str:
        """Generate a response given a query and context.

        Args:
            query: User question.
            context: RAG context from retrieved documents.

        Returns:
            Generated response text.
        """
        pass
