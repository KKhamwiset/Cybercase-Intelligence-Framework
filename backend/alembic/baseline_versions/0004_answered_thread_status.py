"""Allow threads to represent a completed terminal analysis."""

from typing import Sequence, Union

from alembic import op


revision: str = "0004_answered_thread_status"
down_revision: Union[str, None] = "0003_case_state_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ANSWERED_STATUS_CHECK = (
    "status IN ('idle', 'processing', 'awaiting_followup', 'answered', 'failed')"
)
_LEGACY_STATUS_CHECK = (
    "status IN ('idle', 'processing', 'awaiting_followup', 'failed')"
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_chat_threads_status",
        "chat_threads",
        type_="check",
    )
    op.create_check_constraint(
        "ck_chat_threads_status",
        "chat_threads",
        _ANSWERED_STATUS_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_chat_threads_status",
        "chat_threads",
        type_="check",
    )
    op.create_check_constraint(
        "ck_chat_threads_status",
        "chat_threads",
        _LEGACY_STATUS_CHECK,
    )
