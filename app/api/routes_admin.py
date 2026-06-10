"""Admin API routes: overview, users, documents, tools, mcp-servers, config, metrics, audit-logs."""

from __future__ import annotations

import time as time_mod
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import require_admin
from app.db.models import AuditLog, ChatMessage, ChatSession, Document, DocumentChunk, User
from app.db.session import get_db_session
from app.mcp.server_config import load_mcp_server_configs
from app.schemas.admin import (
    AdminConfigResponse,
    AdminDocumentListResponse,
    AdminDocumentResponse,
    AdminMetricsResponse,
    AdminOverviewResponse,
    AdminToolListResponse,
    AdminToolResponse,
    AdminUserListResponse,
    AdminUserPatchRequest,
    AdminUserResponse,
    AuditLogListResponse,
    AuditLogResponse,
    MCPServerListResponse,
    MCPServerStatusResponse,
)
from app.tools.builtin import create_builtin_tools
from app.tools.registry import ToolRegistry

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Track app start time for uptime
_start_time = time_mod.monotonic()


@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminOverviewResponse:
    """Get system overview stats (admin only)."""
    users_count = (await session.execute(select(func.count(User.id)))).scalar_one() or 0
    documents_count = (
        await session.execute(select(func.count(Document.id)).where(Document.status != "deleted"))
    ).scalar_one() or 0
    chat_sessions_count = (
        await session.execute(select(func.count(ChatSession.id)))
    ).scalar_one() or 0
    messages_count = (await session.execute(select(func.count(ChatMessage.id)))).scalar_one() or 0
    audit_logs_count = (await session.execute(select(func.count(AuditLog.id)))).scalar_one() or 0

    # Count tools
    registry = ToolRegistry()
    for tool in create_builtin_tools(session, user_id=None):
        registry.register(tool)
    from app.mcp.tool_adapter import create_mcp_tools

    for tool in create_mcp_tools():
        registry.register(tool)
    tools_count = len(registry.list_tools())

    # Count MCP servers
    mcp_configs = load_mcp_server_configs()
    mcp_servers_count = len(mcp_configs)

    return AdminOverviewResponse(
        users_count=users_count,
        documents_count=documents_count,
        chat_sessions_count=chat_sessions_count,
        messages_count=messages_count,
        audit_logs_count=audit_logs_count,
        tools_count=tools_count,
        mcp_servers_count=mcp_servers_count,
        system_status="ok",
    )


@router.get("/users", response_model=AdminUserListResponse)
async def admin_list_users(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUserListResponse:
    """List all users (admin only). No hashed_password in response."""
    stmt = select(User).order_by(desc(User.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    users = list(result.scalars().all())

    count_stmt = select(func.count(User.id))
    total = (await session.execute(count_stmt)).scalar_one() or 0

    return AdminUserListResponse(
        users=[AdminUserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def admin_patch_user(
    user_id: UUID,
    request: AdminUserPatchRequest,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUserResponse:
    """Update user is_active or role (admin only)."""
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if request.is_active is not None:
        user.is_active = request.is_active
    if request.role is not None:
        if request.role not in ("user", "admin"):
            raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
        user.role = request.role

    user.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(user)

    return AdminUserResponse.model_validate(user)


@router.get("/documents", response_model=AdminDocumentListResponse)
async def admin_list_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminDocumentListResponse:
    """List all documents (admin only)."""
    stmt = (
        select(Document)
        .where(Document.status != "deleted")
        .order_by(desc(Document.created_at))
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    documents = list(result.scalars().all())

    total = (
        await session.execute(select(func.count(Document.id)).where(Document.status != "deleted"))
    ).scalar_one() or 0

    doc_responses = []
    for doc in documents:
        # Get owner email
        owner = (
            await session.execute(select(User).where(User.id == doc.user_id))
        ).scalar_one_or_none()
        # Get chunk count
        chunk_count = (
            await session.execute(
                select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
            )
        ).scalar_one() or 0

        doc_responses.append(
            AdminDocumentResponse(
                id=doc.id,
                title=doc.title,
                filename=doc.filename,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                visibility=doc.visibility,
                user_id=doc.user_id,
                owner_email=owner.email if owner else None,
                chunk_count=chunk_count,
                created_at=doc.created_at,
            )
        )

    return AdminDocumentListResponse(documents=doc_responses, total=total)


@router.get("/tools", response_model=AdminToolListResponse)
async def admin_list_tools(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminToolListResponse:
    """List all tools with permission info (admin only)."""
    registry = ToolRegistry()
    for tool in create_builtin_tools(session, user_id=None):
        registry.register(tool)
    from app.mcp.tool_adapter import create_mcp_tools

    for tool in create_mcp_tools():
        registry.register(tool)

    tools = registry.list_tools()
    tool_responses = [
        AdminToolResponse(
            name=tool.name,
            description=tool.description,
            source=tool.source,
            required_role=tool.required_role,
            enabled=tool.enabled,
            allowed_modes=tool.allowed_modes,
            requires_confirmation=tool.requires_confirmation,
            server_name=tool.server_name,
            transport=tool.transport,
        )
        for tool in tools
    ]

    return AdminToolListResponse(tools=tool_responses, total=len(tool_responses))


@router.get("/mcp-servers", response_model=MCPServerListResponse)
async def admin_list_mcp_servers(
    admin: User = Depends(require_admin),
) -> MCPServerListResponse:
    """List MCP server configs and health (admin only)."""
    configs = load_mcp_server_configs()

    server_responses = []
    for config in configs:
        status_str = "ok" if config.enabled else "disabled"
        # Count tools from this server
        tool_count = 0
        try:
            from app.mcp.manager import MCPManager

            manager = MCPManager(configs=[config])
            manager.initialize()
            tool_count = len(manager.list_all_tools())
        except Exception:
            status_str = "unavailable"

        server_responses.append(
            MCPServerStatusResponse(
                name=config.name,
                transport=config.transport,
                enabled=config.enabled,
                status=status_str,
                tool_count=tool_count,
                required_role=config.required_role,
            )
        )

    return MCPServerListResponse(servers=server_responses, total=len(server_responses))


@router.get("/config", response_model=AdminConfigResponse)
async def admin_get_config(
    admin: User = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> AdminConfigResponse:
    """Get safe config (admin only). No secrets exposed."""
    return AdminConfigResponse(
        app_name=settings.app_name,
        app_version=settings.app_version,
        app_env=settings.app_env,
        auth_required=settings.auth_required,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        rag_retrieval_mode=settings.rag_retrieval_mode,
        rag_chunk_strategy=settings.rag_chunk_strategy,
        rag_reranker_provider=settings.rag_reranker_provider,
        mcp_demo_enabled=settings.mcp_demo_enabled,
    )


@router.get("/metrics", response_model=AdminMetricsResponse)
async def admin_metrics(
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AdminMetricsResponse:
    """Get system metrics (admin only). Lightweight, not production-grade monitoring."""
    chat_messages_total = (
        await session.execute(select(func.count(ChatMessage.id)))
    ).scalar_one() or 0
    documents_total = (
        await session.execute(select(func.count(Document.id)).where(Document.status != "deleted"))
    ).scalar_one() or 0
    audit_logs_total = (await session.execute(select(func.count(AuditLog.id)))).scalar_one() or 0

    # Count by action type
    rag_queries_total = (
        await session.execute(select(func.count(AuditLog.id)).where(AuditLog.action == "rag.query"))
    ).scalar_one() or 0
    tool_invocations_total = (
        await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.action == "tool.invoke")
        )
    ).scalar_one() or 0
    react_runs_total = (
        await session.execute(select(func.count(AuditLog.id)).where(AuditLog.action == "react.run"))
    ).scalar_one() or 0
    plan_execute_runs_total = (
        await session.execute(
            select(func.count(AuditLog.id)).where(AuditLog.action == "plan_execute.run")
        )
    ).scalar_one() or 0

    uptime_seconds = time_mod.monotonic() - _start_time

    return AdminMetricsResponse(
        requests_total=0,  # Not tracked in this lightweight implementation
        chat_messages_total=chat_messages_total,
        rag_queries_total=rag_queries_total,
        tool_invocations_total=tool_invocations_total,
        react_runs_total=react_runs_total,
        plan_execute_runs_total=plan_execute_runs_total,
        documents_total=documents_total,
        audit_logs_total=audit_logs_total,
        uptime_seconds=round(uptime_seconds, 1),
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def admin_list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action: str | None = Query(default=None),
    user_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> AuditLogListResponse:
    """List audit logs with optional filters (admin only)."""
    stmt = select(AuditLog)

    if action:
        stmt = stmt.where(AuditLog.action == action)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    total_stmt = select(func.count(AuditLog.id))
    if action:
        total_stmt = total_stmt.where(AuditLog.action == action)
    if user_id:
        total_stmt = total_stmt.where(AuditLog.user_id == user_id)
    if resource_type:
        total_stmt = total_stmt.where(AuditLog.resource_type == resource_type)

    total = (await session.execute(total_stmt)).scalar_one() or 0

    stmt = stmt.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
    result = await session.execute(stmt)
    logs = list(result.scalars().all())

    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                actor=log.actor,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                metadata=log.meta if isinstance(log.meta, dict) else None,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=total,
    )
