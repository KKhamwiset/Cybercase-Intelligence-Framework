"""persist structured outputs on case analysis turns

Revision ID: 0004_case_chat_analysis_outputs
Revises: 0003_case_chat_state
Create Date: 2026-07-10 00:00:01.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_case_chat_analysis_outputs"
down_revision: Union[str, None] = "0003_case_chat_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_chat_turns",
        sa.Column(
            "analysis_outputs_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("case_chat_turns", "analysis_outputs_json")
