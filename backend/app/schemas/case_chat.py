from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


CaseChatAction = Literal["analyze", "refresh_analysis", "question", "followup"]
CaseChatTurnType = Literal["analysis", "question", "followup"]
CaseChatTurnStatus = Literal["pending", "completed", "failed", "expired", "stale"]
CaseChatWorkspaceStatus = Literal["idle", "pending", "completed", "failed", "expired", "stale"]
CaseAnalysisStatus = Literal["missing", "pending", "completed", "stale", "expired", "failed"]
CaseReportReadinessReason = Literal[
    "analysis_required",
    "analysis_pending",
    "analysis_stale",
    "context_expired",
    "analysis_failed",
    "ready",
]


class CaseChatMessageRequest(BaseModel):
    action: CaseChatAction
    message: str = ""

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        return value.strip()

    def model_post_init(self, __context: object) -> None:
        if self.action in {"question", "followup"} and not self.message:
            raise ValueError("message is required for question and followup actions")


class CaseChatTurnView(BaseModel):
    turn_id: str
    role: Literal["user", "assistant"]
    content: str
    turn_type: CaseChatTurnType
    turn_status: CaseChatTurnStatus
    case_version: int
    case_snapshot_hash: str
    created_at: datetime | None = None


class CaseChatContextSummary(BaseModel):
    title: str
    incident_summary: str
    case_version: int
    case_snapshot_hash: str
    evidence_count: int = 0
    gap_count: int = 0
    attack_mapping_count: int = 0
    gaps: list[str] = Field(default_factory=list)
    attack_candidates: list["CaseChatAttackCandidate"] = Field(default_factory=list)
    updated_at: datetime | None = None


class CaseChatAttackCandidate(BaseModel):
    mapping_id: str = ""
    technique_id: str = ""
    technique_name: str = ""
    tactic: str | None = None
    status: str = "unknown"


class CaseChatWorkspaceView(BaseModel):
    case_id: str
    context: CaseChatContextSummary
    turns: list[CaseChatTurnView] = Field(default_factory=list)
    status: CaseChatWorkspaceStatus
    requires_followup: bool = False
    active_session_id: str | None = None
    latest_retrieval_context_id: str | None = None
    analysis_case_version: int | None = None
    analysis_snapshot_hash: str | None = None
    report_eligible: bool = False


class CaseChatMessageResponse(BaseModel):
    status: CaseChatWorkspaceStatus
    turn_status: CaseChatTurnStatus
    turn_type: CaseChatTurnType
    message: str = ""
    assistant_message: str | None = None
    followup_question: str | None = None
    session_id: str | None = None
    retrieval_context_id: str | None = None
    case_version: int
    case_snapshot_hash: str
    report_eligible: bool = False
    requires_followup: bool = False
    idempotent: bool = False


class CaseReportReadiness(BaseModel):
    case_id: str
    current_case_version: int
    current_case_snapshot_hash: str
    analysis_status: CaseAnalysisStatus
    report_eligible: bool
    reason: CaseReportReadinessReason
    latest_analysis_turn_id: str | None = None
    latest_retrieval_context_id: str | None = None


__all__ = [
    "CaseChatAction",
    "CaseAnalysisStatus",
    "CaseChatAttackCandidate",
    "CaseChatContextSummary",
    "CaseChatMessageRequest",
    "CaseChatMessageResponse",
    "CaseChatTurnStatus",
    "CaseChatTurnType",
    "CaseChatTurnView",
    "CaseChatWorkspaceStatus",
    "CaseChatWorkspaceView",
    "CaseReportReadiness",
    "CaseReportReadinessReason",
]
