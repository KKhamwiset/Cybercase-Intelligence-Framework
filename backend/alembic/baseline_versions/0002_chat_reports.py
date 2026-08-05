"""Add immutable chat-scoped report history.

Revision ID: 0002_chat_reports
Revises: 0001_chat_user_baseline
Create Date: 2026-08-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_chat_reports"
down_revision: Union[str, None] = "0001_chat_user_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column(
            "source_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("source_snapshot_hash", sa.CHAR(length=64), nullable=False),
        sa.Column(
            "extraction_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("extraction_version", sa.String(length=80), nullable=False),
        sa.Column("prompt_version", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column(
            "decoding_settings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column(
            "validation_errors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "structured_report",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_chat_reports_version_number_positive",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_chat_reports_status",
        ),
        sa.CheckConstraint(
            "validation_status IN ('validated', 'failed')",
            name="ck_chat_reports_validation_status",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_chat_reports_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["extraction_message_id"],
            ["chat_messages.id"],
            name="fk_chat_reports_extraction_message_id_chat_messages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chat_reports"),
        sa.UniqueConstraint(
            "thread_id",
            "version_number",
            name="uq_chat_reports_thread_id_version_number",
        ),
        sa.UniqueConstraint(
            "thread_id",
            "idempotency_key",
            name="uq_chat_reports_thread_id_idempotency_key",
        ),
    )
    op.create_index(
        "ix_chat_reports_thread_id_created_at",
        "chat_reports",
        ["thread_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_reports_thread_id_created_at", table_name="chat_reports")
    op.drop_table("chat_reports")
