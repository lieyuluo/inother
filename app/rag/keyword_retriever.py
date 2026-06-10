"""Keyword-based retriever using SQL LIKE for text search."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk
from app.rag.retriever import RetrievalResult


class KeywordRetriever:
    """Simple keyword retriever using SQL LIKE matching.

    This is a lightweight fallback for hybrid search, not a production
    full-text search engine.
    """

    def __init__(self, session: AsyncSession, top_k: int = 4, user_id: UUID | None = None):
        self.session = session
        self.top_k = top_k
        self.user_id = user_id

    async def search(self, query: str) -> list[RetrievalResult]:
        """Search using keyword matching.

        Splits query into words and searches for any match using SQL LIKE.
        Applies user_id and visibility filtering.
        """
        words = [w.strip().lower() for w in query.split() if len(w.strip()) > 2]
        if not words:
            return []

        stmt = (
            select(DocumentChunk, Document.title, Document.visibility, Document.user_id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == "ready")
        )

        # Apply visibility filter
        if self.user_id is not None:
            stmt = stmt.where(
                or_(
                    Document.visibility == "public",
                    Document.user_id == self.user_id,
                )
            )

        # Apply keyword filter
        conditions = []
        for word in words[:5]:  # Limit to 5 keywords
            conditions.append(DocumentChunk.content.ilike(f"%{word}%"))
        stmt = stmt.where(or_(*conditions))

        result = await self.session.execute(stmt)
        rows = result.all()

        # Score: count matching keywords
        results = []
        for chunk, doc_title, _, _ in rows:
            content_lower = chunk.content.lower()
            score = sum(1 for w in words if w in content_lower) / len(words)
            results.append(
                RetrievalResult(
                    chunk_id=str(chunk.id),
                    document_id=str(chunk.document_id),
                    document_title=doc_title,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content[:300],
                    score=score,
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[: self.top_k]
