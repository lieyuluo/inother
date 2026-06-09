"""Text chunking strategies for RAG."""

from app.core.config import get_settings


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