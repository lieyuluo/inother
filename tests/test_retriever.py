"""Tests for RAG Retriever."""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, DocumentChunk, User
from app.rag.embeddings import FakeEmbeddingProvider
from app.rag.retriever import Retriever, _cosine_similarity


class TestCosineSimilarity:
    """Tests for the cosine similarity helper function."""

    def test_identical_vectors(self) -> None:
        """Test that identical vectors have similarity 1.0."""
        vec = [1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(vec, vec) - 1.0) < 1e-6

    def test_opposite_vectors(self) -> None:
        """Test that opposite vectors have similarity -1.0."""
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        assert abs(_cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        """Test that orthogonal vectors have similarity 0.0."""
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self) -> None:
        """Test that zero vector returns 0.0."""
        a = [1.0, 0.0]
        b = [0.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0

    def test_different_dimensions(self) -> None:
        """Test that vectors of different dimensions return 0.0."""
        a = [1.0, 0.0]
        b = [1.0, 0.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0


class TestRetrieverReadyDocuments:
    """Tests for Retriever with ready documents."""

    @pytest.mark.asyncio
    async def test_retriever_returns_ready_chunks(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,
    ) -> None:
        """Test that retriever returns chunks from ready documents."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("API endpoints")

        assert len(results) > 0
        assert results[0].document_id == str(ready_document.id)

    @pytest.mark.asyncio
    async def test_retriever_result_structure(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that retriever results have the correct structure."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("API endpoints")

        assert len(results) > 0
        result = results[0]
        assert hasattr(result, "chunk_id")
        assert hasattr(result, "document_id")
        assert hasattr(result, "document_title")
        assert hasattr(result, "chunk_index")
        assert hasattr(result, "content")
        assert hasattr(result, "score")
        assert result.document_title == "Test Document"

    @pytest.mark.asyncio
    async def test_retriever_results_sorted_by_score(
        self,
        async_db_session: AsyncSession,
        demo_user: User,
    ) -> None:
        """Test that retriever results are sorted by score descending."""
        provider = FakeEmbeddingProvider(dimension=1536)

        doc1 = Document(
            id=uuid4(),
            user_id=demo_user.id,
            title="Doc Alpha",
            filename="alpha.txt",
            file_type="txt",
            file_size=100,
            status="ready",
        )
        async_db_session.add(doc1)
        await async_db_session.flush()

        chunk1_text = "Alpha content about machine learning algorithms"
        chunk1 = DocumentChunk(
            id=uuid4(),
            document_id=doc1.id,
            chunk_index=0,
            content=chunk1_text,
            embedding=provider.embed(chunk1_text),
            token_count=10,
        )
        async_db_session.add(chunk1)

        doc2 = Document(
            id=uuid4(),
            user_id=demo_user.id,
            title="Doc Beta",
            filename="beta.txt",
            file_type="txt",
            file_size=100,
            status="ready",
        )
        async_db_session.add(doc2)
        await async_db_session.flush()

        chunk2_text = "Beta content about database management systems"
        chunk2 = DocumentChunk(
            id=uuid4(),
            document_id=doc2.id,
            chunk_index=0,
            content=chunk2_text,
            embedding=provider.embed(chunk2_text),
            token_count=10,
        )
        async_db_session.add(chunk2)
        await async_db_session.commit()

        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("machine learning")

        # Results should be sorted by score descending
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score


class TestRetrieverExcludedDocuments:
    """Tests for Retriever filtering out non-ready documents."""

    @pytest.mark.asyncio
    async def test_retriever_excludes_deleted_documents(
        self,
        async_db_session: AsyncSession,
        deleted_document: Document,
    ) -> None:
        """Test that retriever does not return chunks from deleted documents."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("deleted document")

        doc_ids = [r.document_id for r in results]
        assert str(deleted_document.id) not in doc_ids

    @pytest.mark.asyncio
    async def test_retriever_excludes_failed_documents(
        self,
        async_db_session: AsyncSession,
        failed_document: Document,
    ) -> None:
        """Test that retriever does not return chunks from failed documents."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("failed document")

        doc_ids = [r.document_id for r in results]
        assert str(failed_document.id) not in doc_ids

    @pytest.mark.asyncio
    async def test_retriever_excludes_processing_documents(
        self,
        async_db_session: AsyncSession,
        processing_document: Document,
    ) -> None:
        """Test that retriever does not return chunks from processing documents."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("processing document")

        doc_ids = [r.document_id for r in results]
        assert str(processing_document.id) not in doc_ids


class TestRetrieverTopK:
    """Tests for Retriever top_k configuration."""

    @pytest.mark.asyncio
    async def test_retriever_default_top_k(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that retriever uses default top_k=4."""
        retriever = Retriever(session=async_db_session)
        assert retriever.top_k == 4

    @pytest.mark.asyncio
    async def test_retriever_custom_top_k(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that retriever respects custom top_k."""
        retriever = Retriever(session=async_db_session, top_k=1)
        results = await retriever.similarity_search("API endpoints")

        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_retriever_no_chunks_returns_empty(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that retriever returns empty list when no chunks exist."""
        retriever = Retriever(session=async_db_session)
        results = await retriever.similarity_search("anything")

        assert results == []


class TestRetrieverSnippetLength:
    """Tests for Retriever snippet truncation."""

    @pytest.mark.asyncio
    async def test_retriever_snippet_truncation(
        self,
        async_db_session: AsyncSession,
        demo_user: User,
    ) -> None:
        """Test that retriever truncates snippets to max length."""
        provider = FakeEmbeddingProvider(dimension=1536)

        doc = Document(
            id=uuid4(),
            user_id=demo_user.id,
            title="Long Doc",
            filename="long.txt",
            file_type="txt",
            file_size=100,
            status="ready",
        )
        async_db_session.add(doc)
        await async_db_session.flush()

        long_content = "A" * 500
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=doc.id,
            chunk_index=0,
            content=long_content,
            embedding=provider.embed(long_content),
            token_count=100,
        )
        async_db_session.add(chunk)
        await async_db_session.commit()

        retriever = Retriever(session=async_db_session, snippet_max_length=50)
        results = await retriever.similarity_search("AAAA")

        if results:
            assert len(results[0].content) <= 50
