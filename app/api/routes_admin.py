"""Admin-only API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.models import User
from app.db.repositories import AuditLogRepository, DocumentRepository
from app.db.session import get_db_session
from app.schemas.admin import AuditLogListResponse, AuditLogResponse
from app.schemas.document import DocumentListResponse, DocumentResponse

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


@router.get("/documents", response_model=DocumentListResponse)
async def list_all_documents(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentListResponse:
    """List all documents (admin only)."""
    doc_repo = DocumentRepository(session)
    documents = await doc_repo.get_all(limit=limit, offset=offset)
    total = await doc_repo.count_all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                title=d.title,
                filename=d.filename,
                file_type=d.file_type,
                file_size=d.file_size,
                status=d.status,
                visibility=d.visibility,
                chunk_count=(d.meta or {}).get("chunk_count"),
                user_id=d.user_id,
                parser_name=(d.meta or {}).get("parser_name"),
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in documents
        ],
        total=total,
    )
