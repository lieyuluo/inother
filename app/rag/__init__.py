"""RAG (Retrieval-Augmented Generation) module for document processing."""

from app.rag.chunking import TextChunker
from app.rag.embeddings import (
    EmbeddingProvider,
    FakeEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from app.rag.loaders import DocumentLoader, MarkdownLoader, TextLoader

__all__ = [
    "DocumentLoader",
    "TextLoader",
    "MarkdownLoader",
    "TextChunker",
    "EmbeddingProvider",
    "FakeEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "get_embedding_provider",
]
