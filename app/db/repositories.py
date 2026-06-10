"""Database repository layer for data access operations."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, ChatMessage, ChatSession, Document, DocumentChunk, User


class UserRepository:
    """Repository for User model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by ID."""
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email."""
        stmt = select(User).where(User.email == email)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        stmt = select(User).where(User.username == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        username: str,
        hashed_password: str,
        full_name: str | None = None,
        role: str = "user",
        is_active: bool = True,
        is_superuser: bool = False,
    ) -> User:
        """Create a user."""
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=is_active,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        await self.session.flush()
        return user

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
            is_superuser=True,
            role="admin",
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
        session.updated_at = datetime.now(UTC)
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


class DocumentRepository:
    """Repository for Document model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        title: str,
        filename: str,
        file_type: str,
        file_size: int,
        content_hash: str | None = None,
        status: str = "pending",
        metadata: dict[str, Any] | None = None,
        visibility: str = "private",
    ) -> Document:
        """Create a new document."""
        document = Document(
            id=uuid4(),
            user_id=user_id,
            title=title,
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            content_hash=content_hash,
            status=status,
            meta=metadata,
            visibility=visibility,
        )
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_by_id(self, document_id: UUID, include_deleted: bool = False) -> Document | None:
        """Get a document by ID.

        Args:
            document_id: Document UUID
            include_deleted: Whether to include deleted documents

        Returns:
            Document or None
        """
        stmt = select(Document).where(Document.id == document_id)
        if not include_deleted:
            stmt = stmt.where(Document.status != "deleted")
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
        include_deleted: bool = False,
    ) -> list[Document]:
        """Get all documents for a user, ordered by created_at descending.

        Args:
            user_id: User UUID
            limit: Maximum number of documents
            offset: Offset for pagination
            include_deleted: Whether to include deleted documents

        Returns:
            List of documents
        """
        stmt = select(Document).where(Document.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Document.status != "deleted")
        stmt = stmt.order_by(desc(Document.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_user(self, user_id: UUID, include_deleted: bool = False) -> int:
        """Count documents for a user.

        Args:
            user_id: User UUID
            include_deleted: Whether to include deleted documents

        Returns:
            Count of documents
        """
        stmt = select(func.count(Document.id)).where(Document.user_id == user_id)
        if not include_deleted:
            stmt = stmt.where(Document.status != "deleted")
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_accessible_by_user(
        self,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """Get documents accessible to a user: own documents + public documents."""
        stmt = (
            select(Document)
            .where(Document.status != "deleted")
            .where(or_(Document.user_id == user_id, Document.visibility == "public"))
            .order_by(desc(Document.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_accessible_by_user(self, user_id: UUID) -> int:
        """Count documents accessible to a user: own documents + public documents."""
        stmt = select(func.count(Document.id)).where(
            Document.status != "deleted",
            or_(Document.user_id == user_id, Document.visibility == "public"),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """Get all non-deleted documents (admin only)."""
        stmt = (
            select(Document)
            .where(Document.status != "deleted")
            .order_by(desc(Document.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_all(self) -> int:
        """Count all non-deleted documents (admin only)."""
        stmt = select(func.count(Document.id)).where(Document.status != "deleted")
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0

    async def update_status(
        self,
        document: Document,
        status: str,
    ) -> Document:
        """Update document status.

        Args:
            document: Document instance
            status: New status (uploaded, processing, ready, failed, deleted)

        Returns:
            Updated document
        """
        document.status = status
        document.updated_at = datetime.now(UTC)
        await self.session.flush()
        return document

    async def soft_delete(self, document: Document) -> Document:
        """Soft delete a document by setting status to 'deleted'.

        Args:
            document: Document instance

        Returns:
            Updated document with status='deleted'
        """
        return await self.update_status(document, "deleted")


class DocumentChunkRepository:
    """Repository for DocumentChunk model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        document_id: UUID,
        chunk_index: int,
        content: str,
        embedding: list[float] | None = None,
        token_count: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentChunk:
        """Create a new document chunk."""
        chunk = DocumentChunk(
            id=uuid4(),
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            embedding=embedding,
            token_count=token_count,
            meta=metadata,
        )
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def create_batch(
        self,
        chunks_data: list[dict[str, Any]],
    ) -> list[DocumentChunk]:
        """Create multiple document chunks in batch.

        Args:
            chunks_data: List of chunk data dictionaries

        Returns:
            List of created DocumentChunk instances
        """
        chunks = []
        for data in chunks_data:
            chunk = DocumentChunk(
                id=uuid4(),
                document_id=data["document_id"],
                chunk_index=data["chunk_index"],
                content=data["content"],
                embedding=data.get("embedding"),
                token_count=data.get("token_count"),
                meta=data.get("metadata"),
            )
            self.session.add(chunk)
            chunks.append(chunk)
        await self.session.flush()
        return chunks

    async def get_all_by_document(
        self,
        document_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DocumentChunk]:
        """Get all chunks for a document, ordered by chunk_index ascending.

        Args:
            document_id: Document UUID
            limit: Maximum number of chunks
            offset: Offset for pagination

        Returns:
            List of document chunks
        """
        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(asc(DocumentChunk.chunk_index))
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_document(self, document_id: UUID) -> int:
        """Count chunks for a document.

        Args:
            document_id: Document UUID

        Returns:
            Count of chunks
        """
        stmt = select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one() or 0


class AuditLogRepository:
    """Repository for AuditLog model operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_recent(self, limit: int = 50) -> list[AuditLog]:
        """List recent audit logs ordered by newest first."""
        stmt = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        action: str,
        actor: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        user_id: UUID | None = None,
    ) -> AuditLog:
        """Create an audit log entry.

        Args:
            action: Action name (e.g., 'rag.query').
            actor: Actor identifier (e.g., 'system').
            resource_type: Type of resource (e.g., 'chat_session').
            resource_id: ID of the resource.
            metadata: Additional metadata.
            user_id: Optional user ID.

        Returns:
            Created AuditLog instance.
        """
        log = AuditLog(
            id=uuid4(),
            action=action,
            actor=actor,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=metadata,
            user_id=user_id,
        )
        self.session.add(log)
        await self.session.flush()
        return log
