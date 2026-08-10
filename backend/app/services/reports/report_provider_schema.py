"""Provider-facing report schema with unambiguous scalar claim references."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chat.reports import (
    ReportClaim,
    ReportSection,
    ReportSectionId,
    ReportStatus,
    StructuredReport,
)


class _ProviderClaimBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=80)
    section_id: ReportSectionId
    text: str = Field(min_length=1, max_length=4_000)


class ProviderIncidentEvidenceClaim(_ProviderClaimBase):
    claim_kind: Literal["incident_evidence"]
    support_type: Literal["user_reported", "extraction_candidate"]
    evidence_id: str


class ProviderIncidentTimelineClaim(_ProviderClaimBase):
    claim_kind: Literal["incident_timeline"]
    support_type: Literal["user_reported", "extraction_candidate"]
    timeline_event_id: str


class ProviderMitreEvidenceClaim(_ProviderClaimBase):
    claim_kind: Literal["mitre_evidence"]
    support_type: Literal["mitre_mapping_candidate"]
    evidence_id: str
    mitre_technique_id: str


class ProviderMitreTimelineClaim(_ProviderClaimBase):
    claim_kind: Literal["mitre_timeline"]
    support_type: Literal["mitre_mapping_candidate"]
    timeline_event_id: str
    mitre_technique_id: str


class ProviderGeneralTechnicalKnowledgeClaim(_ProviderClaimBase):
    claim_kind: Literal["general_technical_knowledge"]
    support_type: Literal["general_technical_knowledge"]


class ProviderUnknownClaim(_ProviderClaimBase):
    claim_kind: Literal["unknown"]
    support_type: Literal["unknown"]


ProviderReportClaim = (
    ProviderIncidentEvidenceClaim
    | ProviderIncidentTimelineClaim
    | ProviderMitreEvidenceClaim
    | ProviderMitreTimelineClaim
    | ProviderGeneralTechnicalKnowledgeClaim
    | ProviderUnknownClaim
)


class ProviderStructuredReport(BaseModel):
    """Strict provider contract converted into the stable public report model."""

    model_config = ConfigDict(extra="forbid")

    report_version: Literal["baseline_report_v1"]
    status: ReportStatus
    title: str = Field(min_length=1, max_length=200)
    sections: list[ReportSection] = Field(min_length=7, max_length=7)
    claims: list[ProviderReportClaim] = Field(default_factory=list, max_length=96)
    limitations: list[str] = Field(default_factory=list, max_length=32)


def provider_report_to_structured_report(
    report: ProviderStructuredReport,
) -> StructuredReport:
    """Convert scalar provider claims exactly into public reference arrays."""

    claims: list[ReportClaim] = []
    for claim in report.claims:
        common = {
            "claim_id": claim.claim_id,
            "section_id": claim.section_id,
            "text": claim.text,
            "support_type": claim.support_type,
        }
        evidence_ids: list[str] = []
        timeline_event_ids: list[str] = []
        mitre_technique_ids: list[str] = []

        if isinstance(
            claim,
            (ProviderIncidentEvidenceClaim, ProviderMitreEvidenceClaim),
        ):
            evidence_ids = [claim.evidence_id]
        if isinstance(
            claim,
            (ProviderIncidentTimelineClaim, ProviderMitreTimelineClaim),
        ):
            timeline_event_ids = [claim.timeline_event_id]
        if isinstance(
            claim,
            (ProviderMitreEvidenceClaim, ProviderMitreTimelineClaim),
        ):
            mitre_technique_ids = [claim.mitre_technique_id]

        claims.append(
            ReportClaim(
                **common,
                evidence_ids=evidence_ids,
                timeline_event_ids=timeline_event_ids,
                mitre_technique_ids=mitre_technique_ids,
            )
        )

    return StructuredReport(
        report_version=report.report_version,
        status=report.status,
        title=report.title,
        sections=report.sections,
        claims=claims,
        limitations=report.limitations,
    )


__all__ = [
    "ProviderGeneralTechnicalKnowledgeClaim",
    "ProviderIncidentEvidenceClaim",
    "ProviderIncidentTimelineClaim",
    "ProviderMitreEvidenceClaim",
    "ProviderMitreTimelineClaim",
    "ProviderReportClaim",
    "ProviderStructuredReport",
    "ProviderUnknownClaim",
    "provider_report_to_structured_report",
]
