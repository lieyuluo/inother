"""Document API request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# Response schemas
class DocumentResponse(BaseModel):
    """Response schema for a document."""

    id: UUID
    title: str
    filename: str
    file_type: str
    file_size: int
    status: str
    visibility: str = "private"
    chunk_count: int | None = None
    user_id: UUID | None = None
    parser_name: str | None = None
    created_at: datetime
    updated_at: datetime | None


class DocumentListResponse(BaseModel):
    """Response schema for a list of documents."""

    documents: list[DocumentResponse]
    total: int


class DocumentChunkResponse(BaseModel):
    """Response schema for a document chunk.

    Note: embedding is not included in API responses to avoid large payloads.
    """

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    token_count: int | None
    start_char: int | None = None
    end_char: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    created_at: datetime
    updated_at: datetime | None


class DocumentChunkListResponse(BaseModel):
    """Response schema for a list of document chunks."""

    chunks: list[DocumentChunkResponse]
    total: int


class UploadResponse(BaseModel):
    """Response schema for document upload."""

    document: DocumentResponse
    chunks_count: int
