"""persist case-owned retrieval snapshots

Revision ID: 0007_retrieval_snapshots
Revises: 0006_merge_migration_heads
Create Date: 2026-07-29 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_retrieval_snapshots"
down_revision: Union[str, None] = "0006_merge_migration_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retrieval_snapshots",
        sa.Column("retrieval_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=80), nullable=False),
        sa.Column("retrieval_context_id", sa.String(length=160), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("case_snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("snapshot_sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column(
            "schema_version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_id"],
            ["cases.case_id"],
            name="fk_retrieval_snapshots_case_id_cases",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "retrieval_snapshot_id",
            name="pk_retrieval_snapshots",
        ),
        sa.UniqueConstraint(
            "analysis_run_id",
            name="uq_retrieval_snapshots_analysis_run_id",
        ),
        sa.UniqueConstraint(
            "retrieval_context_id",
            name="uq_retrieval_snapshots_retrieval_context_id",
        ),
    )
    op.create_index(
        "ix_retrieval_snapshots_case_id",
        "retrieval_snapshots",
        ["case_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_retrieval_snapshots_case_id",
        table_name="retrieval_snapshots",
    )
    op.drop_table("retrieval_snapshots")
