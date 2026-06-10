"""Application configuration management using Pydantic Settings."""

import json
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "dev-jwt-secret-change-in-production"
_MIN_PRODUCTION_SECRET_LENGTH = 32


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
    jwt_secret_key: str = _DEFAULT_JWT_SECRET
    access_token_expire_minutes: int = 60
    auth_required: bool = False

    # LLM Provider Configuration
    llm_provider: str = "fake"  # 'fake' or 'openai'
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""

    # Embedding Provider Configuration
    embedding_provider: str = "fake"  # 'fake' or 'openai'
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_base_url: str = ""

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
    rag_reranker_provider: str = "none"  # 'none' or 'llm'

    # Agent Planning Configuration
    agent_planner_provider: str = ""  # empty => deterministic in dev/test, llm in production

    # MCP Configuration
    mcp_demo_enabled: bool = True  # Enable demo MCP tools
    mcp_server_configs: str = ""

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Fail fast on unsafe production configuration."""
        if not self.is_production():
            return self

        if not self.auth_required:
            raise ValueError("AUTH_REQUIRED must be true when APP_ENV=production")

        if (
            self.jwt_secret_key == _DEFAULT_JWT_SECRET
            or len(self.jwt_secret_key) < _MIN_PRODUCTION_SECRET_LENGTH
        ):
            raise ValueError(
                "JWT_SECRET_KEY must be replaced with a strong secret "
                f"of at least {_MIN_PRODUCTION_SECRET_LENGTH} characters in production"
            )

        if self.mcp_demo_enabled:
            raise ValueError("MCP_DEMO_ENABLED must be false when APP_ENV=production")

        if self.effective_agent_planner_provider != "llm":
            raise ValueError("AGENT_PLANNER_PROVIDER must be llm when APP_ENV=production")

        if self.rag_reranker_provider.lower() == "llm" or (
            self.effective_agent_planner_provider == "llm"
        ):
            if self.llm_provider.lower() != "openai":
                raise ValueError(
                    "LLM_PROVIDER must be openai for LLM planner/reranker in production"
                )
            if not self.effective_llm_api_key:
                raise ValueError(
                    "LLM_API_KEY or OPENAI_API_KEY is required for LLM planner/reranker in production"
                )

        return self

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

    @property
    def effective_agent_planner_provider(self) -> str:
        """Return configured planner provider with production-aware default."""
        provider = self.agent_planner_provider.strip().lower()
        if provider:
            return provider
        if self.is_production():
            return "llm"
        return "deterministic"

    @property
    def effective_llm_api_key(self) -> str:
        """Return the LLM API key, falling back to OPENAI_API_KEY."""
        return self.llm_api_key or self.openai_api_key

    @property
    def effective_llm_base_url(self) -> str:
        """Return the LLM base URL, falling back to OPENAI_BASE_URL."""
        return self.llm_base_url or self.openai_base_url

    @property
    def effective_embedding_api_key(self) -> str:
        """Return the embedding API key, falling back to OPENAI_API_KEY."""
        return self.embedding_api_key or self.openai_api_key

    @property
    def effective_embedding_base_url(self) -> str:
        """Return the embedding base URL, falling back to OPENAI_BASE_URL."""
        return self.embedding_base_url or self.openai_base_url

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
