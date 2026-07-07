from __future__ import annotations

import re

from pydantic import BaseModel, Field

from app.schemas.common import (
    Confidence,
    EvidenceReference,
    EvidenceStatus,
    ReviewStatus,
    SourceType,
)
from app.schemas.report import (
    CaseFact,
    CaseFactPack,
    CaseInformationCompleteness,
    CompletenessField,
    CyberCaseReport,
    Indicator,
    IndicatorType,
    LEGAL_DISCLAIMER,
    LegalRelevanceAssessment,
    MitreAssessment,
    ReportType,
    TimelineEvent,
    WorkflowStatus,
)

INCOMPLETE_TITLE = "Preliminary Report - Incomplete Case Information"
SUFFICIENT_LABEL = "Sufficient for preliminary report"
INCOMPLETE_LABEL = "Incomplete - follow-up required"
REPORT_TYPES = {"overview", "subject", "timeline", "vulnerability"}
TECHNIQUE_ID_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?")
EVIDENCE_ID_PATTERN = re.compile(r"\[(E-\d{3})\]")
COMPLETENESS_THRESHOLD = 80


class ReportWorkflowResponse(BaseModel):
    """Legacy/service response shape used by the RAG-service compatibility path."""

    status: WorkflowStatus
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: str = ""
    report_id: str | None = None
    report: CyberCaseReport | None = None
    case_fact_pack: CaseFactPack | None = None
    completeness: CaseInformationCompleteness | None = None
    missing_information: list[str] = Field(default_factory=list)


class ReportEntity(BaseModel):
    name: str
    kind: str
    attack_id: str = ""
    stix_id: str = ""
    description: str = ""
    relevance: float | None = None
    source: str = "retrieval"


class ReportRelationship(BaseModel):
    source: str
    relationship: str
    target: str
    description: str = ""


class ReportEvidencePacket(BaseModel):
    report_type: ReportType
    user_query: str
    semantic_matches: list[ReportEntity] = Field(default_factory=list)
    graph_entities: list[ReportEntity] = Field(default_factory=list)
    relationships: list[ReportRelationship] = Field(default_factory=list)
    ttp_candidates: list[ReportEntity] = Field(default_factory=list)
    raw_context_excerpt: str = ""


__all__ = [
    "COMPLETENESS_THRESHOLD",
    "EVIDENCE_ID_PATTERN",
    "INCOMPLETE_LABEL",
    "INCOMPLETE_TITLE",
    "LEGAL_DISCLAIMER",
    "REPORT_TYPES",
    "SUFFICIENT_LABEL",
    "TECHNIQUE_ID_PATTERN",
    "CaseFact",
    "CaseFactPack",
    "CaseInformationCompleteness",
    "CompletenessField",
    "Confidence",
    "CyberCaseReport",
    "EvidenceReference",
    "EvidenceStatus",
    "Indicator",
    "IndicatorType",
    "LegalRelevanceAssessment",
    "MitreAssessment",
    "ReportEntity",
    "ReportEvidencePacket",
    "ReportRelationship",
    "ReportType",
    "ReportWorkflowResponse",
    "ReviewStatus",
    "SourceType",
    "TimelineEvent",
    "WorkflowStatus",
]
