"""Document service for business logic operations."""

import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.repositories import (
    DocumentChunkRepository,
    DocumentRepository,
    UserRepository,
)
from app.rag.chunking import TextChunker
from app.rag.embeddings import FakeEmbeddingProvider
from app.rag.loaders import get_loader_for_extension, is_supported_extension
from app.schemas.document import (
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentListResponse,
    DocumentResponse,
    UploadResponse,
)


class DocumentService:
    """Service for document operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.document_repo = DocumentRepository(session)
        self.chunk_repo = DocumentChunkRepository(session)

        # Initialize RAG components
        settings = get_settings()
        self.chunker = TextChunker(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        self.embedding_provider = FakeEmbeddingProvider(dimension=settings.embedding_dimension)

    async def upload_document(
        self,
        filename: str,
        content: bytes,
        title: str | None = None,
    ) -> UploadResponse:
        """Upload and process a document.

        Args:
            filename: Original filename
            content: Raw file content
            title: Optional document title

        Returns:
            UploadResponse with document and chunks count

        Raises:
            ValueError: If file type not supported or content invalid
        """
        # Validate file type
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if not is_supported_extension(extension):
            raise ValueError(f"Unsupported file type: {extension}")

        # Validate content is not empty
        if not content or len(content) == 0:
            raise ValueError("File is empty")

        # Get or create demo user
        user = await self.user_repo.get_or_create_demo_user()

        # Create document with initial status
        document = await self.document_repo.create(
            user_id=user.id,
            title=title or filename,
            filename=filename,
            file_type=extension,
            file_size=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            status="processing",
        )

        try:
            # Load content
            loader = get_loader_for_extension(extension)
            if loader is None:
                raise ValueError(f"No loader available for: {extension}")

            text = loader.load(content, filename)

            # Chunk text
            chunks = self.chunker.chunk(text)

            if not chunks:
                raise ValueError("Document produced no chunks (content may be empty)")

            # Create chunks with embeddings
            chunks_data = []
            for i, chunk_text in enumerate(chunks):
                embedding = self.embedding_provider.embed(chunk_text)
                token_count = self.chunker.estimate_token_count(chunk_text)
                chunks_data.append(
                    {
                        "document_id": document.id,
                        "chunk_index": i,
                        "content": chunk_text,
                        "embedding": embedding,
                        "token_count": token_count,
                    }
                )

            await self.chunk_repo.create_batch(chunks_data)

            # Update document status to ready
            await self.document_repo.update_status(document, "ready")

        except Exception as e:
            # Update document status to failed
            await self.document_repo.update_status(document, "failed")
            raise e

        # Get chunks count
        chunks_count = await self.chunk_repo.count_by_document(document.id)

        return UploadResponse(
            document=DocumentResponse(
                id=document.id,
                title=document.title,
                filename=document.filename,
                file_type=document.file_type,
                file_size=document.file_size,
                status=document.status,
                created_at=document.created_at,
                updated_at=document.updated_at,
            ),
            chunks_count=chunks_count,
        )

    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> DocumentListResponse:
        """List all documents for the demo user.

        Args:
            limit: Maximum number of documents
            offset: Offset for pagination

        Returns:
            DocumentListResponse
        """
        user = await self.user_repo.get_or_create_demo_user()

        documents = await self.document_repo.get_all_by_user(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )
        total = await self.document_repo.count_by_user(user.id)

        return DocumentListResponse(
            documents=[
                DocumentResponse(
                    id=d.id,
                    title=d.title,
                    filename=d.filename,
                    file_type=d.file_type,
                    file_size=d.file_size,
                    status=d.status,
                    created_at=d.created_at,
                    updated_at=d.updated_at,
                )
                for d in documents
            ],
            total=total,
        )

    async def get_document(self, document_id: UUID) -> DocumentResponse | None:
        """Get a document by ID.

        Args:
            document_id: Document UUID

        Returns:
            DocumentResponse or None if not found
        """
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            return None

        return DocumentResponse(
            id=document.id,
            title=document.title,
            filename=document.filename,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    async def get_document_chunks(
        self,
        document_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> DocumentChunkListResponse | None:
        """Get chunks for a document.

        Args:
            document_id: Document UUID
            limit: Maximum number of chunks
            offset: Offset for pagination

        Returns:
            DocumentChunkListResponse or None if document not found
        """
        # Check if document exists (exclude deleted)
        document = await self.document_repo.get_by_id(document_id)
        if not document:
            return None

        chunks = await self.chunk_repo.get_all_by_document(
            document_id=document_id,
            limit=limit,
            offset=offset,
        )
        total = await self.chunk_repo.count_by_document(document_id)

        return DocumentChunkListResponse(
            chunks=[
                DocumentChunkResponse(
                    id=c.id,
                    document_id=c.document_id,
                    chunk_index=c.chunk_index,
                    content=c.content,
                    token_count=c.token_count,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                )
                for c in chunks
            ],
            total=total,
        )

    async def delete_document(self, document_id: UUID) -> bool:
        """Soft delete a document.

        Args:
            document_id: Document UUID

        Returns:
            True if deleted, False if not found
        """
        document = await self.document_repo.get_by_id(document_id, include_deleted=True)
        if not document:
            return False

        # Already deleted
        if document.status == "deleted":
            return False

        await self.document_repo.soft_delete(document)
        return True
