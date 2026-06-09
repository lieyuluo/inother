"""Document API routes for document management operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentListResponse,
    DocumentResponse,
    UploadResponse,
)
from app.services.document_service import DocumentService

router = APIRouter(prefix="/api/documents", tags=["Documents"])

# Dependency for database session
DBSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Upload a .txt or .md document for processing and ingestion.",
)
async def upload_document(
    file: Annotated[UploadFile, File(description="Document file (.txt or .md)")],
    session: DBSession,
    title: Annotated[str | None, Form()] = None,
) -> UploadResponse:
    """Upload and process a document.

    Supported file types: .txt, .md

    The document will be:
    1. Validated for file type
    2. Parsed for text content
    3. Chunked into smaller pieces
    4. Embedded with FakeEmbeddingProvider
    5. Stored in database with status='ready'
    """
    service = DocumentService(session)

    # Read file content
    content = await file.read()

    # Get filename
    filename = file.filename or "unknown"

    try:
        result = await service.upload_document(
            filename=filename,
            content=content,
            title=title,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="Get all documents for the current user, ordered by created_at descending. Excludes deleted documents.",
)
async def list_documents(
    session: DBSession,
    limit: int = 100,
    offset: int = 0,
) -> DocumentListResponse:
    """List all documents."""
    service = DocumentService(session)
    return await service.list_documents(limit=limit, offset=offset)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get a document",
    description="Get a specific document by ID. Returns 404 if not found or deleted.",
)
async def get_document(
    document_id: UUID,
    session: DBSession,
) -> DocumentResponse:
    """Get a document by ID."""
    service = DocumentService(session)
    result = await service.get_document(document_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id '{document_id}' not found",
        )
    return result


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document chunks",
    description="Get all chunks for a document, ordered by chunk_index ascending. Returns 404 if document not found.",
)
async def get_document_chunks(
    document_id: UUID,
    session: DBSession,
    limit: int = 100,
    offset: int = 0,
) -> DocumentChunkListResponse:
    """Get chunks for a document."""
    service = DocumentService(session)
    result = await service.get_document_chunks(
        document_id=document_id,
        limit=limit,
        offset=offset,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id '{document_id}' not found",
        )
    return result


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
    description="Soft delete a document by setting status to 'deleted'. Returns 404 if not found.",
)
async def delete_document(
    document_id: UUID,
    session: DBSession,
) -> None:
    """Soft delete a document."""
    service = DocumentService(session)
    deleted = await service.delete_document(document_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id '{document_id}' not found",
        )
