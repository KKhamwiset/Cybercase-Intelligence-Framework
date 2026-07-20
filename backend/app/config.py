"""
Application configuration — loaded from environment / .env file.
"""

import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configuration values are read from environment variables.
    A `.env` file in the backend/ directory is also supported.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ─────────────────────────────────────────────────────────
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_db: str = os.getenv("POSTGRES_DB", "cybercase_framework")
    postgres_host: str = os.getenv("POSTGRES_HOST", "db")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")

    database_url: str = os.getenv("DATABASE_URL", "")

    @property
    def async_database_url(self) -> str:
        """Ensures the URL uses postgresql+asyncpg:// for SQLAlchemy async engine."""
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://") and "asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: str = os.getenv("CORS_ORIGINS", "")

    @property
    def cors_origins_list(self) -> list[str]:
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
        if self.cors_origins:
            env_origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
            for o in env_origins:
                if not o.startswith("http"):
                    origins.append(f"https://{o}")
                    origins.append(f"http://{o}")
                else:
                    origins.append(o)
        return list(set(origins))

    # ── App ──────────────────────────────────────────────────────────────
    debug: bool = True
    anthropic_api_key: str = ""
    analysis_llm_model: str = "claude-haiku-4-5"
    analysis_llm_timeout_seconds: float = 60.0
    analysis_llm_max_output_tokens: int = 4096
    analysis_semantic_max_output_tokens: int = 128
    analysis_retrieval_timeout_seconds: float = 30.0
    anthropic_messages_url: str = "https://api.anthropic.com/v1/messages"
    experimental_analysis_enabled: bool = False
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "http://rag-service:8001")


settings = Settings()
