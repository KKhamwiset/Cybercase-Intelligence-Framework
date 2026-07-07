from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import Confidence

FindingStatus = Literal["confirmed", "candidate", "unknown"]
ReportSourceType = Literal[
    "user_input",
    "analyst_input",
    "log",
    "document",
    "rag",
    "system_rule",
]
ReportConfidence = Confidence
CaseSeverity = Literal["critical", "high", "medium", "low", "unknown"]
CaseStatus = Literal[
    "new",
    "triage",
    "investigating",
    "contained",
    "resolved",
    "unknown",
]


class CaseMetadata(BaseModel):
    status: FindingStatus = "unknown"
    confidence: ReportConfidence = "low"
    evidence_ids: list[str] = Field(default_factory=list)
    source_type: ReportSourceType = "user_input"
    analyst_verified: bool = False


class CaseEvidenceItem(BaseModel):
    evidence_id: str
    title: str
    description: str = ""
    source_type: ReportSourceType = "user_input"
    status: FindingStatus = "unknown"
    confidence: ReportConfidence = "low"
    collected_at: datetime | None = None
    analyst_verified: bool = False


class CaseTimelineEvent(BaseModel):
    event_id: str
    timestamp: datetime | None = None
    title: str
    description: str = ""
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)


class CaseAttackMapping(BaseModel):
    mapping_id: str
    technique_id: str
    technique_name: str
    tactic: str | None = None
    rationale: str = ""
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)


class CaseActionItem(BaseModel):
    action_id: str
    title: str
    description: str = ""
    status: FindingStatus = "unknown"
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)


class StructuredCase(BaseModel):
    model_config = ConfigDict(extra="allow")

    case_id: str
    title: str = "Untitled case"
    case_type: str = "incident"
    status: CaseStatus = "unknown"
    severity: CaseSeverity = "unknown"
    incident_summary: str = ""
    affected_users: list[str] = Field(default_factory=list)
    affected_assets: list[str] = Field(default_factory=list)
    timeline_events: list[CaseTimelineEvent] = Field(default_factory=list)
    evidence_items: list[CaseEvidenceItem] = Field(default_factory=list)
    attack_mappings: list[CaseAttackMapping] = Field(default_factory=list)
    containment_actions: list[CaseActionItem] = Field(default_factory=list)
    recommendations: list[CaseActionItem] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    analyst_notes: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @model_validator(mode="after")
    def require_case_id(self) -> "StructuredCase":
        if not self.case_id.strip():
            raise ValueError("case_id is required")
        return self


class CaseCreate(BaseModel):
    title: str = "Untitled case"
    case_type: str = "incident"
    status: CaseStatus = "new"
    severity: CaseSeverity = "unknown"
    incident_summary: str = ""


class CaseUpdate(BaseModel):
    title: str | None = None
    case_type: str | None = None
    status: CaseStatus | None = None
    severity: CaseSeverity | None = None
    incident_summary: str | None = None
    affected_users: list[str] | None = None
    affected_assets: list[str] | None = None
    timeline_events: list[CaseTimelineEvent] | None = None
    evidence_items: list[CaseEvidenceItem] | None = None
    attack_mappings: list[CaseAttackMapping] | None = None
    containment_actions: list[CaseActionItem] | None = None
    recommendations: list[CaseActionItem] | None = None
    gaps: list[str] | None = None
    limitations: list[str] | None = None
    analyst_notes: str | None = None


class CaseListItem(BaseModel):
    case_id: str
    title: str
    status: CaseStatus
    severity: CaseSeverity
    updated_at: datetime | None = None


__all__ = [
    "CaseActionItem",
    "CaseAttackMapping",
    "CaseCreate",
    "CaseEvidenceItem",
    "CaseListItem",
    "CaseMetadata",
    "CaseSeverity",
    "CaseStatus",
    "CaseTimelineEvent",
    "CaseUpdate",
    "FindingStatus",
    "ReportConfidence",
    "ReportSourceType",
    "StructuredCase",
]
