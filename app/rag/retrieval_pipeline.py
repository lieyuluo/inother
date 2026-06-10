"""Retrieval pipeline supporting vector, keyword, and hybrid modes."""

import time
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.llm.provider import get_llm_provider
from app.rag.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.rag.keyword_retriever import KeywordRetriever
from app.rag.reranker import LLMReranker, NoopReranker
from app.rag.retriever import RetrievalResult, Retriever


@dataclass
class RetrievalTrace:
    """Trace metadata for a retrieval operation."""

    retrieval_mode: str = "vector"
    vector_results_count: int = 0
    keyword_results_count: int = 0
    final_results_count: int = 0
    reranker_provider: str = "none"
    reranker_fallback_reason: str | None = None
    filters: dict[str, object] = field(default_factory=dict)
    elapsed_ms: float = 0.0


class RetrievalPipeline:
    """Retrieval pipeline that supports vector, keyword, and hybrid modes.

    Modes:
    - vector: Uses embedding similarity search (default)
    - keyword: Uses SQL LIKE keyword matching
    - hybrid: Combines vector and keyword using simple RRF fusion
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        top_k: int | None = None,
        snippet_max_length: int | None = None,
        user_id: UUID | None = None,
        mode: str | None = None,
    ):
        settings = get_settings()
        self.session = session
        self.top_k = top_k or settings.rag_top_k
        self.snippet_max_length = snippet_max_length or settings.rag_snippet_max_length
        self.user_id = user_id
        self.mode = mode or settings.rag_retrieval_mode
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider(
            dimension=settings.embedding_dimension
        )
        self.reranker_provider = settings.rag_reranker_provider

    async def retrieve(self, query: str) -> tuple[list[RetrievalResult], RetrievalTrace]:
        """Retrieve relevant documents based on configured mode.

        Returns:
            Tuple of (results, trace_metadata)
        """
        start = time.monotonic()
        trace = RetrievalTrace(
            retrieval_mode=self.mode,
            reranker_provider=self.reranker_provider,
            filters={"user_id": str(self.user_id) if self.user_id else None},
        )

        if self.mode == "keyword":
            results = await self._keyword_retrieve(query)
            trace.keyword_results_count = len(results)
        elif self.mode == "hybrid":
            results = await self._hybrid_retrieve(query)
        else:  # vector (default)
            results = await self._vector_retrieve(query)
            trace.vector_results_count = len(results)

        results, reranker_fallback_reason = self._rerank(query, results)
        trace.reranker_fallback_reason = reranker_fallback_reason

        trace.final_results_count = len(results)
        trace.elapsed_ms = (time.monotonic() - start) * 1000
        return results, trace

    async def _vector_retrieve(self, query: str) -> list[RetrievalResult]:
        retriever = Retriever(
            session=self.session,
            embedding_provider=self.embedding_provider,
            top_k=self.top_k,
            snippet_max_length=self.snippet_max_length,
            user_id=self.user_id,
        )
        return await retriever.similarity_search(query)

    async def _keyword_retrieve(self, query: str) -> list[RetrievalResult]:
        retriever = KeywordRetriever(
            session=self.session,
            top_k=self.top_k,
            user_id=self.user_id,
        )
        return await retriever.search(query)

    async def _hybrid_retrieve(self, query: str) -> list[RetrievalResult]:
        """Hybrid retrieval using RRF (Reciprocal Rank Fusion)."""
        # Run both retrievers
        vector_results = await self._vector_retrieve(query)
        keyword_results = await self._keyword_retrieve(query)

        # RRF fusion
        rrf_k = 60  # RRF constant
        scores: dict[str, tuple[float, RetrievalResult]] = {}

        for rank, r in enumerate(vector_results):
            if r.chunk_id not in scores:
                scores[r.chunk_id] = (0.0, r)
            score, result = scores[r.chunk_id]
            score += 1.0 / (rrf_k + rank + 1)
            scores[r.chunk_id] = (score, result)

        for rank, r in enumerate(keyword_results):
            if r.chunk_id not in scores:
                scores[r.chunk_id] = (0.0, r)
            score, result = scores[r.chunk_id]
            score += 1.0 / (rrf_k + rank + 1)
            scores[r.chunk_id] = (score, result)

        # Sort by fused score
        fused = sorted(scores.values(), key=lambda x: x[0], reverse=True)
        results = []
        for score, r in fused[: self.top_k]:
            r.score = score
            results.append(r)

        return results

    def _rerank(
        self,
        query: str,
        results: list[RetrievalResult],
    ) -> tuple[list[RetrievalResult], str | None]:
        """Apply configured reranker, falling back to no-op on failure."""
        if self.reranker_provider == "none":
            return NoopReranker().rerank(query, results), None

        if self.reranker_provider != "llm":
            return results, f"Unsupported reranker provider: {self.reranker_provider}"

        try:
            reranker = LLMReranker(get_llm_provider(get_settings()))
            return reranker.rerank(query, results), None
        except Exception as e:
            return NoopReranker().rerank(query, results), str(e)
