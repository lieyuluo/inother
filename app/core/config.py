"""Application configuration management using Pydantic Settings."""

import json
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "enterprise-ai-agent"
    app_env: str = "development"
    app_version: str = "1.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "[]"

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    jwt_secret_key: str = "dev-jwt-secret-change-in-production"
    access_token_expire_minutes: int = 60
    auth_required: bool = False

    # LLM Provider Configuration
    llm_provider: str = "fake"  # 'fake' or 'openai'
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_llm_model: str = "gpt-4o-mini"

    # Embedding Provider Configuration
    embedding_provider: str = "fake"  # 'fake' or 'openai'
    openai_embedding_model: str = "text-embedding-3-small"

    # Provider Configuration
    provider_timeout_seconds: float = 30.0
    provider_max_retries: int = 2

    # RAG Configuration
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    embedding_dimension: int = 1536  # Match OpenAI embedding dimension
    rag_top_k: int = 4
    rag_snippet_max_length: int = 300

    # RAG Advanced Configuration
    rag_chunk_strategy: str = "fixed"  # 'fixed' or 'recursive'
    rag_retrieval_mode: str = "vector"  # 'vector', 'keyword', or 'hybrid'
    rag_reranker_provider: str = "none"  # 'none' (placeholder for future)

    # MCP Configuration
    mcp_demo_enabled: bool = True  # Enable demo MCP tools
    mcp_server_configs: str = ""

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from string to list."""
        try:
            origins: list[str] = json.loads(self.cors_origins)
            return origins
        except json.JSONDecodeError:
            # Handle comma-separated string format
            if self.cors_origins and self.cors_origins != "[]":
                return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
            return []

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"

    def is_pgvector_available(self) -> bool:
        """Check if PostgreSQL with pgvector is available (not SQLite).

        Returns:
            True if the database URL indicates PostgreSQL.
        """
        return "postgresql" in self.database_url.lower()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear settings cache (useful for testing)."""
    get_settings.cache_clear()
