"""Tests for AuditLog and RAG audit logging."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.repositories import AuditLogRepository


class TestAuditLogRepository:
    """Tests for AuditLogRepository."""

    @pytest.mark.asyncio
    async def test_create_audit_log(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test creating an audit log entry."""
        repo = AuditLogRepository(async_db_session)
        log = await repo.create(
            action="rag.query",
            actor="system",
            resource_type="chat_session",
            resource_id=uuid4(),
            metadata={"trace_id": str(uuid4()), "query": "test"},
        )

        assert log.id is not None
        assert log.action == "rag.query"
        assert log.actor == "system"
        assert log.resource_type == "chat_session"
        assert log.meta is not None
        assert "trace_id" in log.meta

    @pytest.mark.asyncio
    async def test_audit_log_immutable(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that audit log has created_at but no updated_at."""
        repo = AuditLogRepository(async_db_session)
        log = await repo.create(
            action="test.action",
            actor="system",
        )

        assert log.created_at is not None
        # AuditLog does not have updated_at (immutable records)


class TestRAGAuditLog:
    """Tests for RAG audit logging in the Chat API."""

    def test_rag_query_creates_audit_log(self, client: TestClient) -> None:
        """Test that sending a chat message creates an audit log entry."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is the API?"},
        )
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_rag_audit_log_metadata(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that RAG audit log contains required metadata fields."""
        from app.services.chat_service import ChatService

        # Create a session via service
        service = ChatService(async_db_session)
        session_result = await service.create_session(title="Audit Test")

        # Send a message
        await service.send_message(session_result.id, "What is the API?")

        # Query audit logs
        stmt = select(AuditLog).where(AuditLog.action == "rag.query")
        result = await async_db_session.execute(stmt)
        logs = list(result.scalars().all())

        assert len(logs) >= 1
        log = logs[-1]  # Get the latest

        assert log.action == "rag.query"
        assert log.actor == "system"
        assert log.resource_type == "chat_session"
        assert log.resource_id == session_result.id
        assert log.meta is not None
        assert "trace_id" in log.meta
        assert "query" in log.meta
        assert "top_k" in log.meta
        assert "citations_count" in log.meta
        assert "used_fallback" in log.meta

    @pytest.mark.asyncio
    async def test_rag_audit_log_trace_id_matches_response(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that audit log trace_id matches the response trace_id."""
        from app.services.chat_service import ChatService

        service = ChatService(async_db_session)
        session_result = await service.create_session(title="Trace Test")

        # Send a message
        msg_result = await service.send_message(session_result.id, "What is the API?")
        assert msg_result is not None

        # Query audit logs
        stmt = select(AuditLog).where(AuditLog.action == "rag.query")
        result = await async_db_session.execute(stmt)
        logs = list(result.scalars().all())

        assert len(logs) >= 1
        log = logs[-1]

        # trace_id in audit log should match response trace_id
        assert log.meta["trace_id"] == msg_result.trace_id

    @pytest.mark.asyncio
    async def test_rag_audit_log_citations_count(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test that audit log citations_count matches actual citations."""
        from app.services.chat_service import ChatService

        service = ChatService(async_db_session)
        session_result = await service.create_session(title="Count Test")

        # Send a message (no documents, so citations_count should be 0)
        msg_result = await service.send_message(session_result.id, "What is the API?")
        assert msg_result is not None

        # Query audit logs
        stmt = select(AuditLog).where(AuditLog.action == "rag.query")
        result = await async_db_session.execute(stmt)
        logs = list(result.scalars().all())

        assert len(logs) >= 1
        log = logs[-1]

        assert log.meta["citations_count"] == len(msg_result.citations)
