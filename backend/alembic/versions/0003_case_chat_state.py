"""add durable case chat and canonical case snapshots

Revision ID: 0003_case_chat_state
Revises: 0002_create_report_tables
Create Date: 2026-07-10 00:00:00.000000
"""

import hashlib
import json
import unicodedata
from copy import deepcopy
from typing import Any, Mapping, Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_case_chat_state"
down_revision: Union[str, None] = "0002_create_report_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CONTEXT_KEYS = (
    "title",
    "case_type",
    "status",
    "severity",
    "incident_summary",
    "affected_users",
    "affected_assets",
    "timeline_events",
    "evidence_items",
    "attack_mappings",
    "containment_actions",
    "recommendations",
    "gaps",
    "limitations",
    "analyst_notes",
)
_ARRAY_SORT_FIELDS: dict[str, tuple[str, ...]] = {
    "timeline_events": ("event_id", "title", "timestamp"),
    "evidence_items": ("evidence_id", "title", "description"),
    "attack_mappings": ("mapping_id", "technique_id", "technique_name"),
    "containment_actions": ("action_id", "title", "description"),
    "recommendations": ("action_id", "title", "description"),
}


def _normalise(value: Any) -> Any:
    if isinstance(value, str):
        value = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
        return "\n".join(line.rstrip() for line in value.strip().split("\n"))
    if isinstance(value, Mapping):
        return {
            str(key): _normalise(item)
            for key, item in value.items()
            if item is not None
        }
    if isinstance(value, (list, tuple, set)):
        return [_normalise(item) for item in value]
    return value


def _sort_records(values: list[Any], fields: tuple[str, ...]) -> list[Any]:
    def key(item: Any) -> tuple[str, ...]:
        if not isinstance(item, Mapping):
            return (str(item),)
        return tuple(str(item.get(field, "")) for field in fields)

    return sorted(values, key=key)


def _build_payload_from_values(
    *,
    title: str,
    status: str,
    severity: str,
    data: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = deepcopy(dict(data or {}))
    source["title"] = title
    source["status"] = status
    source["severity"] = severity
    payload: dict[str, Any] = {}
    for field in _CONTEXT_KEYS:
        value = source.get(field, [] if field in _ARRAY_SORT_FIELDS else "")
        value = _normalise(value)
        if field in _ARRAY_SORT_FIELDS:
            if not isinstance(value, list):
                value = []
            value = _sort_records(value, _ARRAY_SORT_FIELDS[field])
        elif field in {"affected_users", "affected_assets", "gaps", "limitations"}:
            if not isinstance(value, list):
                value = []
            value = sorted(value, key=lambda item: str(item))
        payload[field] = value
    return payload


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _snapshot_hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


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
        payload = _build_payload_from_values(
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
                "snapshot_hash": _snapshot_hash(payload),
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
