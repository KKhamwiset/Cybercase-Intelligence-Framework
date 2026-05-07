"""
Application configuration — loaded from environment / .env file.
"""
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
    )

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tsr_mitre"

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    # ── App ──────────────────────────────────────────────────────────────
    debug: bool = True
    anthropic_api_key: str = ""


settings = Settings()
