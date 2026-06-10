"""Admin API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Public audit log response."""

    id: UUID
    user_id: UUID | None
    actor: str
    action: str
    resource_type: str | None
    resource_id: UUID | None
    metadata: dict[str, object] | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Response for recent audit logs."""

    logs: list[AuditLogResponse]
    total: int


class AdminUserResponse(BaseModel):
    """User info for admin (no hashed_password)."""

    id: UUID
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AdminUserListResponse(BaseModel):
    """Response for admin user list."""

    users: list[AdminUserResponse]
    total: int


class AdminUserPatchRequest(BaseModel):
    """Request to update user by admin."""

    is_active: bool | None = None
    role: str | None = None


class AdminDocumentResponse(BaseModel):
    """Document info for admin."""

    id: UUID
    title: str
    filename: str
    file_type: str
    file_size: int
    status: str
    visibility: str
    user_id: UUID
    owner_email: str | None = None
    chunk_count: int | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class AdminDocumentListResponse(BaseModel):
    """Response for admin document list."""

    documents: list[AdminDocumentResponse]
    total: int


class AdminToolResponse(BaseModel):
    """Tool info for admin."""

    name: str
    description: str
    source: str | None = None
    required_role: str = "user"
    enabled: bool = True
    allowed_modes: list[str] | None = None
    requires_confirmation: bool = False
    server_name: str | None = None
    transport: str | None = None


class AdminToolListResponse(BaseModel):
    """Response for admin tool list."""

    tools: list[AdminToolResponse]
    total: int


class MCPServerStatusResponse(BaseModel):
    """MCP server status for admin."""

    name: str
    transport: str
    enabled: bool
    status: str  # "ok", "disabled", "unavailable"
    tool_count: int = 0
    required_role: str = "user"


class MCPServerListResponse(BaseModel):
    """Response for MCP server list."""

    servers: list[MCPServerStatusResponse]
    total: int


class AdminConfigResponse(BaseModel):
    """Safe config for admin display (no secrets)."""

    app_name: str
    app_version: str
    app_env: str
    auth_required: bool
    llm_provider: str
    embedding_provider: str
    rag_retrieval_mode: str
    rag_chunk_strategy: str
    rag_reranker_provider: str
    mcp_demo_enabled: bool


class AdminOverviewResponse(BaseModel):
    """Admin overview stats."""

    users_count: int
    documents_count: int
    chat_sessions_count: int
    messages_count: int
    audit_logs_count: int
    tools_count: int
    mcp_servers_count: int
    system_status: str


class AdminMetricsResponse(BaseModel):
    """Admin metrics."""

    requests_total: int
    chat_messages_total: int
    rag_queries_total: int
    tool_invocations_total: int
    react_runs_total: int
    plan_execute_runs_total: int
    documents_total: int
    audit_logs_total: int
    uptime_seconds: float


class AuditLogFilterParams(BaseModel):
    """Filter parameters for audit logs."""

    action: str | None = None
    user_id: UUID | None = None
    resource_type: str | None = None
