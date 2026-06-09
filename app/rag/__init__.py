"""RAG (Retrieval-Augmented Generation) module for document processing."""

from app.rag.chunking import TextChunker
from app.rag.embeddings import EmbeddingProvider, FakeEmbeddingProvider
from app.rag.loaders import DocumentLoader, TextLoader, MarkdownLoader

__all__ = [
    "DocumentLoader",
    "TextLoader",
    "MarkdownLoader",
    "TextChunker",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
]