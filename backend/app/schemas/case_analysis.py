from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceType = Literal[
    "case_description",
    "evidence_text",
    "follow_up_answer",
    "retrieved_context",
]
ClaimScope = Literal["case_fact", "retrieved_knowledge"]
EntailmentLabel = Literal["entailed", "contradicted", "not_enough_information"]
EvidentialStatus = Literal[
    "reported",
    "corroborated",
    "contradicted",
    "retrieved_knowledge",
    "unsupported",
    "needs_review",
]
ValidationStatus = Literal["accepted", "rejected", "needs_review"]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]
Sha256 = Annotated[
    str,
    Field(min_length=64, max_length=64, pattern=r"^[0-9a-fA-F]{64}$"),
]
AuxiliaryText = Annotated[str, Field(max_length=4_000)]


class EvidenceTextSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=50_000)


class FollowUpAnswerSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=2_000)
    answer: str = Field(min_length=1, max_length=10_000)


class CaseAnalysisRequest(BaseModel):
    retrieval_context_id: UUID
    case_description: str = Field(min_length=1, max_length=50_000)
    case_description_source_id: str = Field(
        default="case-description", min_length=1, max_length=200
    )
    evidence_sources: list[EvidenceTextSource] = Field(
        default_factory=list, max_length=20
    )
    follow_up_answers: list[FollowUpAnswerSource] = Field(
        default_factory=list, max_length=20
    )

    @model_validator(mode="after")
    def source_ids_must_be_unique(self) -> "CaseAnalysisRequest":
        source_ids = [
            self.case_description_source_id,
            *(source.source_id for source in self.evidence_sources),
            *(source.source_id for source in self.follow_up_answers),
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source_id values must be unique")
        if any(source_id.startswith("retrieval:") for source_id in source_ids):
            raise ValueError(
                "source_id values may not use the reserved retrieval: prefix"
            )
        return self


class MitreContextEntry(BaseModel):
    """Frozen mapping row supplied by rag_service; unknown fields are preserved."""

    model_config = ConfigDict(extra="allow")

    technique_id: str = Field(default="", max_length=100)
    name: str = Field(default="", max_length=500)
    entity_type: str = Field(default="", max_length=200)
    tactic: str | None = Field(default=None, max_length=500)
    score: float | None = None
    source: str = Field(default="", max_length=2_000)
    relevance: str = Field(default="", max_length=4_000)
    description: str = Field(default="", max_length=10_000)
    mitre_url: str | None = Field(default=None, max_length=2_000)


class RetrievalContextSnapshot(BaseModel):
    retrieval_context_id: UUID
    query: str = Field(default="", max_length=200_000)
    context: str = Field(max_length=200_000)
    rag_result: dict[str, Any] = Field(default_factory=dict)
    answer: str = Field(default="", max_length=200_000)
    mitre_table: list[MitreContextEntry] = Field(default_factory=list, max_length=100)


class AnalysisSource(BaseModel):
    source_id: Identifier
    source_type: SourceType
    normalized_text: str = Field(min_length=1, max_length=200_000)
    text_sha256: Sha256
    identity_status: Literal["caller_supplied_unverified", "frozen_retrieval_snapshot"]


class DraftClaim(BaseModel):
    """Only fields the LLM may supply for a material atomic claim."""

    model_config = ConfigDict(extra="forbid")

    claim_text: str = Field(min_length=1, max_length=4_000)
    source_id: str = Field(min_length=1, max_length=200)
    exact_quote: str = Field(min_length=1, max_length=10_000)
    claim_scope: ClaimScope


class DraftCaseAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_summary: str = Field(max_length=10_000)
    claims: list[DraftClaim] = Field(default_factory=list, max_length=12)
    candidate_indicators: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    timeline_events: list[AuxiliaryText] = Field(default_factory=list, max_length=100)
    missing_information: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    suggested_follow_up_questions: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    limitations: list[AuxiliaryText] = Field(default_factory=list, max_length=100)


class SemanticValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: EntailmentLabel


class ValidatedClaim(BaseModel):
    claim_id: Identifier
    claim_text: str = Field(min_length=1, max_length=4_000)
    claim_scope: ClaimScope
    source_id: Identifier
    source_type: SourceType | None = None
    source_sha256: Sha256 | None = None
    exact_quote: str = Field(min_length=1, max_length=10_000)
    span_start: int | None = None
    span_end: int | None = None
    evidence_window: str = Field(default="", max_length=10_400)
    entailment_label: EntailmentLabel | None = None
    evidential_status: EvidentialStatus
    validation_status: ValidationStatus
    validation_reasons: list[Identifier] = Field(default_factory=list, max_length=20)


class AnalysisError(BaseModel):
    code: Identifier
    message: str = Field(max_length=10_000)


class ValidationSummary(BaseModel):
    total_material_claims: int = 0
    claims_with_citations: int = 0
    valid_exact_spans: int = 0
    deterministic_mismatches: int = 0
    entailed_claims: int = 0
    contradicted_claims: int = 0
    not_enough_information_claims: int = 0
    unsupported_claims: int = 0
    needs_review_claims: int = 0
    citation_coverage: float = 0.0


class CaseAnalysisArtifact(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)
    retrieval_context_id: UUID
    context_binding_status: Literal["exact_case_text_match", "unverified"]
    analysis_status: Literal["completed", "needs_review"]
    case_summary: str = Field(default="", max_length=10_000)
    claims: list[ValidatedClaim] = Field(default_factory=list, max_length=12)
    candidate_indicators: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    timeline_events: list[AuxiliaryText] = Field(default_factory=list, max_length=100)
    mitre_context: list[MitreContextEntry] = Field(default_factory=list, max_length=100)
    missing_information: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    suggested_follow_up_questions: list[AuxiliaryText] = Field(
        default_factory=list, max_length=100
    )
    limitations: list[AuxiliaryText] = Field(default_factory=list, max_length=100)
    analysis_errors: list[AnalysisError] = Field(default_factory=list, max_length=100)
    sources: list[AnalysisSource] = Field(default_factory=list, max_length=43)
    validation_summary: ValidationSummary = Field(default_factory=ValidationSummary)
