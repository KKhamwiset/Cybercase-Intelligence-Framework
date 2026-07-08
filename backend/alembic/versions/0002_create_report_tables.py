"""create report tables

Revision ID: 0002_create_report_tables
Revises: 0001_initial_core_schema
Create Date: 2026-07-08 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_create_report_tables"
down_revision: Union[str, None] = "0001_initial_core_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(length=80), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("workflow_status", sa.String(length=40), nullable=False),
        sa.Column("review_status", sa.String(length=40), nullable=False),
        sa.Column("report_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("case_fact_pack_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index(op.f("ix_reports_case_id"), "reports", ["case_id"], unique=False)
    op.create_index(op.f("ix_reports_report_id"), "reports", ["report_id"], unique=False)

    op.create_table(
        "report_sessions",
        sa.Column("session_id", sa.String(length=80), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("request_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "followup_question",
            sa.String(length=2000),
            server_default="",
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
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )
    op.create_index(op.f("ix_report_sessions_case_id"), "report_sessions", ["case_id"], unique=False)
    op.create_index(op.f("ix_report_sessions_session_id"), "report_sessions", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_report_sessions_session_id"), table_name="report_sessions")
    op.drop_index(op.f("ix_report_sessions_case_id"), table_name="report_sessions")
    op.drop_table("report_sessions")
    op.drop_index(op.f("ix_reports_report_id"), table_name="reports")
    op.drop_index(op.f("ix_reports_case_id"), table_name="reports")
    op.drop_table("reports")
