"""Chat service for business logic operations."""

import json
import re
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.plan_execute_agent import PlanExecuteAgent
from app.agents.plan_execute_schemas import PlanStep, StepResult
from app.agents.rag_agent import RAGAgent
from app.agents.react_agent import ReActAgent
from app.agents.react_schemas import ReActStep
from app.agents.schemas import Citation
from app.db.models import ChatMessage, ChatSession, User
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
    PlanStepResponse,
    ReActStepResponse,
    SendMessageResponse,
    SessionListResponse,
    SessionResponse,
    StepResultResponse,
)
from app.schemas.chat_result import ChatResult
from app.tools.service import ToolService

# Pattern: /tool <tool_name> <json_input>
_TOOL_PATTERN = re.compile(r"^/tool\s+(\S+)\s*(.*)$", re.DOTALL)

# Supported modes
_SUPPORTED_MODES = {"rag", "react", "plan_execute"}


def _parse_tool_command(content: str) -> tuple[str, dict[str, object]] | None:
    """Parse a /tool command from user message."""
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

    async def _resolve_user(self, user: User | None = None) -> User:
        """Resolve explicit authenticated user or fallback demo user."""
        if user is not None:
            return user
        return await self.user_repo.get_or_create_demo_user()

    @staticmethod
    def _is_owner(chat_session: ChatSession, user: User) -> bool:
        return chat_session.user_id == user.id

    async def create_session(
        self,
        title: str | None = None,
        user: User | None = None,
    ) -> SessionResponse:
        """Create a new chat session."""
        current_user = await self._resolve_user(user)
        chat_session = await self.session_repo.create(user_id=current_user.id, title=title)
        return SessionResponse(
            id=chat_session.id,
            title=chat_session.title,
            is_active=chat_session.is_active,
            created_at=chat_session.created_at,
            updated_at=chat_session.updated_at,
        )

    async def get_session(
        self,
        session_id: UUID,
        user: User | None = None,
    ) -> SessionResponse | None:
        """Get a chat session by ID."""
        current_user = await self._resolve_user(user)
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session or not self._is_owner(chat_session, current_user):
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
        user: User | None = None,
    ) -> SessionListResponse:
        """List all chat sessions for a user."""
        current_user = await self._resolve_user(user)
        sessions = await self.session_repo.get_all_by_user(
            user_id=current_user.id, limit=limit, offset=offset
        )
        total = await self.session_repo.count_by_user(current_user.id)
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
        user: User | None = None,
    ) -> MessageListResponse | None:
        """Get all messages for a session."""
        current_user = await self._resolve_user(user)
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session or not self._is_owner(chat_session, current_user):
            return None
        messages = await self.message_repo.get_all_by_session(
            session_id=session_id, limit=limit, offset=offset
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
        mode: str | None = None,
        user: User | None = None,
    ) -> SendMessageResponse | None:
        """Send a message to a session (non-streaming).

        Returns SendMessageResponse or None if session not found.
        """
        current_user = await self._resolve_user(user)
        result = await self.process_message(session_id, content, mode, user=current_user)
        if result is None:
            return None

        # Save assistant message
        assistant_message = await self.message_repo.create(
            session_id=session_id,
            role="assistant",
            content=result.answer,
            metadata=result.assistant_metadata,
        )

        return SendMessageResponse(
            user_message=result.user_message,
            assistant_message=_msg_to_response(assistant_message),
            citations=result.citations,
            trace_id=result.trace_id,
            steps=result.steps,
            tool_calls=result.tool_calls,
            mode=result.mode,
            plan=result.plan,
            step_results=result.step_results,
        )

    async def process_message(
        self,
        session_id: UUID,
        content: str,
        mode: str | None = None,
        user: User | None = None,
    ) -> ChatResult | None:
        """Process a message and return ChatResult.

        Shared by both streaming and non-streaming endpoints.

        Returns ChatResult or None if session not found.
        """
        # Validate mode
        if mode is not None and mode not in _SUPPORTED_MODES:
            raise ValueError(
                f"Unsupported mode: '{mode}'. Supported modes: {', '.join(sorted(_SUPPORTED_MODES))}"
            )

        current_user = await self._resolve_user(user)

        # Check if session exists and belongs to the current user.
        chat_session = await self.session_repo.get_by_id(session_id)
        if not chat_session or not self._is_owner(chat_session, current_user):
            return None

        # Create user message
        user_message = await self.message_repo.create(
            session_id=session_id,
            role="user",
            content=content,
        )

        user_msg_resp = _msg_to_response(user_message)

        # Priority 1: /tool command
        tool_parse = _parse_tool_command(content)
        if tool_parse is not None:
            return await self._process_tool_call(
                session_id=session_id,
                tool_name=tool_parse[0],
                tool_input=tool_parse[1],
                user_message=user_msg_resp,
                user=current_user,
            )

        # Priority 2: Plan-and-Execute mode
        if mode == "plan_execute":
            return await self._process_plan_execute_query(
                session_id=session_id,
                content=content,
                user_message=user_msg_resp,
                user=current_user,
            )

        # Priority 3: ReAct mode
        if mode == "react":
            return await self._process_react_query(
                session_id=session_id,
                content=content,
                user_message=user_msg_resp,
                user=current_user,
            )

        # Priority 4: Default RAG mode
        return await self._process_rag_query(
            session_id=session_id,
            content=content,
            user_message=user_msg_resp,
            user=current_user,
        )

    async def _process_tool_call(
        self,
        session_id: UUID,
        tool_name: str,
        tool_input: dict[str, object],
        user_message: MessageResponse,
        user: User,
    ) -> ChatResult:
        """Process a /tool command invocation."""
        tool_service = ToolService(self.session, current_user=user)
        result = await tool_service.invoke_tool(
            tool_name=tool_name,
            input_data=tool_input,
            actor=user.email,
            session_id=session_id,
        )

        if result.status == "success":
            answer = f"[Tool: {result.tool_name}] {json.dumps(result.output, ensure_ascii=False, default=str)}"
        else:
            answer = f"[Tool: {result.tool_name}] Error: {result.error}"

        assistant_metadata = {
            "tool_call": {
                "tool_name": result.tool_name,
                "status": result.status,
                "trace_id": result.trace_id,
                "latency_ms": result.latency_ms,
            },
            "trace_id": result.trace_id,
        }

        return ChatResult(
            user_message=user_message,
            answer=answer,
            trace_id=result.trace_id,
            mode="tool",
            tool_calls=[
                {
                    "tool_name": result.tool_name,
                    "status": result.status,
                    "output": result.output if result.status == "success" else None,
                    "error": result.error if result.status != "success" else None,
                }
            ],
            assistant_metadata=assistant_metadata,
            session_id=session_id,
        )

    async def _process_plan_execute_query(
        self,
        session_id: UUID,
        content: str,
        user_message: MessageResponse,
        user: User,
    ) -> ChatResult:
        """Process a Plan-and-Execute mode query."""
        agent = PlanExecuteAgent(session=self.session, current_user=user)
        result = await agent.query(content, session_id=session_id)

        plan_responses = [
            PlanStepResponse(
                step_index=s.step_index,
                description=s.description,
                action_type=s.action_type,
                tool_name=s.tool_name,
                tool_input=s.tool_input,
                status=s.status,
            )
            for s in result.plan
        ]

        step_result_responses = [
            StepResultResponse(
                step_index=sr.step_index,
                status=sr.status,
                output=sr.output,
                error=sr.error,
                latency_ms=sr.latency_ms,
                tool_name=sr.tool_name,
                citations=sr.citations,
            )
            for sr in result.step_results
        ]

        citation_responses = [
            CitationResponse(
                document_id=c["document_id"],
                document_title=c["document_title"],
                chunk_id=c["chunk_id"],
                chunk_index=c["chunk_index"],
                score=c["score"],
                snippet=c["snippet"],
            )
            for c in result.citations
        ]

        assistant_metadata = {
            "mode": "plan_execute",
            "trace_id": result.trace_id,
            "plan": [_plan_step_to_dict(s) for s in result.plan],
            "step_results": [_step_result_to_dict(sr) for sr in result.step_results],
            "tool_calls": result.tool_calls,
            "citations": result.citations,
            "final_status": result.final_status,
        }

        return ChatResult(
            user_message=user_message,
            answer=result.answer,
            citations=citation_responses,
            trace_id=result.trace_id,
            plan=plan_responses,
            step_results=step_result_responses,
            tool_calls=result.tool_calls,
            mode="plan_execute",
            assistant_metadata=assistant_metadata,
            session_id=session_id,
        )

    async def _process_react_query(
        self,
        session_id: UUID,
        content: str,
        user_message: MessageResponse,
        user: User,
    ) -> ChatResult:
        """Process a ReAct mode query."""
        agent = ReActAgent(session=self.session, current_user=user)
        result = await agent.query(content, session_id=session_id)

        step_responses = [
            ReActStepResponse(
                step_index=s.step_index,
                thought=s.thought,
                action=s.action,
                action_input=s.action_input,
                observation=s.observation,
                status=s.status,
                tool_name=s.tool_name,
                latency_ms=s.latency_ms,
            )
            for s in result.steps
        ]

        citation_responses = [
            CitationResponse(
                document_id=c["document_id"],
                document_title=c["document_title"],
                chunk_id=c["chunk_id"],
                chunk_index=c["chunk_index"],
                score=c["score"],
                snippet=c["snippet"],
            )
            for c in result.citations
        ]

        assistant_metadata = {
            "mode": "react",
            "trace_id": result.trace_id,
            "steps": [_step_to_dict(s) for s in result.steps],
            "tool_calls": result.tool_calls,
            "citations": result.citations,
        }

        return ChatResult(
            user_message=user_message,
            answer=result.answer,
            citations=citation_responses,
            trace_id=result.trace_id,
            steps=step_responses,
            tool_calls=result.tool_calls,
            mode="react",
            assistant_metadata=assistant_metadata,
            session_id=session_id,
        )

    async def _process_rag_query(
        self,
        session_id: UUID,
        content: str,
        user_message: MessageResponse,
        user: User,
    ) -> ChatResult:
        """Process a normal RAG query."""
        agent = RAGAgent(session=self.session, user_id=user.id)
        result = await agent.query(content)

        assistant_metadata = {
            "citations": [_citation_to_dict(c) for c in result.citations],
            "trace_id": result.trace_id,
        }

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
            user_id=user.id,
        )

        return ChatResult(
            user_message=user_message,
            answer=result.answer,
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
            mode="rag",
            assistant_metadata=assistant_metadata,
            session_id=session_id,
        )


def _msg_to_response(msg: ChatMessage) -> MessageResponse:
    """Convert ChatMessage to MessageResponse."""
    return MessageResponse(
        id=msg.id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        token_count=msg.token_count,
        created_at=msg.created_at,
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


def _step_to_dict(step: ReActStep) -> dict[str, object]:
    """Convert a ReActStep to a dictionary for metadata storage."""
    result: dict[str, object] = {
        "step_index": step.step_index,
        "thought": step.thought,
        "action": step.action,
        "action_input": step.action_input,
        "observation": step.observation,
        "status": step.status,
    }
    if step.tool_name is not None:
        result["tool_name"] = step.tool_name
    if step.latency_ms is not None:
        result["latency_ms"] = step.latency_ms
    return result


def _plan_step_to_dict(step: PlanStep) -> dict[str, object]:
    """Convert a PlanStep to a dictionary for metadata storage."""
    result: dict[str, object] = {
        "step_index": step.step_index,
        "description": step.description,
        "action_type": step.action_type,
        "tool_input": step.tool_input,
        "status": step.status,
    }
    if step.tool_name is not None:
        result["tool_name"] = step.tool_name
    return result


def _step_result_to_dict(sr: StepResult) -> dict[str, object]:
    """Convert a StepResult to a dictionary for metadata storage."""
    result: dict[str, object] = {
        "step_index": sr.step_index,
        "status": sr.status,
        "output": sr.output,
    }
    if sr.error is not None:
        result["error"] = sr.error
    if sr.latency_ms is not None:
        result["latency_ms"] = sr.latency_ms
    if sr.tool_name is not None:
        result["tool_name"] = sr.tool_name
    if sr.citations:
        result["citations"] = sr.citations
    return result
