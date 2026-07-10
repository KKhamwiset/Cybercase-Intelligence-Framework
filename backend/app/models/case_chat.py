from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.case import CaseRecord


class CaseChatState(Base):
    __tablename__ = "case_chat_states"

    case_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("cases.case_id", ondelete="CASCADE"), primary_key=True
    )
    case_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    case_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    active_session_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    requires_followup: Mapped[bool] = mapped_column(nullable=False, default=False)
    latest_analysis_turn_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latest_retrieval_context_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    analysis_case_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    analysis_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pending_idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped[CaseRecord] = relationship("CaseRecord", back_populates="chat_state")


class CaseChatTurn(Base):
    __tablename__ = "case_chat_turns"
    __table_args__ = (
        UniqueConstraint("case_id", "idempotency_key", name="uq_case_chat_turns_case_idempotency"),
    )

    turn_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    case_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    turn_type: Mapped[str] = mapped_column(String(20), nullable=False)
    turn_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    case_version: Mapped[int] = mapped_column(Integer, nullable=False)
    case_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    rag_session_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    retrieval_context_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payload_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    analysis_outputs_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    case: Mapped[CaseRecord] = relationship("CaseRecord", back_populates="chat_turns")


__all__ = ["CaseChatState", "CaseChatTurn"]
