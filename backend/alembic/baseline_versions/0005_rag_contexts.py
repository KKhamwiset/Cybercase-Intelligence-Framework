"""Persist one retrieval context for each case-state version.

Revision ID: 0005_rag_contexts
Revises: 0004_answered_thread_status
Create Date: 2026-08-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_rag_contexts"
down_revision: Union[str, None] = "0004_answered_thread_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rag_contexts",
        sa.Column("retrieval_context_id", sa.String(length=160), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "case_state_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("context", sa.Text(), nullable=False),
        sa.Column(
            "mitre_table",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "case_state_version_id"],
            ["case_state_versions.thread_id", "case_state_versions.id"],
            name="fk_rag_contexts_thread_case_state_version",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "retrieval_context_id",
            name="pk_rag_contexts",
        ),
        sa.UniqueConstraint(
            "case_state_version_id",
            name="uq_rag_contexts_case_state_version_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("rag_contexts")
