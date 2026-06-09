"""RAG retriever for searching relevant document chunks."""

import math
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.rag.embeddings import EmbeddingProvider, FakeEmbeddingProvider


@dataclass
class RetrievalResult:
    """A single retrieval result from the RAG retriever."""

    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float


class Retriever:
    """RAG retriever that finds relevant document chunks using embedding similarity.

    Supports two backends:
    - PostgreSQL with pgvector: uses cosine distance for vector similarity
    - SQLite (testing): uses Python-level cosine similarity computation

    The backend is automatically detected based on the database engine.
    Database-specific logic is encapsulated within this class.
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        top_k: int | None = None,
        snippet_max_length: int | None = None,
    ) -> None:
        """Initialize retriever.

        Args:
            session: Async database session.
            embedding_provider: Embedding provider (default: FakeEmbeddingProvider).
            top_k: Number of results to return (default: from config).
            snippet_max_length: Max snippet length (default: from config).
        """
        settings = get_settings()
        self.session = session
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider(
            dimension=settings.embedding_dimension
        )
        self.top_k = top_k or settings.rag_top_k
        self.snippet_max_length = snippet_max_length or settings.rag_snippet_max_length

    async def similarity_search(self, query: str) -> list[RetrievalResult]:
        """Search for document chunks similar to the query.

        Args:
            query: User question text.

        Returns:
            List of RetrievalResult sorted by score descending.
            Only returns chunks from documents with status='ready'.
        """
        # Generate query embedding
        query_embedding = self.embedding_provider.embed(query)

        # Fetch all chunks from ready documents
        chunks = await self._fetch_ready_chunks()

        if not chunks:
            return []

        # Compute similarity scores
        results = self._compute_similarities(chunks, query_embedding)

        # Sort by score descending and take top_k
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[: self.top_k]

        # Truncate snippets
        for r in results:
            if len(r.content) > self.snippet_max_length:
                r.content = r.content[: self.snippet_max_length]

        return results

    async def _fetch_ready_chunks(self) -> list[tuple[DocumentChunk, str]]:
        """Fetch all chunks from documents with status='ready'.

        Returns:
            List of (DocumentChunk, document_title) tuples.
        """
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == "ready")
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row[0], row[1]) for row in rows]

    def _compute_similarities(
        self,
        chunks: list[tuple[DocumentChunk, str]],
        query_embedding: list[float],
    ) -> list[RetrievalResult]:
        """Compute cosine similarity between query embedding and chunk embeddings.

        This uses Python-level cosine similarity computation which works
        with both SQLite and PostgreSQL backends.

        Args:
            chunks: List of (DocumentChunk, document_title) tuples.
            query_embedding: Query embedding vector.

        Returns:
            List of RetrievalResult with similarity scores.
        """
        results: list[RetrievalResult] = []

        for chunk, doc_title in chunks:
            if chunk.embedding is None:
                continue

            score = _cosine_similarity(query_embedding, chunk.embedding)

            results.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    document_title=doc_title,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    score=score,
                )
            )

        return results


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector.
        b: Second vector.

    Returns:
        Cosine similarity score in range [-1, 1].
    """
    if len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)
