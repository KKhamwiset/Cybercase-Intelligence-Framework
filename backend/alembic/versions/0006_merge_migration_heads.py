"""merge report and durable chat migration heads

Revision ID: 0006_merge_migration_heads
Revises: 0002_create_chat_threads, 0005_single_report_per_case
Create Date: 2026-07-29 00:00:00.000000
"""

from typing import Sequence, Union


revision: str = "0006_merge_migration_heads"
down_revision: tuple[str, str] = (
    "0002_create_chat_threads",
    "0005_single_report_per_case",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
