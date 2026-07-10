"""add durable case chat and canonical case snapshots

Revision ID: 0003_case_chat_state
Revises: 0002_create_report_tables
Create Date: 2026-07-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.case_context import CaseContextService


revision: str = "0003_case_chat_state"
down_revision: Union[str, None] = "0002_create_report_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("case_version", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("case_snapshot_hash", sa.String(length=64), nullable=True))

    # Migration-time backfill uses the same pure canonical serializer as the
    # API.  It does not touch updated_at, so existing cases are not marked as
    # newly edited merely because persistent hashing was introduced.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT case_id, title, status, severity, data FROM cases")
    ).mappings()
    for row in rows:
        payload = CaseContextService.build_payload_from_values(
            title=row["title"],
            status=row["status"],
            severity=row["severity"],
            data=row["data"] or {},
        )
        connection.execute(
            sa.text(
                "UPDATE cases SET case_version = :version, case_snapshot_hash = :snapshot_hash "
                "WHERE case_id = :case_id"
            ),
            {
                "case_id": row["case_id"],
                "version": 1,
                "snapshot_hash": CaseContextService.snapshot_hash(payload),
            },
        )
    op.alter_column("cases", "case_version", nullable=False, server_default="1")
    op.alter_column("cases", "case_snapshot_hash", nullable=False, server_default="")

    op.create_table(
        "case_chat_states",
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("case_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("active_session_id", sa.String(length=160), nullable=True),
        sa.Column("requires_followup", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("latest_analysis_turn_id", sa.String(length=80), nullable=True),
        sa.Column("latest_retrieval_context_id", sa.String(length=160), nullable=True),
        sa.Column("analysis_case_version", sa.Integer(), nullable=True),
        sa.Column("analysis_snapshot_hash", sa.String(length=64), nullable=True),
        sa.Column("pending_idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("pending_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("case_id"),
    )
    op.create_table(
        "case_chat_turns",
        sa.Column("turn_id", sa.String(length=80), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("turn_type", sa.String(length=20), nullable=False),
        sa.Column("turn_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("case_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("rag_session_id", sa.String(length=160), nullable=True),
        sa.Column("retrieval_context_id", sa.String(length=160), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.UniqueConstraint("case_id", "idempotency_key", name="uq_case_chat_turns_case_idempotency"),
    )
    op.create_index(op.f("ix_case_chat_turns_case_id"), "case_chat_turns", ["case_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_case_chat_turns_case_id"), table_name="case_chat_turns")
    op.drop_table("case_chat_turns")
    op.drop_table("case_chat_states")
    op.drop_column("cases", "case_snapshot_hash")
    op.drop_column("cases", "case_version")
