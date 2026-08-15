"""Durable retrieval context bound one-to-one to a case-state version."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RagContext(Base):
    __tablename__ = "rag_contexts"
    __table_args__ = (
        PrimaryKeyConstraint(
            "retrieval_context_id",
            name="pk_rag_contexts",
        ),
        UniqueConstraint(
            "case_state_version_id",
            name="uq_rag_contexts_case_state_version_id",
        ),
        ForeignKeyConstraint(
            ["thread_id", "case_state_version_id"],
            ["case_state_versions.thread_id", "case_state_versions.id"],
            name="fk_rag_contexts_thread_case_state_version",
            ondelete="CASCADE",
        ),
    )

    retrieval_context_id: Mapped[str] = mapped_column(
        String(160),
        primary_key=True,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    case_state_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    context: Mapped[str] = mapped_column(Text, nullable=False)
    mitre_table: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = ["RagContext"]
