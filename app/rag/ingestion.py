"""Document ingestion pipeline for RAG."""

from uuid import UUID, uuid4

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.rag.chunking import TextChunker
from app.rag.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.rag.loaders import DocumentLoader, get_loader_for_extension, is_supported_extension


class IngestionPipeline:
    """Document ingestion pipeline for processing and storing documents.

    Pipeline steps:
    1. Validate file type
    2. Load and parse content
    3. Chunk text
    4. Generate embeddings
    5. Create Document and DocumentChunk records
    """

    def __init__(
        self,
        chunker: TextChunker | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        """Initialize ingestion pipeline.

        Args:
            chunker: Text chunker (default: configured chunker)
            embedding_provider: Embedding provider (default: FakeEmbeddingProvider)
        """
        settings = get_settings()
        self.chunker = chunker or TextChunker()
        self.embedding_provider = embedding_provider or FakeEmbeddingProvider(
            dimension=settings.embedding_dimension
        )

    def validate_file_type(self, filename: str) -> tuple[bool, str]:
        """Validate file type is supported.

        Args:
            filename: Filename to validate

        Returns:
            Tuple of (is_valid, extension)
        """
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        is_valid = is_supported_extension(extension)
        return is_valid, extension

    def load_content(self, content: bytes, filename: str) -> str:
        """Load and parse document content.

        Args:
            content: Raw file content
            filename: Original filename

        Returns:
            Parsed text content

        Raises:
            ValueError: If file type not supported or content invalid
        """
        is_valid, extension = self.validate_file_type(filename)
        if not is_valid:
            raise ValueError(f"Unsupported file type: {extension}")

        loader = get_loader_for_extension(extension)
        if loader is None:
            raise ValueError(f"No loader available for: {extension}")

        return loader.load(content, filename)

    def process_document(
        self,
        user_id: UUID,
        filename: str,
        content: bytes,
        title: str | None = None,
    ) -> tuple[Document, list[DocumentChunk]]:
        """Process document and create records.

        Args:
            user_id: User ID owning the document
            filename: Original filename
            content: Raw file content
            title: Optional document title

        Returns:
            Tuple of (Document, list of DocumentChunks)

        Raises:
            ValueError: If file type not supported or content invalid
        """
        # Validate and get extension
        is_valid, extension = self.validate_file_type(filename)
        if not is_valid:
            raise ValueError(f"Unsupported file type: {extension}")

        # Load content
        text = self.load_content(content, filename)

        # Create Document record
        document = Document(
            id=uuid4(),
            user_id=user_id,
            title=title or filename,
            filename=filename,
            file_type=extension,
            file_size=len(content),
            content_hash=hashlib.sha256(content).hexdigest() if content else None,
            status="processing",
        )

        # Chunk text
        chunks = self.chunker.chunk(text)

        # Create DocumentChunk records
        document_chunks: list[DocumentChunk] = []
        for i, chunk_text in enumerate(chunks):
            # Generate embedding
            embedding = self.embedding_provider.embed(chunk_text)

            # Estimate token count
            token_count = self.chunker.estimate_token_count(chunk_text)

            chunk = DocumentChunk(
                id=uuid4(),
                document_id=document.id,
                chunk_index=i,
                content=chunk_text,
                embedding=embedding,
                token_count=token_count,
            )
            document_chunks.append(chunk)

        # Update document status
        document.status = "ready"

        return document, document_chunks

    def estimate_chunks(self, content: bytes, filename: str) -> int:
        """Estimate number of chunks for a document.

        Args:
            content: Raw file content
            filename: Original filename

        Returns:
            Estimated number of chunks

        Raises:
            ValueError: If file type not supported
        """
        text = self.load_content(content, filename)
        chunks = self.chunker.chunk(text)
        return len(chunks)


import hashlib  # Import needed for content_hash