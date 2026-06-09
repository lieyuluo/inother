"""Chat API request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Request schemas
class CreateSessionRequest(BaseModel):
    """Request schema for creating a new chat session."""

    title: str | None = Field(default=None, max_length=255, description="Optional title for the session")


class SendMessageRequest(BaseModel):
    """Request schema for sending a message to a session."""

    content: str = Field(min_length=1, description="Message content, cannot be empty")


# Response schemas
class SessionResponse(BaseModel):
    """Response schema for a chat session."""

    id: UUID
    title: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None


class SessionListResponse(BaseModel):
    """Response schema for a list of chat sessions."""

    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """Response schema for a chat message."""

    id: UUID
    session_id: UUID
    role: str
    content: str
    token_count: int | None
    created_at: datetime


class MessageListResponse(BaseModel):
    """Response schema for a list of chat messages."""

    messages: list[MessageResponse]
    total: int


class SendMessageResponse(BaseModel):
    """Response schema for sending a message (includes user and assistant messages)."""

    user_message: MessageResponse
    assistant_message: MessageResponse