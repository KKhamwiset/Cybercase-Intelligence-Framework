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
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5433/cybercase_framework",
    )

    @property
    def async_database_url(self) -> str:
        """Ensures the URL uses postgresql+asyncpg:// for SQLAlchemy async engine."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif "asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        # Always allow localhost for development
        origins = ["http://localhost:3000", "http://127.0.0.1:3000"]

        # Add origins from environment variable if they exist
        if self.cors_origins:
            env_origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
            for o in env_origins:
                # Ensure protocol is present
                if not o.startswith("http"):
                    origins.append(f"https://{o}")
                    origins.append(f"http://{o}")
                else:
                    origins.append(o)

        return list(set(origins))  # Deduplicate

    # ── App ──────────────────────────────────────────────────────────────
    debug: bool = True
    anthropic_api_key: str = ""
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "http://rag-service:8001")


settings = Settings()
