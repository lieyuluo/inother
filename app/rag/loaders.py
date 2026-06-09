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

    return None


def is_supported_extension(extension: str) -> bool:
    """Check if file extension is supported.

    Args:
        extension: File extension (without dot)

    Returns:
        True if extension is supported
    """
    return get_loader_for_extension(extension) is not None