from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
CaseAnalysisOutputStatus = Literal[
    "not_started", "pending", "completed", "stale", "failed", "expired"
]
CaseOutputSourceType = Literal[
    "analyst_input",
    "user_input",
    "log",
    "document",
    "system_rule",
    "rag",
    "manual_edit",
    "legacy_unverified",
]
CaseOutputReviewStatus = Literal["unreviewed", "accepted", "rejected", "edited"]


def _strip_text(value: str) -> str:
    return value.strip()


def _normalise_string_list(values: list[str]) -> list[str]:
    normalised = [value.strip() for value in values]
    if any(not value for value in normalised):
        raise ValueError("list values must not be empty")
    return list(dict.fromkeys(normalised))


class CaseMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FindingStatus = "unknown"
    confidence: ReportConfidence = "low"
    evidence_ids: list[str] = Field(default_factory=list, max_length=200)
    source_type: ReportSourceType = "analyst_input"
    analyst_verified: bool = False

    @field_validator("evidence_ids")
    @classmethod
    def normalise_evidence_ids(cls, values: list[str]) -> list[str]:
        return _normalise_string_list(values)


class CaseEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=10_000)
    source_type: ReportSourceType = "analyst_input"
    status: FindingStatus = "unknown"
    confidence: ReportConfidence = "low"
    collected_at: datetime | None = None
    analyst_verified: bool = False
    intake_derived: bool = False

    @field_validator("evidence_id", "title", "description")
    @classmethod
    def normalise_text(cls, value: str) -> str:
        return _strip_text(value)


class CaseTimelineEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1, max_length=80)
    timestamp: datetime | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=10_000)
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)

    @field_validator("event_id", "title", "description")
    @classmethod
    def normalise_text(cls, value: str) -> str:
        return _strip_text(value)


class CaseAttackMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_id: str = Field(min_length=1, max_length=80)
    technique_id: str = Field(min_length=1, max_length=40)
    technique_name: str = Field(min_length=1, max_length=255)
    tactic: str | None = Field(default=None, max_length=255)
    rationale: str = Field(default="", max_length=10_000)
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)

    @field_validator("mapping_id", "technique_id", "technique_name", "rationale")
    @classmethod
    def normalise_text(cls, value: str) -> str:
        return _strip_text(value)

    @field_validator("tactic")
    @classmethod
    def normalise_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CaseActionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=10_000)
    status: FindingStatus = "unknown"
    metadata: CaseMetadata = Field(default_factory=CaseMetadata)

    @field_validator("action_id", "title", "description")
    @classmethod
    def normalise_text(cls, value: str) -> str:
        return _strip_text(value)


class StructuredCase(BaseModel):
    # Historical case payloads can contain additive, non-editable fields such as
    # report follow-up answers. Request models below remain strict.
    model_config = ConfigDict(extra="allow")

    case_id: str
    case_version: int = Field(default=1, ge=1)
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


class _CaseAnalystInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    case_type: str | None = Field(default=None, min_length=1, max_length=80)
    status: CaseStatus | None = None
    severity: CaseSeverity | None = None
    incident_summary: str | None = Field(default=None, max_length=20_000)
    affected_users: list[str] | None = Field(default=None, max_length=200)
    affected_assets: list[str] | None = Field(default=None, max_length=200)
    timeline_events: list[CaseTimelineEvent] | None = Field(default=None, max_length=500)
    evidence_items: list[CaseEvidenceItem] | None = Field(default=None, max_length=500)
    containment_actions: list[CaseActionItem] | None = Field(default=None, max_length=500)
    limitations: list[str] | None = Field(default=None, max_length=200)
    analyst_notes: str | None = Field(default=None, max_length=20_000)

    @field_validator("title", "case_type")
    @classmethod
    def normalise_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @field_validator("incident_summary", "analyst_notes")
    @classmethod
    def normalise_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("affected_users", "affected_assets", "limitations")
    @classmethod
    def normalise_lists(cls, values: list[str] | None) -> list[str] | None:
        return _normalise_string_list(values) if values is not None else None

    @model_validator(mode="after")
    def require_analyst_provenance(self) -> "_CaseAnalystInputs":
        for item in self.evidence_items or []:
            if item.intake_derived:
                raise ValueError("intake_derived is system-managed")
            if item.source_type not in {"analyst_input", "user_input", "log", "document"}:
                raise ValueError("analyst evidence cannot claim generated provenance")
        for event in self.timeline_events or []:
            if event.metadata.source_type not in {"analyst_input", "user_input"}:
                raise ValueError("analyst timeline events cannot claim generated provenance")
        for action in self.containment_actions or []:
            if action.metadata.source_type not in {"analyst_input", "user_input"}:
                raise ValueError("analyst containment actions cannot claim generated provenance")
        return self


class CaseCreate(_CaseAnalystInputs):
    title: str = Field(default="Untitled case", min_length=1, max_length=255)
    case_type: str = Field(default="incident", min_length=1, max_length=80)
    status: CaseStatus = "new"
    severity: CaseSeverity = "unknown"
    incident_summary: str = Field(default="", max_length=20_000)
    affected_users: list[str] = Field(default_factory=list, max_length=200)
    affected_assets: list[str] = Field(default_factory=list, max_length=200)
    timeline_events: list[CaseTimelineEvent] = Field(default_factory=list, max_length=500)
    evidence_items: list[CaseEvidenceItem] = Field(default_factory=list, max_length=500)
    containment_actions: list[CaseActionItem] = Field(default_factory=list, max_length=500)
    limitations: list[str] = Field(default_factory=list, max_length=200)
    analyst_notes: str = Field(default="", max_length=20_000)


class CaseUpdate(_CaseAnalystInputs):
    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "CaseUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one editable field is required")
        null_fields = [field for field in self.model_fields_set if getattr(self, field) is None]
        if null_fields:
            raise ValueError("editable fields must not be null: " + ", ".join(sorted(null_fields)))
        return self


class CaseListItem(BaseModel):
    case_id: str
    case_version: int = Field(ge=1)
    title: str
    status: CaseStatus
    severity: CaseSeverity
    updated_at: datetime | None = None


class CaseOutputItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    title: str
    description: str = ""
    source_type: CaseOutputSourceType
    analysis_run_id: str | None = None
    case_version: int
    generated_at: datetime | None = None
    source_references: list[str] = Field(default_factory=list)
    review_status: CaseOutputReviewStatus = "unreviewed"
    status: str = "unknown"
    details: dict[str, Any] = Field(default_factory=dict)


class CaseOutputBucket(BaseModel):
    current_count: int = Field(ge=0)
    items: list[CaseOutputItem] = Field(default_factory=list)
    source_types: list[CaseOutputSourceType] = Field(default_factory=list)

    @model_validator(mode="after")
    def count_matches_items(self) -> "CaseOutputBucket":
        if self.current_count != len(self.items):
            raise ValueError("current_count must match the number of items")
        return self


class CaseHistoricalOutputBucket(BaseModel):
    historical_count: int = Field(ge=0)
    items: list[CaseOutputItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def count_matches_items(self) -> "CaseHistoricalOutputBucket":
        if self.historical_count != len(self.items):
            raise ValueError("historical_count must match the number of items")
        return self


class CaseOutputBuckets(BaseModel):
    evidence: CaseOutputBucket
    gaps: CaseOutputBucket
    attack_mappings: CaseOutputBucket
    recommendations: CaseOutputBucket


class CaseHistoricalOutputBuckets(BaseModel):
    evidence: CaseHistoricalOutputBucket
    gaps: CaseHistoricalOutputBucket
    attack_mappings: CaseHistoricalOutputBucket
    recommendations: CaseHistoricalOutputBucket


class CaseAnalysisOutputState(BaseModel):
    status: CaseAnalysisOutputStatus
    analysis_run_id: str | None = None
    analyzed_case_version: int | None = None
    analyzed_snapshot_hash: str | None = None


class CaseOutputsResponse(BaseModel):
    case_id: str
    case_version: int = Field(ge=1)
    analysis: CaseAnalysisOutputState
    outputs: CaseOutputBuckets
    historical_outputs: CaseHistoricalOutputBuckets


__all__ = [
    "CaseActionItem",
    "CaseAnalysisOutputState",
    "CaseAttackMapping",
    "CaseCreate",
    "CaseEvidenceItem",
    "CaseHistoricalOutputBucket",
    "CaseHistoricalOutputBuckets",
    "CaseListItem",
    "CaseMetadata",
    "CaseOutputBucket",
    "CaseOutputBuckets",
    "CaseOutputItem",
    "CaseOutputsResponse",
    "CaseSeverity",
    "CaseStatus",
    "CaseTimelineEvent",
    "CaseUpdate",
    "FindingStatus",
    "ReportConfidence",
    "ReportSourceType",
    "StructuredCase",
]
