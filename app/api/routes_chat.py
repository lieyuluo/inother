"""Chat API routes including SSE streaming endpoint."""

import json
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.provider_errors import (
    ProviderConfigError,
    ProviderError,
    ProviderResponseError,
    ProviderTimeoutError,
)
from app.core.security import get_request_user
from app.db.models import User
from app.db.session import get_db_session
from app.schemas.chat import (
    CreateSessionRequest,
    MessageListResponse,
    SendMessageRequest,
    SessionListResponse,
    SessionResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _sse_event(event: str, data: object) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


def _chunk_answer(answer: str, chunk_size: int = 5) -> list[str]:
    """Split answer into chunks for simulated token streaming.

    Since fake provider doesn't stream real tokens, we simulate
    by splitting the answer into small chunks.
    """
    if not answer:
        return []
    chunks = []
    for i in range(0, len(answer), chunk_size):
        chunks.append(answer[i : i + chunk_size])
    return chunks


# -- Session endpoints --------------------------------------------------


@router.post("/sessions", status_code=status.HTTP_201_CREATED, response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> SessionResponse:
    """Create a new chat session."""
    service = ChatService(session)
    title = request.title if request else None
    result = await service.create_session(title=title, user=current_user)
    return result


@router.get("/sessions")
async def list_sessions(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> SessionListResponse:
    """List all chat sessions."""
    service = ChatService(session)
    return await service.list_sessions(user=current_user)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> object:
    """Get a chat session by ID."""
    service = ChatService(session)
    result = await service.get_session(session_id, user=current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> MessageListResponse:
    """Get messages for a session."""
    service = ChatService(session)
    result = await service.get_messages(session_id, user=current_user)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


# -- Non-streaming message endpoint ------------------------------------


@router.post("/sessions/{session_id}/messages", status_code=status.HTTP_201_CREATED)
async def send_message(
    session_id: UUID,
    request: SendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> object:
    """Send a message to a session (non-streaming)."""
    service = ChatService(session)
    try:
        result = await service.send_message(
            session_id,
            content=request.content,
            mode=request.mode,
            user=current_user,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


# -- SSE Streaming message endpoint ------------------------------------


@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: UUID,
    request: SendMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_request_user),
) -> StreamingResponse:
    """Send a message to a session with SSE streaming."""
    service = ChatService(session)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            result = await service.process_message(
                session_id,
                request.content,
                request.mode,
                user=current_user,
            )
        except ValueError as e:
            yield _sse_event("error", {"error": str(e)})
            return
        except ProviderError as e:
            yield _sse_event("error", {"error": _provider_error_message(e)})
            return
        except Exception:
            yield _sse_event("error", {"error": "Internal server error"})
            return

        if result is None:
            yield _sse_event("error", {"error": "Session not found"})
            return

        # 1. trace event
        yield _sse_event("trace", {"trace_id": result.trace_id})

        # 2. user_message event
        yield _sse_event("user_message", result.user_message.model_dump(mode="json"))

        # 3. token events (simulated streaming)
        chunks = _chunk_answer(result.answer)
        for chunk in chunks:
            yield _sse_event("token", {"content": chunk})

        # 4. citations event
        if result.citations:
            yield _sse_event(
                "citations",
                [c.model_dump(mode="json") for c in result.citations],
            )

        # 5. steps event (ReAct)
        if result.steps:
            yield _sse_event(
                "steps",
                [s.model_dump(mode="json") for s in result.steps],
            )

        # 6. plan event (Plan-Execute)
        if result.plan:
            yield _sse_event(
                "plan",
                [p.model_dump(mode="json") for p in result.plan],
            )

        # 7. step_results event (Plan-Execute)
        if result.step_results:
            yield _sse_event(
                "step_results",
                [sr.model_dump(mode="json") for sr in result.step_results],
            )

        # 8. tool_calls event
        if result.tool_calls:
            yield _sse_event("tool_calls", result.tool_calls)

        # 9. Save assistant message and emit
        from app.db.repositories import ChatMessageRepository
        from app.services.chat_service import _msg_to_response

        msg_repo = ChatMessageRepository(session)
        assistant_message = await msg_repo.create(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            metadata=result.assistant_metadata,
        )

        assistant_msg_resp = _msg_to_response(assistant_message)
        yield _sse_event("assistant_message", assistant_msg_resp.model_dump(mode="json"))

        # 10. done event
        yield _sse_event("done", {"status": "ok"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _provider_error_message(exc: ProviderError) -> str:
    if isinstance(exc, ProviderConfigError):
        return "AI 服务配置错误，请联系管理员检查 API Key、模型名称或 Base URL。"
    if isinstance(exc, ProviderTimeoutError):
        return "AI 服务响应超时，请稍后重试。"
    if isinstance(exc, ProviderResponseError):
        return "AI 服务返回异常，请检查模型、额度、Base URL，或稍后重试。"
    return "AI 服务暂时不可用，请稍后重试。"
