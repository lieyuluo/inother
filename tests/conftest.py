"""Test fixtures and configuration."""

from collections.abc import AsyncGenerator, Generator
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, User
from app.db.repositories import ChatMessageRepository, ChatSessionRepository, UserRepository
from app.db.session import get_db_session
from app.main import app


@pytest_asyncio.fixture
async def async_db_session(tmp_path) -> AsyncGenerator[AsyncSession, None]:
    """Create an isolated async database session for testing."""
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    engine = create_async_engine(database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture
def client(async_db_session: AsyncSession) -> Generator[TestClient, None, None]:
    """Create a test client for the FastAPI application."""

    async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield async_db_session
            await async_db_session.commit()
        except Exception:
            await async_db_session.rollback()
            raise

    app.dependency_overrides[get_db_session] = override_get_db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def user_repo(async_db_session: AsyncSession) -> UserRepository:
    """Create a user repository."""
    return UserRepository(async_db_session)


@pytest.fixture
def session_repo(async_db_session: AsyncSession) -> ChatSessionRepository:
    """Create a chat session repository."""
    return ChatSessionRepository(async_db_session)


@pytest.fixture
def message_repo(async_db_session: AsyncSession) -> ChatMessageRepository:
    """Create a chat message repository."""
    return ChatMessageRepository(async_db_session)


@pytest_asyncio.fixture
async def demo_user(async_db_session: AsyncSession) -> User:
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
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_session(async_db_session: AsyncSession, demo_user: User) -> ChatSession:
    """Create a test chat session."""
    session = ChatSession(
        id=uuid4(),
        user_id=demo_user.id,
        title="Test Session",
        is_active=True,
    )
    async_db_session.add(session)
    await async_db_session.commit()
    await async_db_session.refresh(session)
    return session


@pytest_asyncio.fixture
async def test_messages(
    async_db_session: AsyncSession,
    test_session: ChatSession,
) -> list[ChatMessage]:
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
        async_db_session.add(msg)
    await async_db_session.commit()
    for msg in messages:
        await async_db_session.refresh(msg)
    return messages
