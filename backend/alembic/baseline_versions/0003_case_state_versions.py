"""Add immutable case-state versions and the current thread pointer.

Revision ID: 0003_case_state_versions
Revises: 0002_chat_reports
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_case_state_versions"
down_revision: Union[str, None] = "0002_chat_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_chat_messages_thread_id_id",
        "chat_messages",
        ["thread_id", "id"],
    )
    op.create_table(
        "case_state_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "parent_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "trigger_message_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "delta_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "state_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version > 0",
            name="ck_case_state_versions_version_positive",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name="fk_case_state_versions_thread_id_chat_threads",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "parent_version_id"],
            ["case_state_versions.thread_id", "case_state_versions.id"],
            name="fk_case_state_versions_thread_parent",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "trigger_message_id"],
            ["chat_messages.thread_id", "chat_messages.id"],
            name="fk_case_state_versions_thread_trigger_message",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_state_versions"),
        sa.UniqueConstraint(
            "thread_id",
            "version",
            name="uq_case_state_versions_thread_id_version",
        ),
        sa.UniqueConstraint(
            "thread_id",
            "id",
            name="uq_case_state_versions_thread_id_id",
        ),
    )
    op.create_index(
        "ix_case_state_versions_thread_id_created_at",
        "case_state_versions",
        ["thread_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "chat_threads",
        sa.Column(
            "current_case_state_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_chat_threads_current_case_state_version",
        "chat_threads",
        "case_state_versions",
        ["id", "current_case_state_version_id"],
        ["thread_id", "id"],
        deferrable=True,
        initially="DEFERRED",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_chat_threads_current_case_state_version",
        "chat_threads",
        type_="foreignkey",
    )
    op.drop_column("chat_threads", "current_case_state_version_id")
    op.drop_index(
        "ix_case_state_versions_thread_id_created_at",
        table_name="case_state_versions",
    )
    op.drop_table("case_state_versions")
    op.drop_constraint(
        "uq_chat_messages_thread_id_id",
        "chat_messages",
        type_="unique",
    )
