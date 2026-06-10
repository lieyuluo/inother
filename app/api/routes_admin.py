"""Admin-only API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.models import User
from app.db.repositories import AuditLogRepository
from app.db.session import get_db_session
from app.schemas.admin import AuditLogListResponse, AuditLogResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
) -> AuditLogListResponse:
    """Return recent audit logs for admins."""
    logs = await AuditLogRepository(session).list_recent(limit=limit)
    return AuditLogListResponse(
        logs=[
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                actor=log.actor,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                metadata=log.meta,
                created_at=log.created_at,
            )
            for log in logs
        ],
        total=len(logs),
    )
