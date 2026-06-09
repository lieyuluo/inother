"""Test fixtures and configuration."""

import os
from collections.abc import AsyncGenerator, Generator
from uuid import uuid4

# Ensure test environment uses SQLite (not PostgreSQL/pgvector)
# MUST be set before importing app modules that create engines at module level
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test.db")
os.environ.setdefault("LLM_PROVIDER", "fake")
os.environ.setdefault("EMBEDDING_PROVIDER", "fake")

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.base import Base
from app.db.models import ChatMessage, ChatSession, Document, DocumentChunk, User
from app.db.repositories import (
    AuditLogRepository,
    ChatMessageRepository,
    ChatSessionRepository,
    DocumentChunkRepository,
    DocumentRepository,
    UserRepository,
)
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


@pytest.fixture
def document_repo(async_db_session: AsyncSession) -> DocumentRepository:
    """Create a document repository."""
    return DocumentRepository(async_db_session)


@pytest.fixture
def chunk_repo(async_db_session: AsyncSession) -> DocumentChunkRepository:
    """Create a document chunk repository."""
    return DocumentChunkRepository(async_db_session)


@pytest.fixture
def audit_repo(async_db_session: AsyncSession) -> AuditLogRepository:
    """Create an audit log repository."""
    return AuditLogRepository(async_db_session)


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


@pytest_asyncio.fixture
async def ready_document(
    async_db_session: AsyncSession,
    demo_user: User,
) -> Document:
    """Create a ready document with chunks for RAG testing."""
    from app.rag.embeddings import FakeEmbeddingProvider

    document = Document(
        id=uuid4(),
        user_id=demo_user.id,
        title="Test Document",
        filename="test.txt",
        file_type="txt",
        file_size=100,
        content_hash="abc123",
        status="ready",
    )
    async_db_session.add(document)
    await async_db_session.flush()

    provider = FakeEmbeddingProvider(dimension=1536)
    chunk_text = "This document describes the API endpoints for the enterprise AI agent system."
    embedding = provider.embed(chunk_text)

    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=chunk_text,
        embedding=embedding,
        token_count=10,
    )
    async_db_session.add(chunk)
    await async_db_session.commit()
    await async_db_session.refresh(document)
    return document


@pytest_asyncio.fixture
async def deleted_document(
    async_db_session: AsyncSession,
    demo_user: User,
) -> Document:
    """Create a deleted document with chunks for RAG testing."""
    from app.rag.embeddings import FakeEmbeddingProvider

    document = Document(
        id=uuid4(),
        user_id=demo_user.id,
        title="Deleted Document",
        filename="deleted.txt",
        file_type="txt",
        file_size=100,
        content_hash="def456",
        status="deleted",
    )
    async_db_session.add(document)
    await async_db_session.flush()

    provider = FakeEmbeddingProvider(dimension=1536)
    chunk_text = "This is content from a deleted document that should not appear in results."
    embedding = provider.embed(chunk_text)

    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=chunk_text,
        embedding=embedding,
        token_count=10,
    )
    async_db_session.add(chunk)
    await async_db_session.commit()
    await async_db_session.refresh(document)
    return document


@pytest_asyncio.fixture
async def failed_document(
    async_db_session: AsyncSession,
    demo_user: User,
) -> Document:
    """Create a failed document with chunks for RAG testing."""
    from app.rag.embeddings import FakeEmbeddingProvider

    document = Document(
        id=uuid4(),
        user_id=demo_user.id,
        title="Failed Document",
        filename="failed.txt",
        file_type="txt",
        file_size=100,
        content_hash="ghi789",
        status="failed",
    )
    async_db_session.add(document)
    await async_db_session.flush()

    provider = FakeEmbeddingProvider(dimension=1536)
    chunk_text = "This is content from a failed document that should not appear in results."
    embedding = provider.embed(chunk_text)

    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=chunk_text,
        embedding=embedding,
        token_count=10,
    )
    async_db_session.add(chunk)
    await async_db_session.commit()
    await async_db_session.refresh(document)
    return document


@pytest_asyncio.fixture
async def processing_document(
    async_db_session: AsyncSession,
    demo_user: User,
) -> Document:
    """Create a processing document with chunks for RAG testing."""
    from app.rag.embeddings import FakeEmbeddingProvider

    document = Document(
        id=uuid4(),
        user_id=demo_user.id,
        title="Processing Document",
        filename="processing.txt",
        file_type="txt",
        file_size=100,
        content_hash="jkl012",
        status="processing",
    )
    async_db_session.add(document)
    await async_db_session.flush()

    provider = FakeEmbeddingProvider(dimension=1536)
    chunk_text = "This is content from a processing document that should not appear in results."
    embedding = provider.embed(chunk_text)

    chunk = DocumentChunk(
        id=uuid4(),
        document_id=document.id,
        chunk_index=0,
        content=chunk_text,
        embedding=embedding,
        token_count=10,
    )
    async_db_session.add(chunk)
    await async_db_session.commit()
    await async_db_session.refresh(document)
    return document
