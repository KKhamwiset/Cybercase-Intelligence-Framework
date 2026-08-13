"""Immutable structured case-state history for persisted chat threads."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CaseStateVersion(Base):
    __tablename__ = "case_state_versions"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_case_state_versions"),
        UniqueConstraint(
            "thread_id",
            "version",
            name="uq_case_state_versions_thread_id_version",
        ),
        UniqueConstraint(
            "thread_id",
            "id",
            name="uq_case_state_versions_thread_id_id",
        ),
        ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_case_state_versions_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["thread_id", "parent_version_id"],
            ["case_state_versions.thread_id", "case_state_versions.id"],
            name="fk_case_state_versions_thread_parent",
            deferrable=True,
            initially="DEFERRED",
        ),
        ForeignKeyConstraint(
            ["thread_id", "trigger_message_id"],
            ["chat_messages.thread_id", "chat_messages.id"],
            name="fk_case_state_versions_thread_trigger_message",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "version > 0",
            name="ck_case_state_versions_version_positive",
        ),
        Index(
            "ix_case_state_versions_thread_id_created_at",
            "thread_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    trigger_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    delta_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    state_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    thread = relationship(
        "ChatThread",
        back_populates="case_state_versions",
        foreign_keys=[thread_id],
        primaryjoin="CaseStateVersion.thread_id == ChatThread.id",
    )


__all__ = ["CaseStateVersion"]
