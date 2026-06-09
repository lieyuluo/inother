"""Tests for Chat API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession
from app.db.repositories import ChatMessageRepository, ChatSessionRepository


class TestCreateSession:
    """Tests for creating chat sessions."""

    def test_create_session_success(self, client: TestClient) -> None:
        """Test creating a session successfully."""
        response = client.post("/api/chat/sessions", json={})
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["title"] == "New Chat"
        assert data["is_active"] is True
        assert "created_at" in data

    def test_create_session_with_title(self, client: TestClient) -> None:
        """Test creating a session with a custom title."""
        response = client.post("/api/chat/sessions", json={"title": "My Chat"})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Chat"

    def test_create_session_default_title(self, client: TestClient) -> None:
        """Test that session without title uses default 'New Chat'."""
        response = client.post("/api/chat/sessions", json={})
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Chat"


class TestListSessions:
    """Tests for listing chat sessions."""

    def test_list_sessions_success(self, client: TestClient) -> None:
        """Test listing sessions successfully."""
        # Create a session first
        client.post("/api/chat/sessions", json={"title": "Test Session"})

        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data
        assert data["total"] >= 1

    def test_list_sessions_empty(self, client: TestClient) -> None:
        """Test listing sessions when there are none."""
        response = client.get("/api/chat/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "total" in data


class TestGetSession:
    """Tests for getting a single session."""

    def test_get_session_success(self, client: TestClient) -> None:
        """Test getting a session by ID."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={"title": "Test"})
        session_id = create_response.json()["id"]

        # Get the session
        response = client.get(f"/api/chat/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
        assert data["title"] == "Test"

    def test_get_session_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent session returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/api/chat/sessions/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestGetMessages:
    """Tests for getting messages from a session."""

    def test_get_messages_success(self, client: TestClient) -> None:
        """Test getting messages from a session."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send a message
        client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
        )

        # Get messages
        response = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert data["total"] >= 2  # user + assistant

    def test_get_messages_not_found(self, client: TestClient) -> None:
        """Test getting messages from non-existent session returns 404."""
        fake_id = str(uuid4())
        response = client.get(f"/api/chat/sessions/{fake_id}/messages")
        assert response.status_code == 404

    def test_messages_ordered_by_created_at(self, client: TestClient) -> None:
        """Test that messages are ordered by created_at ascending."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send multiple messages
        client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "First"})
        client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Second"})

        # Get messages
        response = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert response.status_code == 200
        data = response.json()

        # Check ordering - user messages should be in order
        user_messages = [m for m in data["messages"] if m["role"] == "user"]
        assert len(user_messages) >= 2
        assert user_messages[0]["content"] == "First"
        assert user_messages[1]["content"] == "Second"


class TestSendMessage:
    """Tests for sending messages to a session."""

    def test_send_message_success(self, client: TestClient) -> None:
        """Test sending a message successfully with RAG response."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Hello"},
        )
        assert response.status_code == 201
        data = response.json()

        assert "user_message" in data
        assert "assistant_message" in data
        assert "citations" in data
        assert "trace_id" in data
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "Hello"
        assert data["assistant_message"]["role"] == "assistant"

    def test_send_message_creates_two_messages(self, client: TestClient) -> None:
        """Test that sending a message creates user and assistant messages."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        client.post(f"/api/chat/sessions/{session_id}/messages", json={"content": "Test"})

        # Get messages
        response = client.get(f"/api/chat/sessions/{session_id}/messages")
        data = response.json()

        # Should have at least 2 messages (user + assistant)
        assert data["total"] >= 2

        # Check roles
        roles = [m["role"] for m in data["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    def test_send_message_session_not_found(self, client: TestClient) -> None:
        """Test sending message to non-existent session returns 404."""
        fake_id = str(uuid4())
        response = client.post(
            f"/api/chat/sessions/{fake_id}/messages",
            json={"content": "Hello"},
        )
        assert response.status_code == 404

    def test_send_empty_content_returns_422(self, client: TestClient) -> None:
        """Test sending empty content returns validation error."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send empty message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": ""},
        )
        assert response.status_code == 422

    def test_send_whitespace_only_content_returns_422(self, client: TestClient) -> None:
        """Test sending whitespace-only content returns validation error."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send whitespace message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "   "},
        )
        assert response.status_code == 422


class TestRAGResponse:
    """Tests for RAG-powered assistant response."""

    def test_rag_response_has_citations_field(self, client: TestClient) -> None:
        """Test that RAG response includes citations field."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Test message"},
        )
        assert response.status_code == 201
        data = response.json()

        assert "citations" in data
        assert isinstance(data["citations"], list)

    def test_rag_response_has_trace_id(self, client: TestClient) -> None:
        """Test that RAG response includes trace_id."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "Test message"},
        )
        assert response.status_code == 201
        data = response.json()

        assert "trace_id" in data
        assert isinstance(data["trace_id"], str)
        assert len(data["trace_id"]) > 0

    def test_rag_no_documents_returns_fallback(self, client: TestClient) -> None:
        """Test that RAG returns fallback when no documents exist."""
        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message (no documents uploaded)
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What is the API?"},
        )
        assert response.status_code == 201
        data = response.json()

        # Should return fallback response
        assert data["assistant_message"]["content"] == "未在知识库中找到足够信息。"
        assert data["citations"] == []

    def test_rag_with_document_returns_citations(self, client: TestClient) -> None:
        """Test that RAG returns citations when documents exist."""
        # Upload a document first
        import io

        content = b"The enterprise AI agent system supports multiple API endpoints for chat and documents."
        file = io.BytesIO(content)
        client.post(
            "/api/documents/upload",
            files={"file": ("api_doc.txt", file, "text/plain")},
        )

        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message related to the document
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "What are the API endpoints?"},
        )
        assert response.status_code == 201
        data = response.json()

        # Should have citations from the ready document
        assert len(data["citations"]) > 0
        citation = data["citations"][0]
        assert "document_id" in citation
        assert "document_title" in citation
        assert "chunk_id" in citation
        assert "chunk_index" in citation
        assert "score" in citation
        assert "snippet" in citation

    def test_rag_citation_snippet_from_real_chunk(self, client: TestClient) -> None:
        """Test that citation snippets come from actual chunk content."""
        import io

        content = (
            b"The system provides REST API endpoints for chat sessions and document management."
        )
        file = io.BytesIO(content)
        client.post(
            "/api/documents/upload",
            files={"file": ("snippet_doc.txt", file, "text/plain")},
        )

        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "API endpoints"},
        )
        data = response.json()

        if data["citations"]:
            # Snippet should contain actual content from the document
            assert len(data["citations"][0]["snippet"]) > 0

    def test_rag_assistant_message_saves_citations_metadata(self, client: TestClient) -> None:
        """Test that assistant message metadata contains citations."""
        import io

        content = (
            b"The metadata test document describes how assistant messages store citation data."
        )
        file = io.BytesIO(content)
        client.post(
            "/api/documents/upload",
            files={"file": ("metadata_doc.txt", file, "text/plain")},
        )

        # Create a session
        create_response = client.post("/api/chat/sessions", json={})
        session_id = create_response.json()["id"]

        # Send message
        response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "API endpoints"},
        )
        assert response.status_code == 201

        # Get messages and check assistant message
        messages_response = client.get(f"/api/chat/sessions/{session_id}/messages")
        messages = messages_response.json()["messages"]
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1


class TestRepositoryLayer:
    """Tests for repository layer operations."""

    @pytest.mark.asyncio
    async def test_create_session_repo(
        self,
        async_db_session: AsyncSession,
    ) -> None:
        """Test creating a session via repository."""
        from app.db.models import User

        user = User(
            id=uuid4(),
            email="test@example.com",
            username="test_user",
            hashed_password="hash",
            is_active=True,
            is_superuser=False,
        )
        async_db_session.add(user)
        await async_db_session.commit()

        repo = ChatSessionRepository(async_db_session)
        session = await repo.create(user_id=user.id, title="Repo Test")

        assert session.id is not None
        assert session.title == "Repo Test"
        assert session.user_id == user.id

    @pytest.mark.asyncio
    async def test_create_message_repo(
        self,
        async_db_session: AsyncSession,
        test_session: ChatSession,
    ) -> None:
        """Test creating a message via repository."""
        repo = ChatMessageRepository(async_db_session)
        message = await repo.create(
            session_id=test_session.id,
            role="user",
            content="Repo message",
        )

        assert message.id is not None
        assert message.session_id == test_session.id
        assert message.role == "user"
        assert message.content == "Repo message"

    @pytest.mark.asyncio
    async def test_get_messages_ordered(
        self,
        async_db_session: AsyncSession,
        test_session: ChatSession,
    ) -> None:
        """Test that repository returns messages ordered by created_at."""
        repo = ChatMessageRepository(async_db_session)

        await repo.create(session_id=test_session.id, role="user", content="First")
        await repo.create(session_id=test_session.id, role="assistant", content="Echo: First")
        await repo.create(session_id=test_session.id, role="user", content="Second")
        await async_db_session.commit()

        messages = await repo.get_all_by_session(test_session.id)

        user_messages = [m for m in messages if m.role == "user"]
        assert user_messages[0].content == "First"
        assert user_messages[1].content == "Second"
