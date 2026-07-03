from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


EvidenceStatus = Literal["confirmed", "reported", "inferred", "unknown"]
ReviewStatus = Literal["draft", "ai_generated", "reviewed", "approved"]
SourceType = Literal[
    "user_input",
    "uploaded_file",
    "log",
    "rag_source",
    "mitre_source",
    "legal_source",
]
Confidence = Literal["low", "medium", "high"]
IndicatorType = Literal["ip", "domain", "url", "email", "hash", "cve", "file", "other"]
ReportType = Literal["overview", "subject", "timeline", "vulnerability"]
WorkflowStatus = Literal["completed", "followup"]

LEGAL_DISCLAIMER = (
    "This is preliminary investigation support only and is not a legal conclusion."
)


class EvidenceReference(BaseModel):
    evidence_id: str
    source_type: SourceType
    source_name: str
    excerpt: str | None = None
    page_number: int | None = None
    line_reference: str | None = None
    file_hash_sha256: str | None = None
    content_type: str | None = None
    uploaded_at: str | None = None
    extraction_method: str | None = None


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
            raise ValueError("Legal assessment requires the preliminary legal disclaimer")
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

    # Backward-compatible fields for old report clients.
    case_summary: str = ""
    detected_indicators: list[str] = Field(default_factory=list)
    mitre_mapping: list[str] = Field(default_factory=list)
    mapping_justification: str = ""
    evidence_to_investigate: list[str] = Field(default_factory=list)
    preliminary_recommendations: list[str] = Field(default_factory=list)
    system_limitations: str = ""


class QueryRequest(BaseModel):
    query: str
    use_agent: bool = True
    report_type: ReportType = "overview"
    legal: bool = False
    force_generate: bool = False
    evidence_registry: list[EvidenceReference] = Field(default_factory=list)
    retrieval_context_id: str = ""


class MitreTableRow(BaseModel):
    """One entry of the MITRE mapping table produced by the RAG service.

    Mirrors ``rag_service`` ``MitreTableRow``; rows are noise-filtered there
    (answer-grounded + rerank-score threshold). ``relevance`` tells the
    frontend whether the LLM actually used the entity in its case summary
    (``cited_in_answer``) or it merely scored well in retrieval
    (``retrieved_only``).
    """

    technique_id: str = ""
    name: str
    entity_type: str = ""
    tactic: str | None = None
    score: float | None = None
    source: Literal["vector", "graph"] = "vector"
    relevance: Literal["cited_in_answer", "retrieved_only"] = "retrieved_only"
    description: str = ""
    mitre_url: str | None = None


class QueryResponse(BaseModel):
    status: Literal["completed", "followup"]
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    retrieval_context_id: str = ""
    mitre_table: list[MitreTableRow] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    session_id: str
    answer: str


class ReportWorkflowResponse(BaseModel):
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


class ReviewStatusUpdate(BaseModel):
    review_status: ReviewStatus
