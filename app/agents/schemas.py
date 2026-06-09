"""Schemas for RAG Agent."""

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class Citation:
    """A citation referencing a retrieved document chunk."""

    document_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    score: float
    snippet: str


@dataclass
class RAGAgentResult:
    """Result from the RAG Agent."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    used_fallback: bool = False
