"""Test fixtures and configuration."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, User
from app.db.repositories import ChatMessageRepository, ChatSessionRepository, UserRepository
from app.db.session import get_db_session
from app.main import app


# Sync engine for sync tests (using SQLite in-memory)
SYNC_DATABASE_URL = "sqlite:///:memory:?check_same_thread=False"
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SyncSessionFactory = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="function")
def sync_db() -> Generator[Session, None, None]:
    """Create a sync database session for testing."""
    # Create tables
    Base.metadata.create_all(sync_engine)
    session = SyncSessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        # Drop tables after test
        Base.metadata.drop_all(sync_engine)


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def db_session(sync_db: Session) -> Session:
    """Alias for sync_db."""
    return sync_db


@pytest.fixture
def user_repo(sync_db: Session) -> UserRepository:
    """Create a user repository."""
    return UserRepository(sync_db)


@pytest.fixture
def session_repo(sync_db: Session) -> ChatSessionRepository:
    """Create a chat session repository."""
    return ChatSessionRepository(sync_db)


@pytest.fixture
def message_repo(sync_db: Session) -> ChatMessageRepository:
    """Create a chat message repository."""
    return ChatMessageRepository(sync_db)


@pytest.fixture
def demo_user(sync_db: Session) -> User:
    """Create a demo user for testing."""
    user = User(
        id=uuid4(),
        email="demo@example.com",
        username="demo_user",
        hashed_password="demo_hash",
        is_active=True,
        is_superuser=False,
        full_name="Demo User",
    )
    sync_db.add(user)
    sync_db.commit()
    sync_db.refresh(user)
    return user


@pytest.fixture
def test_session(sync_db: Session, demo_user: User) -> ChatSession:
    """Create a test chat session."""
    session = ChatSession(
        id=uuid4(),
        user_id=demo_user.id,
        title="Test Session",
        is_active=True,
    )
    sync_db.add(session)
    sync_db.commit()
    sync_db.refresh(session)
    return session


@pytest.fixture
def test_messages(sync_db: Session, test_session: ChatSession) -> list[ChatMessage]:
    """Create test messages for a session."""
    messages = [
        ChatMessage(
            id=uuid4(),
            session_id=test_session.id,
            role="user",
            content="Hello",
        ),
        ChatMessage(
            id=uuid4(),
            session_id=test_session.id,
            role="assistant",
            content="Echo: Hello",
        ),
    ]
    for msg in messages:
        sync_db.add(msg)
    sync_db.commit()
    for msg in messages:
        sync_db.refresh(msg)
    return messages