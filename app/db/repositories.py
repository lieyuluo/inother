"""Database repository layer for data access operations."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage, ChatSession, User


class UserRepository:
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create_demo_user(self) -> User:
        """Get or create a demo user for Phase 2 development.

        This is a temporary solution until proper authentication is implemented.
        """
        # Try to find existing demo user
        stmt = select(User).where(User.email == "demo@example.com")
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            return user

        # Create demo user
        user = User(
            id=uuid4(),
            email="demo@example.com",
            username="demo_user",
            hashed_password="demo_password_hash_placeholder",  # Placeholder, not used for auth
            is_active=True,
            is_superuser=False,
            full_name="Demo User",
        )
        self.session.add(user)
        await self.session.flush()
        return user


class ChatSessionRepository:
    """Repository for ChatSession model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        title: str | None = None,
        is_active: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ChatSession:
        """Create a new chat session."""
        session = ChatSession(
            id=uuid4(),
            user_id=user_id,
            title=title or "New Chat",
            is_active=is_active,
            meta=metadata,
        )
        self.session.add(session)
        await self.session.flush()
        return session

    async def get_by_id(self, session_id: UUID) -> ChatSession | None:
        """Get a chat session by ID."""
        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChatSession]:
        """Get all chat sessions for a user, ordered by created_at descending."""
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(desc(ChatSession.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID) -> int:
        """Count chat sessions for a user."""
        stmt = select(ChatSession).where(ChatSession.user_id == user_id)
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))

    async def update(
        self,
        session: ChatSession,
        title: str | None = None,
        is_active: bool | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatSession:
        """Update a chat session."""
        if title is not None:
            session.title = title
        if is_active is not None:
            session.is_active = is_active
        if metadata is not None:
            session.meta = metadata
        session.updated_at = datetime.utcnow()
        await self.session.flush()
        return session


class ChatMessageRepository:
    """Repository for ChatMessage model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        session_id: UUID,
        role: str,
        content: str,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        """Create a new chat message."""
        message = ChatMessage(
            id=uuid4(),
            session_id=session_id,
            role=role,
            content=content,
            token_count=token_count,
            meta=metadata,
        )
        self.session.add(message)
        await self.session.flush()
        return message

    async def get_all_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """Get all messages for a session, ordered by created_at ascending."""
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(asc(ChatMessage.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_session(self, session_id: UUID) -> int:
        """Count messages for a session."""
        stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))