"""Text chunking strategies for RAG."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass
class ChunkMetadata:
    """Metadata for a single chunk."""

    start_char: int
    end_char: int
    page_number: int | None = None
    section_title: str | None = None


class TextChunker:
    """Text chunker for splitting documents into smaller pieces.

    Default configuration:
    - chunk_size: 800 characters
    - chunk_overlap: 100 characters

    These can be configured via environment variables:
    - RAG_CHUNK_SIZE
    - RAG_CHUNK_OVERLAP
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """Initialize chunker with configuration.

        Args:
            chunk_size: Maximum characters per chunk (default from config)
            chunk_overlap: Characters to overlap between chunks (default from config)
        """
        settings = get_settings()
        self.chunk_size = chunk_size or settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or settings.rag_chunk_overlap

        # Validate configuration
        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    def chunk(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Input text to chunk

        Returns:
            List of text chunks

        Note:
            - Empty text returns empty list
            - Short text (<= chunk_size) returns single chunk
            - Long text is split with overlap
        """
        if not text.strip():
            return []

        # Normalize text (preserve content but clean whitespace)
        text = text.strip()

        # If text is shorter than chunk_size, return as single chunk
        if len(text) <= self.chunk_size:
            return [text]

        # Split text into overlapping chunks
        chunks: list[str] = []
        start = 0

        while start < len(text):
            # Calculate end position
            end = start + self.chunk_size

            # If this is not the last chunk, try to find a good break point
            if end < len(text):
                # Look for natural break points (newline, space)
                break_point = self._find_break_point(text, start, end)
                if break_point > start:
                    end = break_point

            # Extract chunk
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position with overlap
            start = end - self.chunk_overlap
            if start < 0:
                start = 0

            # Prevent infinite loop
            if start >= len(text) or (chunks and start == end):
                break

        return chunks

    def chunk_with_metadata(self, text: str) -> list[tuple[str, ChunkMetadata]]:
        """Split text and return chunks with metadata.

        Args:
            text: Input text to chunk

        Returns:
            List of (chunk_text, ChunkMetadata) tuples
        """
        chunks = self.chunk(text)
        if not chunks:
            return []

        result: list[tuple[str, ChunkMetadata]] = []
        offset = 0
        for chunk_text in chunks:
            start = text.find(chunk_text, offset)
            if start == -1:
                start = offset
            end = start + len(chunk_text)
            offset = start + 1
            result.append(
                (
                    chunk_text,
                    ChunkMetadata(start_char=start, end_char=end),
                )
            )
        return result

    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find a natural break point in text.

        Looks for newline or space near the end position.

        Args:
            text: Full text
            start: Start position
            end: Target end position

        Returns:
            Position to break at, or end if no good break point found
        """
        # Look for newline first (better break point)
        search_start = max(start, end - 100)  # Look back 100 chars
        for i in range(end - 1, search_start, -1):
            if text[i] == "\n":
                return i + 1

        # Look for space
        for i in range(end - 1, search_start, -1):
            if text[i] == " ":
                return i + 1

        # No good break point found, use end
        return end

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text.

        Simple estimation: ~4 characters per token for English text.
        This is a rough approximation for planning purposes.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Simple estimation: 4 chars per token
        return len(text) // 4


class RecursiveTextChunker:
    """Recursive text chunker that splits by paragraphs/headers first.

    Strategy:
    1. Split by double newlines (paragraphs)
    2. If a paragraph is too long, split by single newlines
    3. If still too long, fall back to fixed chunking
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        settings = get_settings()
        self.chunk_size = chunk_size or settings.rag_chunk_size
        self.chunk_overlap = chunk_overlap or settings.rag_chunk_overlap

        if self.chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if self.chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")

    def chunk(self, text: str) -> list[str]:
        """Split text using recursive strategy."""
        if not text.strip():
            return []

        text = text.strip()

        if len(text) <= self.chunk_size:
            return [text]

        # Step 1: Split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        # Merge small paragraphs and split large ones
        chunks: list[str] = []
        current_chunk = ""

        for para in paragraphs:
            if len(para) > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                # Step 2: Split large paragraph by single newlines
                sub_chunks = self._split_by_lines(para)
                chunks.extend(sub_chunks)
            elif len(current_chunk) + len(para) + 2 > self.chunk_size:
                # Current chunk would be too large, flush it
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def chunk_with_metadata(self, text: str) -> list[tuple[str, ChunkMetadata]]:
        """Split text and return chunks with metadata."""
        chunks = self.chunk(text)
        if not chunks:
            return []

        result: list[tuple[str, ChunkMetadata]] = []
        offset = 0
        for chunk_text in chunks:
            start = text.find(chunk_text, offset)
            if start == -1:
                start = offset
            end = start + len(chunk_text)
            offset = start + 1

            # Try to detect section title from first line
            section_title = None
            first_line = chunk_text.split("\n", 1)[0].strip()
            if first_line.startswith("#"):
                section_title = first_line.lstrip("#").strip()

            result.append(
                (
                    chunk_text,
                    ChunkMetadata(
                        start_char=start,
                        end_char=end,
                        section_title=section_title,
                    ),
                )
            )
        return result

    def _split_by_lines(self, text: str) -> list[str]:
        """Split text by single newlines, merging small lines."""
        lines = text.split("\n")
        chunks: list[str] = []
        current = ""

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if len(line_stripped) > self.chunk_size:
                # Flush current
                if current:
                    chunks.append(current.strip())
                    current = ""
                # Step 3: Fall back to fixed chunking for very long lines
                chunks.extend(self._fixed_chunk(line_stripped))
            elif len(current) + len(line_stripped) + 1 > self.chunk_size:
                if current:
                    chunks.append(current.strip())
                current = line_stripped
            else:
                current = current + "\n" + line_stripped if current else line_stripped

        if current:
            chunks.append(current.strip())

        return chunks

    def _fixed_chunk(self, text: str) -> list[str]:
        """Fall back to fixed-size chunking for oversized text."""
        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - self.chunk_overlap
            if start < 0:
                start = 0
            if start >= len(text):
                break

        return chunks

    def estimate_token_count(self, text: str) -> int:
        """Estimate token count for text.

        Simple estimation: ~4 characters per token for English text.
        """
        return len(text) // 4


def get_chunker(
    strategy: str | None = None,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> TextChunker | RecursiveTextChunker:
    """Get chunker by strategy name."""
    settings = get_settings()
    strategy = strategy or settings.rag_chunk_strategy
    if strategy == "recursive":
        return RecursiveTextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
