"""Immutable report history scoped to a persisted chat thread."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChatReport(Base):
    __tablename__ = "chat_reports"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chat_reports"),
        UniqueConstraint(
            "thread_id",
            "version_number",
            name="uq_chat_reports_thread_id_version_number",
        ),
        UniqueConstraint(
            "thread_id",
            "idempotency_key",
            name="uq_chat_reports_thread_id_idempotency_key",
        ),
        CheckConstraint(
            "version_number > 0",
            name="ck_chat_reports_version_number_positive",
        ),
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_chat_reports_status",
        ),
        CheckConstraint(
            "validation_status IN ('validated', 'failed')",
            name="ck_chat_reports_validation_status",
        ),
        Index("ix_chat_reports_thread_id_created_at", "thread_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "chat_threads.id",
            name="fk_chat_reports_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_snapshot_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    source_snapshot_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
    )
    extraction_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "chat_messages.id",
            name="fk_chat_reports_extraction_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    extraction_version: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    decoding_settings: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    validation_errors_json: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    structured_report: Mapped[dict[str, object] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    thread = relationship("ChatThread", back_populates="reports")
    extraction_message = relationship("ChatMessage")


__all__ = ["ChatReport"]
