"""Chat service for business logic operations."""

import json
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rag_agent import RAGAgent
from app.agents.schemas import Citation
from app.db.models import ChatMessage
from app.db.repositories import (
    AuditLogRepository,
    ChatMessageRepository,
    ChatSessionRepository,
    UserRepository,
)
from app.schemas.chat import (
    CitationResponse,
    MessageListResponse,
    MessageResponse,
    SendMessageResponse,
    SessionListResponse,
    SessionResponse,
)
from app.tools.service import ToolService

# Pattern: /tool <tool_name> <json_input>
_TOOL_PATTERN = re.compile(r"^/tool\s+(\S+)\s*(.*)$", re.DOTALL)


def _parse_tool_command(content: str) -> tuple[str, dict[str, object]] | None:
    """Parse a /tool command from user message.

    Args:
        content: User message content.

    Returns:
        Tuple of (tool_name, input_data) if valid /tool command, None otherwise.
    """
    match = _TOOL_PATTERN.match(content.strip())
    if not match:
        return None

    tool_name = match.group(1)
    json_str = match.group(2).strip()

    if not json_str:
        return (tool_name, {})

    try:
        input_data = json.loads(json_str)
        if not isinstance(input_data, dict):
            return None
        return (tool_name, input_data)
    except json.JSONDecodeError:
        return None


class ChatService:
    """Service for chat session and message operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.session_repo = ChatSessionRepository(session)
        self.message_repo = ChatMessageRepository(session)
        self.audit_repo = AuditLogRepository(session)

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
        """Send a message to a session and get RAG-powered or tool-invoked response.

        If the message starts with /tool, it triggers tool invocation.
        Otherwise, it goes through the RAG Agent.

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

        # Check if this is a /tool command
        tool_parse = _parse_tool_command(content)
        if tool_parse is not None:
            return await self._handle_tool_call(
                session_id=session_id,
                tool_name=tool_parse[0],
                tool_input=tool_parse[1],
                user_message=user_message,
            )

        # Default: RAG Agent flow
        return await self._handle_rag_query(
            session_id=session_id,
            content=content,
            user_message=user_message,
        )

    async def _handle_tool_call(
        self,
        session_id: UUID,
        tool_name: str,
        tool_input: dict[str, object],
        user_message: ChatMessage,
    ) -> SendMessageResponse:
        """Handle a /tool command invocation.

        Args:
            session_id: Chat session ID.
            tool_name: Tool to invoke.
            tool_input: Input for the tool.
            user_message: The user message record.

        Returns:
            SendMessageResponse with tool result.
        """
        tool_service = ToolService(self.session)
        result = await tool_service.invoke_tool(
            tool_name=tool_name,
            input_data=tool_input,
            actor="system",
            session_id=session_id,
        )

        # Format assistant response
        if result.status == "success":
            answer = f"[Tool: {result.tool_name}] {json.dumps(result.output, ensure_ascii=False, default=str)}"
        else:
            answer = f"[Tool: {result.tool_name}] Error: {result.error}"

        # Create assistant message with tool_call metadata
        assistant_metadata = {
            "tool_call": {
                "tool_name": result.tool_name,
                "status": result.status,
                "trace_id": result.trace_id,
                "latency_ms": result.latency_ms,
            },
            "trace_id": result.trace_id,
        }
        assistant_message = await self.message_repo.create(
            session_id=session_id,
            role="assistant",
            content=answer,
            metadata=assistant_metadata,
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
            citations=[],  # Tool calls have no citations
            trace_id=result.trace_id,
        )

    async def _handle_rag_query(
        self,
        session_id: UUID,
        content: str,
        user_message: ChatMessage,
    ) -> SendMessageResponse:
        """Handle a normal RAG query.

        Args:
            session_id: Chat session ID.
            content: User question.
            user_message: The user message record.

        Returns:
            SendMessageResponse with RAG answer and citations.
        """
        # Run RAG Agent
        agent = RAGAgent(session=self.session)
        result = await agent.query(content)

        # Create assistant message with citations metadata
        assistant_metadata = {
            "citations": [_citation_to_dict(c) for c in result.citations],
            "trace_id": result.trace_id,
        }
        assistant_message = await self.message_repo.create(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            metadata=assistant_metadata,
        )

        # Write AuditLog
        await self.audit_repo.create(
            action="rag.query",
            actor="system",
            resource_type="chat_session",
            resource_id=session_id,
            metadata={
                "trace_id": result.trace_id,
                "query": content,
                "top_k": agent.retriever.top_k,
                "citations_count": len(result.citations),
                "used_fallback": result.used_fallback,
            },
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
            citations=[
                CitationResponse(
                    document_id=c.document_id,
                    document_title=c.document_title,
                    chunk_id=c.chunk_id,
                    chunk_index=c.chunk_index,
                    score=c.score,
                    snippet=c.snippet,
                )
                for c in result.citations
            ],
            trace_id=result.trace_id,
        )


def _citation_to_dict(citation: Citation) -> dict[str, object]:
    """Convert a Citation to a dictionary for metadata storage."""
    return {
        "document_id": citation.document_id,
        "document_title": citation.document_title,
        "chunk_id": citation.chunk_id,
        "chunk_index": citation.chunk_index,
        "score": citation.score,
        "snippet": citation.snippet,
    }
