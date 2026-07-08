from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import (
    Confidence,
    EvidenceReference,
    EvidenceStatus,
    ReviewStatus,
)
from app.schemas.rag import MitreTableRow

IndicatorType = Literal["ip", "domain", "url", "email", "hash", "cve", "file", "other"]
ReportType = Literal["overview", "subject", "timeline", "vulnerability"]
WorkflowStatus = Literal["completed", "followup", "error", "context_expired"]
ReportSectionStatus = Literal["complete", "partial", "missing"]
DeterministicReportStatus = Literal["draft", "incomplete", "ready_for_review"]
GapPriority = Literal["high", "medium", "low"]
IncidentReportType = Literal["incident_analysis"]

LEGAL_DISCLAIMER = (
    "This is preliminary investigation support only and is not a legal conclusion."
)


class CaseFact(BaseModel):
    fact_id: str
    statement: str
    category: str
    status: EvidenceStatus
    confidence: Confidence
    evidence_ids: list[str]
    notes: str | None = None

    @model_validator(mode="after")
    def require_evidence(self) -> "CaseFact":
        if not self.evidence_ids:
            raise ValueError("CaseFact requires at least one evidence_id")
        return self


class TimelineEvent(BaseModel):
    event_id: str
    timestamp: str | None = None
    event: str
    status: EvidenceStatus
    evidence_ids: list[str]

    @model_validator(mode="after")
    def require_evidence(self) -> "TimelineEvent":
        if not self.evidence_ids:
            raise ValueError("TimelineEvent requires at least one evidence_id")
        return self


class Indicator(BaseModel):
    indicator_id: str
    indicator_type: IndicatorType
    value: str
    status: EvidenceStatus
    evidence_ids: list[str]
    notes: str | None = None

    @model_validator(mode="after")
    def require_evidence(self) -> "Indicator":
        if not self.evidence_ids:
            raise ValueError("Indicator requires at least one evidence_id")
        return self


class MitreAssessment(BaseModel):
    technique_id: str
    technique_name: str
    mapping_status: EvidenceStatus
    justification: str
    evidence_ids: list[str]

    @model_validator(mode="after")
    def require_evidence(self) -> "MitreAssessment":
        if not self.evidence_ids:
            raise ValueError("MitreAssessment requires at least one evidence_id")
        return self


class LegalRelevanceAssessment(BaseModel):
    enabled: bool
    provision_reference: str
    preliminary_relevance: str
    status: EvidenceStatus
    evidence_ids: list[str]
    disclaimer: str

    @model_validator(mode="after")
    def validate_legal_guardrails(self) -> "LegalRelevanceAssessment":
        if self.enabled and LEGAL_DISCLAIMER not in self.disclaimer:
            raise ValueError(
                "Legal assessment requires the preliminary legal disclaimer"
            )
        if self.enabled and not self.evidence_ids:
            raise ValueError("Legal assessment requires at least one evidence_id")
        return self


class CompletenessField(BaseModel):
    field_id: str
    label: str
    present: bool
    evidence_ids: list[str] = Field(default_factory=list)


class CaseInformationCompleteness(BaseModel):
    percentage: int
    status: Literal[
        "Sufficient for preliminary report", "Incomplete - follow-up required"
    ]
    missing_fields: list[str]
    fields: list[CompletenessField]


class CaseFactPack(BaseModel):
    facts: list[CaseFact]
    evidence_registry: list[EvidenceReference]
    indicators: list[Indicator]
    timeline: list[TimelineEvent]
    mitre_assessments: list[MitreAssessment]
    legal_assessments: list[LegalRelevanceAssessment]
    missing_information: list[str]
    limitations: list[str]
    completeness_percentage: int
    completeness: CaseInformationCompleteness
    review_status: ReviewStatus

    @model_validator(mode="after")
    def validate_evidence_references(self) -> "CaseFactPack":
        known_ids = {item.evidence_id for item in self.evidence_registry}
        if len(known_ids) != len(self.evidence_registry):
            raise ValueError("Evidence IDs must be unique")

        missing: set[str] = set()
        collections: list[object] = [
            *self.facts,
            *self.indicators,
            *self.timeline,
            *self.mitre_assessments,
            *self.legal_assessments,
        ]
        for item in collections:
            for evidence_id in getattr(item, "evidence_ids", []):
                if evidence_id not in known_ids:
                    missing.add(evidence_id)

        for field in self.completeness.fields:
            for evidence_id in field.evidence_ids:
                if evidence_id not in known_ids:
                    missing.add(evidence_id)

        if missing:
            raise ValueError(
                "Unknown evidence IDs referenced: " + ", ".join(sorted(missing))
            )
        if not 0 <= self.completeness_percentage <= 100:
            raise ValueError("completeness_percentage must be between 0 and 100")
        if self.completeness.percentage != self.completeness_percentage:
            raise ValueError("completeness percentage fields must match")
        return self


class CyberCaseReport(BaseModel):
    report_id: str
    title: str
    report_type: ReportType
    executive_case_summary: str
    case_information_completeness: CaseInformationCompleteness
    evidence_and_indicators_table: list[Indicator]
    incident_timeline: list[TimelineEvent]
    mitre_attack_assessment: list[MitreAssessment]
    evidence_still_required: list[str]
    investigation_next_steps: list[str]
    legal_assessments: list[LegalRelevanceAssessment]
    limitations_and_disclaimers: list[str]
    review_status: ReviewStatus
    case_fact_pack: CaseFactPack
    created_at: str


class GenerateReportRequest(BaseModel):
    query: str
    report_type: ReportType = "overview"
    legal: bool = False
    force_generate: bool = False
    evidence_registry: list[EvidenceReference] = Field(default_factory=list)
    retrieval_context_id: str = ""


ReportRequest = GenerateReportRequest


class GenerateCaseReportRequest(BaseModel):
    """Request body for POST /cases/{case_id}/report — no query required."""
    report_type: ReportType = "overview"
    legal: bool = False
    force_generate: bool = False


class ReportInputSnapshot(BaseModel):
    retrieval_context_id: str
    query: str = ""
    context: str
    rag_result: dict[str, Any] = Field(default_factory=dict)
    answer: str = ""
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class ReportResumeRequest(BaseModel):
    session_id: str
    answer: str


class ReviewStatusUpdate(BaseModel):
    review_status: ReviewStatus


class ReportCompletedResponse(BaseModel):
    status: Literal["completed"]
    report_id: str
    report: CyberCaseReport
    answer: str = ""


class ReportFollowUpResponse(BaseModel):
    status: Literal["followup"]
    session_id: str
    followup_question: str
    retrieval_context_id: str = ""
    completeness: CaseInformationCompleteness
    missing_information: list[str] = Field(default_factory=list)


class ReportErrorResponse(BaseModel):
    status: Literal["error", "context_expired"]
    error_code: str
    message: str


ReportWorkflowResponse = Annotated[
    ReportCompletedResponse | ReportFollowUpResponse | ReportErrorResponse,
    Field(discriminator="status"),
]


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


class ReportRegistryItem(BaseModel):
    report_id: str
    case_id: str
    case_title: str
    case_status: str
    severity: str
    report_type: str
    workflow_status: str
    review_status: str
    created_at: str
    updated_at: str
    executive_summary_preview: str


__all__ = [
    "CaseFact",
    "CaseFactPack",
    "CaseInformationCompleteness",
    "CompletenessField",
    "CyberCaseReport",
    "DeterministicReportStatus",
    "EvidenceReference",
    "GapPriority",
    "GenerateCaseReportRequest",
    "GenerateReportRequest",
    "IncidentReportType",
    "Indicator",
    "IndicatorType",
    "LEGAL_DISCLAIMER",
    "LegalRelevanceAssessment",
    "MitreAssessment",
    "ReportCompletedResponse",
    "ReportErrorResponse",
    "ReportFollowUpResponse",
    "ReportGap",
    "ReportInputSnapshot",
    "ReportMetadata",
    "ReportRegistryItem",
    "ReportRequest",
    "ReportResumeRequest",
    "ReportSection",
    "ReportSectionStatus",
    "ReportType",
    "ReportViewModel",
    "ReportWorkflowResponse",
    "ReviewStatusUpdate",
    "TimelineEvent",
    "WorkflowStatus",
]
