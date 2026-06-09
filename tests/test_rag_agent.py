"""Tests for RAG Agent."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag_agent import RAGAgent
from app.agents.schemas import RAGAgentResult
from app.db.models import Document
from app.llm.fake import FALLBACK_RESPONSE


class TestRAGAgentNoDocuments:
    """Tests for RAG Agent when no documents exist."""

    @pytest.mark.asyncio
    async def test_rag_agent_returns_fallback_when_no_docs(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that RAG Agent returns fallback when no documents exist."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("What is the API?")

        assert isinstance(result, RAGAgentResult)
        assert result.answer == FALLBACK_RESPONSE
        assert result.citations == []
        assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_rag_agent_has_trace_id(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that RAG Agent result has a trace_id."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("What is the API?")

        assert len(result.trace_id) > 0

    @pytest.mark.asyncio
    async def test_rag_agent_empty_citations_when_no_docs(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that RAG Agent returns empty citations when no documents exist."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("What is the API?")

        assert result.citations == []


class TestRAGAgentWithDocuments:
    """Tests for RAG Agent with documents."""

    @pytest.mark.asyncio
    async def test_rag_agent_returns_citations_with_ready_doc(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,
    ) -> None:
        """Test that RAG Agent returns citations when ready documents exist."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("API endpoints")

        assert len(result.citations) > 0
        assert result.citations[0].document_id == str(ready_document.id)

    @pytest.mark.asyncio
    async def test_rag_agent_answer_uses_context(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that RAG Agent answer reflects context usage."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("API endpoints")

        # Should not be fallback
        assert result.answer != FALLBACK_RESPONSE
        assert "根据知识库内容" in result.answer
        assert result.used_fallback is False

    @pytest.mark.asyncio
    async def test_rag_agent_citations_from_real_chunks(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that RAG Agent citations come from real DocumentChunk records."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("API endpoints")

        assert len(result.citations) > 0
        citation = result.citations[0]
        assert citation.document_title == "Test Document"
        assert len(citation.snippet) > 0
        assert citation.chunk_index == 0

    @pytest.mark.asyncio
    async def test_rag_agent_citations_count_within_top_k(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,  # noqa: ARG002
    ) -> None:
        """Test that citations count does not exceed top_k."""
        agent = RAGAgent(session=async_db_session, top_k=2)
        result = await agent.query("API endpoints")

        assert len(result.citations) <= 2


class TestRAGAgentExcludedDocuments:
    """Tests for RAG Agent filtering out non-ready documents."""

    @pytest.mark.asyncio
    async def test_rag_agent_excludes_deleted_documents(
        self,
        async_db_session: AsyncSession,
        deleted_document: Document,
    ) -> None:
        """Test that RAG Agent does not return citations from deleted documents."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("deleted document")

        doc_ids = [c.document_id for c in result.citations]
        assert str(deleted_document.id) not in doc_ids

    @pytest.mark.asyncio
    async def test_rag_agent_excludes_failed_documents(
        self,
        async_db_session: AsyncSession,
        failed_document: Document,
    ) -> None:
        """Test that RAG Agent does not return citations from failed documents."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("failed document")

        doc_ids = [c.document_id for c in result.citations]
        assert str(failed_document.id) not in doc_ids

    @pytest.mark.asyncio
    async def test_rag_agent_excludes_processing_documents(
        self,
        async_db_session: AsyncSession,
        processing_document: Document,
    ) -> None:
        """Test that RAG Agent does not return citations from processing documents."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("processing document")

        doc_ids = [c.document_id for c in result.citations]
        assert str(processing_document.id) not in doc_ids

    @pytest.mark.asyncio
    async def test_rag_agent_only_ready_documents(
        self,
        async_db_session: AsyncSession,
        ready_document: Document,
        deleted_document: Document,
        failed_document: Document,
        processing_document: Document,
    ) -> None:
        """Test that RAG Agent only returns citations from ready documents."""
        agent = RAGAgent(session=async_db_session)
        result = await agent.query("document content")

        doc_ids = [c.document_id for c in result.citations]
        # Only ready document should appear
        assert str(ready_document.id) in doc_ids
        assert str(deleted_document.id) not in doc_ids
        assert str(failed_document.id) not in doc_ids
        assert str(processing_document.id) not in doc_ids
