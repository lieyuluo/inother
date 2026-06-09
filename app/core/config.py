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
    app_version: str = "0.1.0"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_ai_agent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"

    # CORS
    cors_origins: str = "[]"

    # Security (for future phases)
    secret_key: str = "your-secret-key-change-in-production"

    # RAG Configuration
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    embedding_dimension: int = 1536  # Match OpenAI embedding dimension
    rag_top_k: int = 4
    rag_snippet_max_length: int = 300

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear settings cache (useful for testing)."""
    get_settings.cache_clear()
