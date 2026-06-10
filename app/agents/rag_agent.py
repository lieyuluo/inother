"""RAG Agent that combines retrieval and generation for question answering."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import Citation, RAGAgentResult
from app.core.config import get_settings
from app.llm.base import BaseLLMProvider
from app.llm.provider import get_llm_provider
from app.rag.embeddings import EmbeddingProvider, get_embedding_provider
from app.rag.retriever import Retriever


class RAGAgent:
    """RAG Agent that retrieves relevant documents and generates answers.

    Flow:
    1. Accept user question
    2. Use Retriever to find relevant document chunks
    3. Build context from retrieved chunks
    4. Use LLM Provider to generate answer
    5. Return answer with citations
    """

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        llm_provider: BaseLLMProvider | None = None,
        top_k: int | None = None,
        snippet_max_length: int | None = None,
        user_id: UUID | None = None,
    ) -> None:
        """Initialize RAG Agent.

        Args:
            session: Async database session.
            embedding_provider: Embedding provider (default: from config).
            llm_provider: LLM provider (default: from config).
            top_k: Number of retrieval results (default: from config).
            snippet_max_length: Max snippet length (default: from config).
        """
        settings = get_settings()
        self.embedding_provider = embedding_provider or get_embedding_provider(
            provider_name=settings.embedding_provider,
            dimension=settings.embedding_dimension,
            api_key=settings.openai_api_key or None,
            model=settings.openai_embedding_model,
        )
        self.llm_provider = llm_provider or get_llm_provider(settings)
        self.retriever = Retriever(
            session=session,
            embedding_provider=self.embedding_provider,
            top_k=top_k,
            snippet_max_length=snippet_max_length,
            user_id=user_id,
        )

    async def query(self, question: str) -> RAGAgentResult:
        """Process a user question through the RAG pipeline.

        Args:
            question: User question text.

        Returns:
            RAGAgentResult containing answer, citations, and metadata.
        """
        # Retrieve relevant chunks
        retrieval_results = await self.retriever.similarity_search(question)

        # Build citations from retrieval results
        citations = [
            Citation(
                document_id=r.document_id,
                document_title=r.document_title,
                chunk_id=r.chunk_id,
                chunk_index=r.chunk_index,
                score=r.score,
                snippet=r.content,
            )
            for r in retrieval_results
        ]

        # Build context string from retrieved chunks
        if retrieval_results:
            context_parts = [r.content for r in retrieval_results]
            context = "\n---\n".join(context_parts)
            used_fallback = False
        else:
            context = ""
            used_fallback = True

        # Generate answer using LLM provider
        answer = self.llm_provider.generate(question, context)

        return RAGAgentResult(
            answer=answer,
            citations=citations,
            used_fallback=used_fallback,
        )
