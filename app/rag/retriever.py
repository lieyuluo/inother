"""RAG retriever for searching relevant document chunks.

Supports two backends:
- PostgreSQL with pgvector: uses native cosine distance for vector similarity
- SQLite (testing): uses Python-level cosine similarity computation

The backend is automatically detected based on the database engine.
Database-specific logic is encapsulated within this class.
"""

import math
from dataclasses import dataclass

from sqlalchemy import select, text
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

    The backend is automatically detected based on the database URL in settings.
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
        # Detect database type from the actual session engine, not from settings.
        # This ensures SQLite test sessions always use Python cosine fallback,
        # even if settings.DATABASE_URL points to PostgreSQL.
        self._use_pgvector = self._detect_pgvector(session)

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

        if self._use_pgvector:
            return await self._pgvector_search(query_embedding)
        else:
            return await self._python_cosine_search(query_embedding)

    @staticmethod
    def _detect_pgvector(session: AsyncSession) -> bool:
        """Detect if the session is connected to PostgreSQL with pgvector.

        Checks the actual engine dialect of the session, not the settings.
        This ensures SQLite test sessions always use Python cosine fallback.

        Args:
            session: Async database session.

        Returns:
            True if the session uses PostgreSQL engine.
        """
        bind = session.get_bind()
        if bind is None:
            return False
        dialect = bind.dialect
        return dialect.name == "postgresql"

    async def _pgvector_search(self, query_embedding: list[float]) -> list[RetrievalResult]:
        """Search using pgvector native cosine distance query.

        Uses PostgreSQL pgvector operator '<=>' for cosine distance.
        Score is converted to similarity: score = 1 - distance.

        Args:
            query_embedding: Query embedding vector.

        Returns:
            List of RetrievalResult sorted by score descending.
        """
        # Format embedding as string for pgvector
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # Use raw SQL for pgvector cosine distance query
        # <=> is the cosine distance operator in pgvector
        query_sql = text("""
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                d.title AS document_title,
                dc.chunk_index,
                dc.content,
                1 - (dc.embedding <=> :query_embedding::vector) AS score
            FROM document_chunks dc
            JOIN documents d ON dc.document_id = d.id
            WHERE d.status = 'ready'
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> :query_embedding::vector
            LIMIT :limit
        """)

        result = await self.session.execute(
            query_sql,
            {"query_embedding": embedding_str, "limit": self.top_k},
        )
        rows = result.all()

        results: list[RetrievalResult] = []
        for row in rows:
            content = str(row.content)
            if len(content) > self.snippet_max_length:
                content = content[: self.snippet_max_length]

            results.append(
                RetrievalResult(
                    chunk_id=str(row.chunk_id),
                    document_id=str(row.document_id),
                    document_title=str(row.document_title),
                    chunk_index=int(row.chunk_index),
                    content=content,
                    score=float(row.score),
                )
            )

        return results

    async def _python_cosine_search(self, query_embedding: list[float]) -> list[RetrievalResult]:
        """Search using Python-level cosine similarity.

        This is the fallback path for SQLite and other databases
        that don't support pgvector.

        Args:
            query_embedding: Query embedding vector.

        Returns:
            List of RetrievalResult sorted by score descending.
        """
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
