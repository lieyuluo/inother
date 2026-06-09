"""Chat service for business logic operations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import ChatMessageRepository, ChatSessionRepository, UserRepository
from app.schemas.chat import (
    MessageListResponse,
    MessageResponse,
    SendMessageResponse,
    SessionListResponse,
    SessionResponse,
)


class ChatService:
    """Service for chat session and message operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.session_repo = ChatSessionRepository(session)
        self.message_repo = ChatMessageRepository(session)

    async def create_session(self, title: str | None = None) -> SessionResponse:
        """Create a new chat session.

        Uses a demo user for Phase 2 development.
        """
        # Get or create demo user
        user = await self.user_repo.get_or_create_demo_user()

        # Create session
        chat_session = await self.session_repo.create(
            user_id=user.id,
            title=title,
        )

        return SessionResponse(
            id=chat_session.id,
            title=chat_session.title,
            is_active=chat_session.is_active,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
        )

    async def get_session(self, session_id: UUID) -> SessionResponse | None:
        """Get a chat session by ID."""
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session:
            return None

        return SessionResponse(
            id=chat_session.id,
            title=chat_session.title,
            is_active=chat_session.is_active,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
        )

    async def list_sessions(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> SessionListResponse:
        """List all chat sessions for the demo user."""
        # Get demo user
        user = await self.user_repo.get_or_create_demo_user()

        # Get sessions
        sessions = await self.session_repo.get_all_by_user(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )
        total = await self.session_repo.count_by_user(user.id)

        return SessionListResponse(
            sessions=[
                SessionResponse(
                    id=s.id,
                    title=s.title,
                    is_active=s.is_active,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in sessions
            ],
            total=total,
        )

    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> MessageListResponse | None:
        """Get all messages for a session.

        Returns None if session doesn't exist.
        """
        # Check if session exists
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session:
            return None

        # Get messages
        messages = await self.message_repo.get_all_by_session(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
        total = await self.message_repo.count_by_session(session_id)

        return MessageListResponse(
            messages=[
                MessageResponse(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    token_count=m.token_count,
                    created_at=m.created_at,
                )
                for m in messages
            ],
            total=total,
        )

    async def send_message(
        self,
        session_id: UUID,
        content: str,
    ) -> SendMessageResponse | None:
        """Send a message to a session and get mock assistant response.

        Returns None if session doesn't exist.
        """
        # Check if session exists
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session:
            return None

        # Create user message
        user_message = await self.message_repo.create(
            session_id=session_id,
            role="user",
            content=content,
        )

        # Generate mock assistant response
        assistant_content = self._generate_mock_response(content)

        # Create assistant message
        assistant_message = await self.message_repo.create(
            session_id=session_id,
            role="assistant",
            content=assistant_content,
        )

        return SendMessageResponse(
            user_message=MessageResponse(
                id=user_message.id,
                session_id=user_message.session_id,
                role=user_message.role,
                content=user_message.content,
                token_count=user_message.token_count,
                created_at=user_message.created_at,
            ),
            assistant_message=MessageResponse(
                id=assistant_message.id,
                session_id=assistant_message.session_id,
                role=assistant_message.role,
                content=assistant_message.content,
                token_count=assistant_message.token_count,
                created_at=assistant_message.created_at,
            ),
        )

    def _generate_mock_response(self, user_content: str) -> str:
        """Generate a mock assistant response.

        This is a placeholder for Phase 2. In future phases, this will be replaced
        with actual LLM integration.

        The mock response format is stable and predictable for testing:
        "Echo: {user_content}"
        """
        return f"Echo: {user_content}"
