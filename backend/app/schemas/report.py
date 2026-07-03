from app.schemas.rag import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    EvidenceReference,
    QueryRequest as ReportRequest,
    ReportWorkflowResponse,
    ResumeRequest as ReportResumeRequest,
    ReviewStatusUpdate,
)

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FindingStatus = Literal["confirmed", "candidate", "unknown"]
ReportSourceType = Literal[
    "user_input",
    "analyst_input",
    "log",
    "document",
    "rag",
    "system_rule",
]
ReportConfidence = Literal["high", "medium", "low"]
CaseSeverity = Literal["critical", "high", "medium", "low", "unknown"]
CaseStatus = Literal[
    "new",
    "triage",
    "investigating",
    "contained",
    "resolved",
    "unknown",
]
ReportSectionStatus = Literal["complete", "partial", "missing"]
DeterministicReportStatus = Literal["draft", "incomplete", "ready_for_review"]
GapPriority = Literal["high", "medium", "low"]
IncidentReportType = Literal["incident_analysis"]


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


class ReportGap(BaseModel):
    gap_id: str
    section_id: str
    title: str
    description: str
    priority: GapPriority
    evidence_ids: list[str] = Field(default_factory=list)


class ReportSection(BaseModel):
    id: str
    title: str
    required: bool
    status: ReportSectionStatus
    content: dict[str, Any] = Field(default_factory=dict)
    source_fact_ids: list[str] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    confirmed_findings: int = 0
    candidate_findings: int = 0
    unknown_findings: int = 0
    evidence_count: int = 0
    gap_count: int = 0


class ReportViewModel(BaseModel):
    case_id: str
    report_type: IncidentReportType = "incident_analysis"
    generated_at: datetime
    report_status: DeterministicReportStatus
    sections: list[ReportSection]
    gaps: list[ReportGap] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: ReportMetadata = Field(default_factory=ReportMetadata)


__all__ = [
    "CaseFactPack",
    "CaseInformationCompleteness",
    "CaseCreate",
    "CyberCaseReport",
    "EvidenceReference",
    "CaseListItem",
    "CaseUpdate",
    "ReportRequest",
    "ReportResumeRequest",
    "ReportViewModel",
    "ReportWorkflowResponse",
    "StructuredCase",
    "ReviewStatusUpdate",
]
