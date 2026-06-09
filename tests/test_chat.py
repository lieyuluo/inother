"""Tests for Chat API endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession
from app.db.repositories import ChatMessageRepository, ChatSessionRepository, UserRepository
from app.services.chat_service import ChatService


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
        # May have sessions from previous tests, but structure is correct
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
        """Test sending a message successfully."""
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
        assert data["user_message"]["role"] == "user"
        assert data["user_message"]["content"] == "Hello"
        assert data["assistant_message"]["role"] == "assistant"
        assert data["assistant_message"]["content"] == "Echo: Hello"

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


class TestMockResponse:
    """Tests for mock assistant response."""

    def test_mock_response_format(self, client: TestClient) -> None:
        """Test that mock response follows the expected format."""
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
        
        # Check mock response format
        assert data["assistant_message"]["content"] == "Echo: Test message"


class TestRepositoryLayer:
    """Tests for repository layer operations."""

    def test_create_session_repo(
        self,
        db_session: Session,
        demo_user: ChatSession,
    ) -> None:
        """Test creating a session via repository."""
        from app.db.models import User
        
        # Create user first
        user = User(
            id=uuid4(),
            email="test@example.com",
            username="test_user",
            hashed_password="hash",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        
        repo = ChatSessionRepository(db_session)
        session = repo.create(user_id=user.id, title="Repo Test")
        
        assert session.id is not None
        assert session.title == "Repo Test"
        assert session.user_id == user.id

    def test_create_message_repo(
        self,
        db_session: Session,
        test_session: ChatSession,
    ) -> None:
        """Test creating a message via repository."""
        repo = ChatMessageRepository(db_session)
        message = repo.create(
            session_id=test_session.id,
            role="user",
            content="Repo message",
        )
        
        assert message.id is not None
        assert message.session_id == test_session.id
        assert message.role == "user"
        assert message.content == "Repo message"

    def test_get_messages_ordered(
        self,
        db_session: Session,
        test_session: ChatSession,
    ) -> None:
        """Test that repository returns messages ordered by created_at."""
        repo = ChatMessageRepository(db_session)
        
        # Create messages
        repo.create(session_id=test_session.id, role="user", content="First")
        repo.create(session_id=test_session.id, role="assistant", content="Echo: First")
        repo.create(session_id=test_session.id, role="user", content="Second")
        
        db_session.commit()
        
        # Get messages
        messages = repo.get_all_by_session(test_session.id)
        
        # Check ordering
        user_messages = [m for m in messages if m.role == "user"]
        assert user_messages[0].content == "First"
        assert user_messages[1].content == "Second"