"""enforce one current report per case

Revision ID: 0005_single_report_per_case
Revises: 0004_case_chat_analysis_outputs
Create Date: 2026-07-10 00:00:02.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_single_report_per_case"
down_revision: Union[str, None] = "0004_case_chat_analysis_outputs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            WITH ranked_reports AS (
                SELECT
                    report_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY case_id
                        ORDER BY created_at DESC, updated_at DESC, report_id DESC
                    ) AS report_rank
                FROM reports
            )
            DELETE FROM reports
            USING ranked_reports
            WHERE reports.report_id = ranked_reports.report_id
              AND ranked_reports.report_rank > 1
            """
        )
    )
    op.drop_index("ix_reports_case_id", table_name="reports")
    op.create_unique_constraint("uq_reports_case_id", "reports", ["case_id"])


def downgrade() -> None:
    op.drop_constraint("uq_reports_case_id", "reports", type_="unique")
    op.create_index("ix_reports_case_id", "reports", ["case_id"], unique=False)
