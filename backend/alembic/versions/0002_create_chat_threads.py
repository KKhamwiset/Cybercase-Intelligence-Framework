"""create persistent chat threads, messages, and background runs

Revision ID: 0002_create_chat_threads
Revises: 0001_initial_core_schema
Create Date: 2026-07-19 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_create_chat_threads"
down_revision: Union[str, None] = "0001_initial_core_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "title",
            sa.String(length=255),
            server_default=sa.text("'New chat'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'idle'"),
            nullable=False,
        ),
        sa.Column(
            "active_rag_session_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column(
            "next_message_ordinal",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('idle', 'processing', 'awaiting_followup', 'failed')",
            name="ck_chat_threads_status",
        ),
        sa.CheckConstraint(
            "next_message_ordinal > 0",
            name="ck_chat_threads_next_message_ordinal_positive",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_threads"),
    )
    op.create_index(
        "ix_chat_threads_updated_at",
        "chat_threads",
        ["updated_at"],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "retrieval_context_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "ordinal > 0",
            name="ck_chat_messages_ordinal_positive",
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')",
            name="ck_chat_messages_role",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_messages_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_messages"),
        sa.UniqueConstraint(
            "thread_id",
            "ordinal",
            name="uq_chat_messages_thread_id_ordinal",
        ),
    )

    op.create_table(
        "chat_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "request_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("operation", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column(
            "input_rag_session_id",
            sa.String(length=160),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "request_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "operation IN ('query', 'resume')",
            name="ck_chat_runs_operation",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed')",
            name="ck_chat_runs_status",
        ),
        sa.CheckConstraint(
            "((operation = 'query' AND input_rag_session_id IS NULL) OR "
            "(operation = 'resume' AND input_rag_session_id IS NOT NULL))",
            name="ck_chat_runs_input_rag_session_id",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_chat_runs_attempt_count_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["request_message_id"],
            ["chat_messages.id"],
            name="fk_chat_runs_request_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_runs_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_runs"),
        sa.UniqueConstraint(
            "thread_id",
            "idempotency_key",
            name="uq_chat_runs_thread_id_idempotency_key",
        ),
    )
    op.create_index(
        "ix_chat_runs_status_lease_expires_at",
        "chat_runs",
        ["status", "lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_chat_runs_thread_id_created_at",
        "chat_runs",
        ["thread_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ux_chat_runs_one_active_per_thread",
        "chat_runs",
        ["thread_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index(
        "ux_chat_runs_one_active_per_thread",
        table_name="chat_runs",
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.drop_index("ix_chat_runs_thread_id_created_at", table_name="chat_runs")
    op.drop_index("ix_chat_runs_status_lease_expires_at", table_name="chat_runs")
    op.drop_table("chat_runs")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_threads_updated_at", table_name="chat_threads")
    op.drop_table("chat_threads")
