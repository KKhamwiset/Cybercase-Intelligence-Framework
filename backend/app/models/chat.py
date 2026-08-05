"""Persistent chat threads, messages, and background processing runs."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
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


class ChatThread(Base):
    __tablename__ = "chat_threads"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chat_threads"),
        CheckConstraint(
            "status IN ('idle', 'processing', 'awaiting_followup', 'failed')",
            name="ck_chat_threads_status",
        ),
        CheckConstraint(
            "next_message_ordinal > 0",
            name="ck_chat_threads_next_message_ordinal_positive",
        ),
        Index("ix_chat_threads_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New chat",
        server_default=text("'New chat'"),
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="idle",
        server_default=text("'idle'"),
    )
    active_rag_session_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    next_message_ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.ordinal",
    )
    runs: Mapped[list[ChatRun]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    reports: Mapped[list["ChatReport"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chat_messages"),
        UniqueConstraint(
            "thread_id",
            "ordinal",
            name="uq_chat_messages_thread_id_ordinal",
        ),
        CheckConstraint(
            "ordinal > 0",
            name="ck_chat_messages_ordinal_positive",
        ),
        CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
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
            name="fk_chat_messages_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_context_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    thread: Mapped[ChatThread] = relationship(back_populates="messages")
    runs: Mapped[list[ChatRun]] = relationship(
        back_populates="request_message",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChatRun(Base):
    __tablename__ = "chat_runs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_chat_runs"),
        UniqueConstraint(
            "thread_id",
            "idempotency_key",
            name="uq_chat_runs_thread_id_idempotency_key",
        ),
        CheckConstraint(
            "operation IN ('query', 'resume')",
            name="ck_chat_runs_operation",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_chat_runs_status",
        ),
        CheckConstraint(
            "((operation = 'query' AND input_rag_session_id IS NULL) OR "
            "(operation = 'resume' AND input_rag_session_id IS NOT NULL))",
            name="ck_chat_runs_input_rag_session_id",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_chat_runs_attempt_count_nonnegative",
        ),
        Index(
            "ux_chat_runs_one_active_per_thread",
            "thread_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index(
            "ix_chat_runs_status_lease_expires_at",
            "status",
            "lease_expires_at",
        ),
        Index("ix_chat_runs_thread_id_created_at", "thread_id", "created_at"),
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
            name="fk_chat_runs_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    request_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "chat_messages.id",
            name="fk_chat_runs_request_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="queued",
        server_default=text("'queued'"),
    )
    input_rag_session_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    request_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    thread: Mapped[ChatThread] = relationship(back_populates="runs")
    request_message: Mapped[ChatMessage] = relationship(back_populates="runs")
