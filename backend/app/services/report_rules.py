from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from app.schemas.report import (
    CaseAttackMapping,
    CaseMetadata,
    FindingStatus,
    ReportGap,
    StructuredCase,
)


def normalize_case_for_reporting(case: StructuredCase) -> StructuredCase:
    normalized = case.model_copy(deep=True)
    evidence_ids = {item.evidence_id for item in normalized.evidence_items}

    for mapping in normalized.attack_mappings:
        _normalize_metadata(mapping.metadata, evidence_ids)
        if not mapping.rationale.strip() or not _has_known_evidence(mapping.metadata, evidence_ids):
            mapping.metadata.status = "candidate"
            mapping.metadata.analyst_verified = False
        if mapping.metadata.source_type == "rag" and not mapping.metadata.analyst_verified:
            mapping.metadata.status = "candidate"

    for event in normalized.timeline_events:
        _normalize_metadata(event.metadata, evidence_ids)

    for action in [*normalized.containment_actions, *normalized.recommendations]:
        _normalize_metadata(action.metadata, evidence_ids)
        if action.metadata.status != action.status:
            action.status = action.metadata.status

    return normalized


def evaluate_report_gaps(case: StructuredCase) -> list[ReportGap]:
    gaps: list[ReportGap] = []
    evidence_ids = {item.evidence_id for item in case.evidence_items}

    if not case.incident_summary.strip():
        gaps.append(
            ReportGap(
                gap_id="gap_incident_narrative",
                section_id="executive_summary",
                title="Incident narrative missing",
                description="No incident summary is available, so the report cannot state what happened as a confirmed fact.",
                priority="high",
            )
        )

    if not case.timeline_events:
        gaps.append(
            ReportGap(
                gap_id="gap_timeline",
                section_id="attack_timeline",
                title="Timeline missing",
                description="No chronological events are available for the attack timeline.",
                priority="medium",
            )
        )

    for mapping in case.attack_mappings:
        if not mapping.rationale.strip() or not _has_known_evidence(mapping.metadata, evidence_ids):
            gaps.append(
                ReportGap(
                    gap_id=f"gap_mapping_{mapping.mapping_id}",
                    section_id="mitre_attack_mapping",
                    title=f"{mapping.technique_id} needs analyst validation",
                    description="The ATT&CK mapping is missing supporting evidence or rationale and is shown as a candidate finding.",
                    priority="medium",
                    evidence_ids=_known_evidence_ids(mapping.metadata, evidence_ids),
                )
            )

    if not case.affected_users and not case.affected_assets:
        gaps.append(
            ReportGap(
                gap_id="gap_scope",
                section_id="scope_and_affected_assets",
                title="Affected scope missing",
                description="Affected users and assets are not recorded.",
                priority="medium",
            )
        )

    if not case.containment_actions:
        gaps.append(
            ReportGap(
                gap_id="gap_containment",
                section_id="containment_and_response_actions",
                title="Containment status missing",
                description="No containment or response actions are recorded.",
                priority="medium",
            )
        )

    if not case.evidence_items:
        gaps.append(
            ReportGap(
                gap_id="gap_evidence",
                section_id="evidence_register",
                title="Evidence register empty",
                description="No evidence items are available, so findings must remain unsupported until evidence is added.",
                priority="high",
            )
        )

    return _dedupe_gaps(gaps)


def group_mappings_by_tactic(mappings: Iterable[CaseAttackMapping]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for mapping in mappings:
        tactic = mapping.tactic or "Unassigned tactic"
        grouped[tactic].append(
            {
                "mapping_id": mapping.mapping_id,
                "technique_id": mapping.technique_id,
                "technique_name": mapping.technique_name,
                "rationale": mapping.rationale,
                "status": mapping.metadata.status,
                "confidence": mapping.metadata.confidence,
                "evidence_ids": mapping.metadata.evidence_ids,
                "analyst_verified": mapping.metadata.analyst_verified,
                "source_type": mapping.metadata.source_type,
            }
        )
    return [
        {"tactic": tactic, "mappings": items}
        for tactic, items in sorted(grouped.items(), key=lambda item: item[0].lower())
    ]


def count_statuses(case: StructuredCase) -> dict[FindingStatus, int]:
    counts: dict[FindingStatus, int] = {"confirmed": 0, "candidate": 0, "unknown": 0}
    metadata_items = [
        *(item.metadata for item in case.timeline_events),
        *(item.metadata for item in case.attack_mappings),
        *(item.metadata for item in case.containment_actions),
        *(item.metadata for item in case.recommendations),
    ]
    for evidence in case.evidence_items:
        counts[evidence.status] += 1
    for metadata in metadata_items:
        counts[metadata.status] += 1
    return counts


def _normalize_metadata(metadata: CaseMetadata, known_evidence_ids: set[str]) -> None:
    metadata.evidence_ids = _known_evidence_ids(metadata, known_evidence_ids)
    if metadata.status == "confirmed" and not metadata.evidence_ids:
        metadata.status = "candidate"
        metadata.analyst_verified = False
    if metadata.source_type == "rag" and not metadata.analyst_verified:
        metadata.status = "candidate"


def _has_known_evidence(metadata: CaseMetadata, known_evidence_ids: set[str]) -> bool:
    return bool(_known_evidence_ids(metadata, known_evidence_ids))


def _known_evidence_ids(metadata: CaseMetadata, known_evidence_ids: set[str]) -> list[str]:
    return [evidence_id for evidence_id in metadata.evidence_ids if evidence_id in known_evidence_ids]


def _dedupe_gaps(gaps: list[ReportGap]) -> list[ReportGap]:
    seen: set[str] = set()
    deduped: list[ReportGap] = []
    for gap in gaps:
        if gap.gap_id in seen:
            continue
        seen.add(gap.gap_id)
        deduped.append(gap)
    return deduped
