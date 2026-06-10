"""Reranker architecture placeholder."""

from app.rag.retriever import RetrievalResult


class BaseReranker:
    """Base class for rerankers."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:
        raise NotImplementedError


class NoopReranker(BaseReranker):
    """No-op reranker that returns results unchanged."""

    def rerank(self, query: str, results: list[RetrievalResult]) -> list[RetrievalResult]:  # noqa: ARG002
        return results
