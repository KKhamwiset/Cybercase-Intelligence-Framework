from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.report import ReportRecord, ReportSessionRecord


class CaseRecord(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(80), primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled case")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    severity: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    reports: Mapped[list[ReportRecord]] = relationship(
        "ReportRecord", back_populates="case", cascade="all, delete-orphan"
    )
    report_sessions: Mapped[list[ReportSessionRecord]] = relationship(
        "ReportSessionRecord", back_populates="case", cascade="all, delete-orphan"
    )
