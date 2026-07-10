from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.case import CaseRecord


class ReportRecord(Base):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("case_id", name="uq_reports_case_id"),)

    report_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    case_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False
    )
    report_type: Mapped[str] = mapped_column(String(40), nullable=False, default="overview")
    workflow_status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    review_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    report_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    case_fact_pack_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    case: Mapped[CaseRecord] = relationship("CaseRecord", back_populates="report")


class ReportSessionRecord(Base):
    __tablename__ = "report_sessions"

    session_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    case_id: Mapped[str] = mapped_column(
        String(80), ForeignKey("cases.case_id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    followup_question: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    case: Mapped[CaseRecord] = relationship("CaseRecord", back_populates="report_sessions")
