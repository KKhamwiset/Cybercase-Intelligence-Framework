"""remove non-chat tables while preserving the chat-only schema

Revision ID: 0008_chat_user_only_cleanup
Revises: 0007_retrieval_snapshots
Create Date: 2026-08-03 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_chat_user_only_cleanup"
down_revision: Union[str, None] = "0007_retrieval_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RETAINED_TABLES = (
    "users",
    "chat_threads",
    "chat_messages",
    "chat_runs",
)
DROP_TABLES = (
    "retrieval_snapshots",
    "report_sessions",
    "reports",
    "case_chat_turns",
    "case_chat_states",
    "cases",
)


def _preflight_inbound_foreign_keys() -> None:
    unexpected = op.get_bind().execute(
        sa.text(
            """
            SELECT
                source_namespace.nspname AS source_schema,
                source_table.relname AS source_table,
                constraint_record.conname AS constraint_name,
                target_table.relname AS target_table
            FROM pg_constraint AS constraint_record
            JOIN pg_class AS source_table
              ON source_table.oid = constraint_record.conrelid
            JOIN pg_namespace AS source_namespace
              ON source_namespace.oid = source_table.relnamespace
            JOIN pg_class AS target_table
              ON target_table.oid = constraint_record.confrelid
            JOIN pg_namespace AS target_namespace
              ON target_namespace.oid = target_table.relnamespace
            WHERE constraint_record.contype = 'f'
              AND target_namespace.nspname = current_schema()
              AND target_table.relname IN (
                  'retrieval_snapshots',
                  'report_sessions',
                  'reports',
                  'case_chat_turns',
                  'case_chat_states',
                  'cases'
              )
              AND NOT (
                  source_namespace.nspname = current_schema()
                  AND source_table.relname IN (
                      'retrieval_snapshots',
                      'report_sessions',
                      'reports',
                      'case_chat_turns',
                      'case_chat_states',
                      'cases'
                  )
              )
            ORDER BY
                source_namespace.nspname,
                source_table.relname,
                constraint_record.conname
            """
        )
    ).mappings().all()
    if unexpected:
        details = ", ".join(
            f"{row['source_schema']}.{row['source_table']}."
            f"{row['constraint_name']} -> {row['target_table']}"
            for row in unexpected
        )
        raise RuntimeError(
            "Refusing chat-only cleanup because unexpected inbound foreign "
            f"keys exist: {details}"
        )


def upgrade() -> None:
    _preflight_inbound_foreign_keys()
    op.drop_table("retrieval_snapshots")
    op.drop_table("report_sessions")
    op.drop_table("reports")
    op.drop_table("case_chat_turns")
    op.drop_table("case_chat_states")
    op.drop_table("cases")


def downgrade() -> None:
    raise RuntimeError(
        "This cleanup migration is irreversible; restore the database from a "
        "verified backup to recover the removed non-chat tables."
    )
