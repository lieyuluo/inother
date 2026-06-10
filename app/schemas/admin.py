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


class AuditLogListResponse(BaseModel):
    """Response for recent audit logs."""

    logs: list[AuditLogResponse]
    total: int
