"""Typed report output and chat-report API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReportSupportType = Literal[
    "user_reported",
    "extraction_candidate",
    "general_technical_knowledge",
    "mitre_mapping_candidate",
    "unknown",
]
ReportStatus = Literal["provisional_unverified"]
ReportPersistenceStatus = Literal["completed", "failed"]
ReportValidationStatus = Literal["validated", "failed"]
ReportSectionId = Literal[
    "executive_summary",
    "case_background_scope",
    "evidence_findings",
    "individuals_accounts_systems_roles",
    "chronological_timeline",
    "technical_analysis_mitre",
    "conclusions_limitations_next_steps",
]
ReportHeading = Literal[
    "Executive Summary",
    "Case Background and Scope",
    "Evidence Findings",
    "Individuals, Accounts, Systems, and Reported Roles",
    "Chronological Timeline",
    "Technical Analysis and MITRE ATT&CK Mapping",
    "Conclusions, Limitations, and Recommended Next Investigative Steps",
]

REPORT_SECTION_IDS: tuple[str, ...] = (
    "executive_summary",
    "case_background_scope",
    "evidence_findings",
    "individuals_accounts_systems_roles",
    "chronological_timeline",
    "technical_analysis_mitre",
    "conclusions_limitations_next_steps",
)

REPORT_SECTION_HEADINGS: dict[str, str] = {
    "executive_summary": "Executive Summary",
    "case_background_scope": "Case Background and Scope",
    "evidence_findings": "Evidence Findings",
    "individuals_accounts_systems_roles": (
        "Individuals, Accounts, Systems, and Reported Roles"
    ),
    "chronological_timeline": "Chronological Timeline",
    "technical_analysis_mitre": "Technical Analysis and MITRE ATT&CK Mapping",
    "conclusions_limitations_next_steps": (
        "Conclusions, Limitations, and Recommended Next Investigative Steps"
    ),
}


class ReportClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=80)
    section_id: ReportSectionId
    text: str = Field(min_length=1, max_length=4_000)
    support_type: ReportSupportType
    evidence_ids: list[str] = Field(default_factory=list, max_length=32)
    timeline_event_ids: list[str] = Field(default_factory=list, max_length=32)
    mitre_technique_ids: list[str] = Field(default_factory=list, max_length=32)


class ReportSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: ReportSectionId
    heading: ReportHeading
    paragraphs: list[str] = Field(default_factory=list, max_length=16)
    items: list[str] = Field(default_factory=list, max_length=32)


class StructuredReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_version: Literal["baseline_report_v1"]
    status: ReportStatus
    title: str = Field(min_length=1, max_length=200)
    sections: list[ReportSection] = Field(min_length=7, max_length=7)
    claims: list[ReportClaim] = Field(default_factory=list, max_length=96)
    limitations: list[str] = Field(default_factory=list, max_length=32)


class ChatReportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, max_length=255)

    @field_validator("idempotency_key")
    @classmethod
    def normalize_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ChatReportRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: UUID
    thread_id: UUID
    version_number: int
    idempotency_key: str
    source_snapshot_hash: str
    extraction_id: UUID
    extraction_version: str
    prompt_version: str
    provider: str
    model: str
    decoding_settings: dict[str, Any]
    persistence_status: ReportPersistenceStatus
    validation_status: ReportValidationStatus
    report: StructuredReport | None
    validation_errors: list[str]
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    finished_at: datetime | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None


__all__ = [
    "ChatReportCreate",
    "ChatReportRead",
    "REPORT_SECTION_HEADINGS",
    "REPORT_SECTION_IDS",
    "ReportClaim",
    "ReportPersistenceStatus",
    "ReportSection",
    "ReportHeading",
    "ReportSectionId",
    "ReportStatus",
    "ReportSupportType",
    "ReportValidationStatus",
    "StructuredReport",
]
