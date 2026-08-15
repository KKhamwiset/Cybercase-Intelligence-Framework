"""
Application configuration — loaded from environment / .env file.
"""

import os
from typing import Literal

from pydantic import Field
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
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif "asyncpg" not in url:
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url

        # Construct from components if DATABASE_URL is not provided
        from sqlalchemy.engine.url import URL

        return str(
            URL.create(
                drivername="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=int(self.postgres_port),
                database=self.postgres_db,
            )
        )

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

    # ── Chat application ─────────────────────────────────────────────────
    debug: bool = False
    core_llm_provider: Literal["anthropic", "openrouter"] = "openrouter"
    anthropic_api_key: str = ""
    anthropic_messages_url: str = "https://api.anthropic.com/v1/messages"
    openrouter_cybercase: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_messages_url: str = "https://openrouter.ai/api/v1/messages"
    core_llm_openrouter_model: str = "openai/gpt-5.6-luna"
    rag_service_url: str = os.getenv("RAG_SERVICE_URL", "http://rag-service:8001")
    chat_followup_policy_enabled: bool = True
    chat_followup_policy_model: str = "openai/gpt-5.6-luna"
    chat_followup_policy_timeout_seconds: float = 15.0
    chat_followup_policy_max_output_tokens: int = 128
    chat_followup_policy_max_user_chars: int = 4_000
    chat_followup_question_max_chars: int = 300
    chat_followup_combined_query_max_chars: int = 12_000
    chat_followup_max_rounds: int = Field(default=8, ge=1, le=16)

    # Post-answer ASK reasons over the persisted case and latest analysis. It
    # deliberately does not call the retrieval service again.
    chat_ask_model: str = "openai/gpt-5.6-luna"
    chat_ask_timeout_seconds: float = 60.0
    chat_ask_max_output_tokens: int = 2_048
    chat_ask_max_input_chars: int = 20_000

    # Terminal chat extraction baseline. A missing provider key produces an
    # explicit failed extraction record rather than falling back to regex.
    chat_extraction_enabled: bool = True
    chat_extraction_model: str = "openai/gpt-5.6-luna"
    chat_extraction_timeout_seconds: float = 120.0
    chat_extraction_max_input_chars: int = 60_000
    chat_extraction_max_output_tokens: int = 16_384
    chat_extraction_max_entities: int = 32
    chat_extraction_max_relationships: int = 64
    chat_extraction_max_evidence: int = 32
    chat_extraction_max_timeline: int = 48
    chat_extraction_max_missing_information: int = 24
    chat_extraction_max_text_chars: int = 8_000
    chat_extraction_max_raw_response_chars: int = 96_000

    # Persisted report generation. The report service performs one provider
    # call per valid generation attempt and never repairs model output.
    chat_report_enabled: bool = True
    chat_report_model: str = "openai/gpt-5.6-luna"
    chat_report_timeout_seconds: float = 180.0
    chat_report_max_input_chars: int = 100_000
    chat_report_max_output_tokens: int = 16_384
    chat_report_max_raw_response_chars: int = 96_000
    chat_report_temperature: float = 0.0
    chat_report_max_text_chars: int = 8_000
    chat_report_max_claims: int = 128
    chat_report_max_limitations: int = 48

settings = Settings()
