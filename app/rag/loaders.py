"""Document loaders for different file types."""

from abc import ABC, abstractmethod
from pathlib import Path


class DocumentLoader(ABC):
    """Abstract base class for document loaders."""

    @abstractmethod
    def load(self, content: bytes, filename: str) -> str:
        """Load and parse document content.

        Args:
            content: Raw file content as bytes
            filename: Original filename

        Returns:
            Parsed text content

        Raises:
            ValueError: If content cannot be parsed
        """
        pass

    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Get file extension from filename."""
        return Path(filename).suffix.lower().lstrip(".")


class TextLoader(DocumentLoader):
    """Loader for plain text files (.txt)."""

    SUPPORTED_EXTENSIONS = ["txt"]

    def load(self, content: bytes, filename: str) -> str:
        """Load plain text content.

        Args:
            content: Raw file content as bytes
            filename: Original filename

        Returns:
            UTF-8 decoded text

        Raises:
            ValueError: If content cannot be decoded as UTF-8
        """
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"Cannot decode file '{filename}' as UTF-8: {e}") from e

        # Check for empty content
        if not text.strip():
            raise ValueError(f"File '{filename}' is empty or contains only whitespace")

        return text


class MarkdownLoader(DocumentLoader):
    """Loader for Markdown files (.md).

    Phase 3 keeps Markdown content as-is without converting to plain text.
    Future phases may implement Markdown-to-text conversion.
    """

    SUPPORTED_EXTENSIONS = ["md", "markdown"]

    def load(self, content: bytes, filename: str) -> str:
        """Load Markdown content.

        Args:
            content: Raw file content as bytes
            filename: Original filename

        Returns:
            UTF-8 decoded Markdown text

        Raises:
            ValueError: If content cannot be decoded as UTF-8
        """
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError(f"Cannot decode file '{filename}' as UTF-8: {e}") from e

        # Check for empty content
        if not text.strip():
            raise ValueError(f"File '{filename}' is empty or contains only whitespace")

        return text


class PDFLoader(DocumentLoader):
    """Loader for PDF files (.pdf) using pypdf."""

    SUPPORTED_EXTENSIONS = ["pdf"]

    def load(self, content: bytes, filename: str) -> str:
        try:
            from io import BytesIO

            from pypdf import PdfReader

            reader = PdfReader(BytesIO(content))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())

            if not pages:
                raise ValueError(f"File '{filename}' contains no extractable text")

            return "\n\n".join(pages)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse PDF '{filename}': {e}") from e


class DocxLoader(DocumentLoader):
    """Loader for DOCX files (.docx) using python-docx."""

    SUPPORTED_EXTENSIONS = ["docx"]

    def load(self, content: bytes, filename: str) -> str:
        try:
            from io import BytesIO

            from docx import Document as DocxDocument

            doc = DocxDocument(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]

            if not paragraphs:
                raise ValueError(f"File '{filename}' contains no text content")

            return "\n\n".join(paragraphs)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX '{filename}': {e}") from e


def get_loader_for_extension(extension: str) -> DocumentLoader | None:
    """Get appropriate loader for file extension.

    Args:
        extension: File extension (without dot)

    Returns:
        DocumentLoader instance or None if extension not supported
    """
    extension = extension.lower()

    if extension in TextLoader.SUPPORTED_EXTENSIONS:
        return TextLoader()
    if extension in MarkdownLoader.SUPPORTED_EXTENSIONS:
        return MarkdownLoader()
    if extension in PDFLoader.SUPPORTED_EXTENSIONS:
        return PDFLoader()
    if extension in DocxLoader.SUPPORTED_EXTENSIONS:
        return DocxLoader()

    return None


def is_supported_extension(extension: str) -> bool:
    """Check if file extension is supported.

    Args:
        extension: File extension (without dot)

    Returns:
        True if extension is supported
    """
    return get_loader_for_extension(extension) is not None
