"""Chat API routes for session and message operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.chat import (
    CreateSessionRequest,
    MessageListResponse,
    SendMessageRequest,
    SendMessageResponse,
    SessionListResponse,
    SessionResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# Dependency for database session
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
    description="Create a new chat session. If title is not provided, defaults to 'New Chat'.",
)
async def create_session(
    request: CreateSessionRequest,
    session: DBSession,
) -> SessionResponse:
    """Create a new chat session."""
    service = ChatService(session)
    return await service.create_session(title=request.title)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all chat sessions",
    description="Get all chat sessions for the current user, ordered by created_at descending.",
)
async def list_sessions(
    session: DBSession,
    limit: int = 100,
    offset: int = 0,
) -> SessionListResponse:
    """List all chat sessions."""
    service = ChatService(session)
    return await service.list_sessions(limit=limit, offset=offset)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a chat session",
    description="Get a specific chat session by ID. Returns 404 if not found.",
)
async def get_session(
    session_id: UUID,
    session: DBSession,
) -> SessionResponse:
    """Get a chat session by ID."""
    service = ChatService(session)
    result = await service.get_session(session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with id '{session_id}' not found",
        )
    return result


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get messages for a session",
    description="Get all messages for a chat session, ordered by created_at ascending. Returns 404 if session not found.",
)
async def get_messages(
    session_id: UUID,
    session: DBSession,
    limit: int = 100,
    offset: int = 0,
) -> MessageListResponse:
    """Get messages for a chat session."""
    service = ChatService(session)
    result = await service.get_messages(session_id, limit=limit, offset=offset)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with id '{session_id}' not found",
        )
    return result


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a message to a session",
    description="Send a user message to a chat session and receive a mock assistant response. Returns 404 if session not found.",
)
async def send_message(
    session_id: UUID,
    request: SendMessageRequest,
    session: DBSession,
) -> SendMessageResponse:
    """Send a message to a chat session."""
    service = ChatService(session)
    try:
        result = await service.send_message(session_id, content=request.content, mode=request.mode)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat session with id '{session_id}' not found",
        )
    return result
