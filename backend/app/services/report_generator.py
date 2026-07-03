from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.report import (
    ReportGap,
    ReportMetadata,
    ReportSection,
    ReportSectionStatus,
    ReportViewModel,
    StructuredCase,
)
from app.services.report_rules import (
    count_statuses,
    evaluate_report_gaps,
    group_mappings_by_tactic,
    normalize_case_for_reporting,
)


class DeterministicReportGenerator:
    def generate(self, case: StructuredCase) -> ReportViewModel:
        normalized = normalize_case_for_reporting(case)
        gaps = evaluate_report_gaps(normalized)
        limitations = self._build_limitations(normalized, gaps)
        sections = self._build_sections(normalized, gaps, limitations)
        counts = count_statuses(normalized)

        return ReportViewModel(
            case_id=normalized.case_id,
            generated_at=datetime.now(timezone.utc),
            report_status=self._report_status(gaps, counts["candidate"], counts["unknown"]),
            sections=sections,
            gaps=gaps,
            limitations=limitations,
            metadata=ReportMetadata(
                confirmed_findings=counts["confirmed"],
                candidate_findings=counts["candidate"],
                unknown_findings=counts["unknown"],
                evidence_count=len(normalized.evidence_items),
                gap_count=len(gaps),
            ),
        )

    def _build_sections(
        self,
        case: StructuredCase,
        gaps: list[ReportGap],
        limitations: list[str],
    ) -> list[ReportSection]:
        sorted_timeline = sorted(
            case.timeline_events,
            key=lambda event: event.timestamp or datetime.max.replace(tzinfo=timezone.utc),
        )
        gap_section_ids = {gap.section_id for gap in gaps}

        sections = [
            ReportSection(
                id="executive_summary",
                title="Executive Summary",
                required=True,
                status=self._section_status(bool(case.incident_summary), "executive_summary", gap_section_ids),
                content={
                    "summary": case.incident_summary or "No incident narrative provided.",
                    "severity": case.severity,
                    "case_status": case.status,
                },
                source_fact_ids=["incident_summary"] if case.incident_summary else [],
            ),
            ReportSection(
                id="incident_overview",
                title="Incident Overview",
                required=True,
                status=self._section_status(bool(case.title or case.case_type), "incident_overview", gap_section_ids),
                content={
                    "title": case.title,
                    "case_type": case.case_type,
                    "status": case.status,
                    "severity": case.severity,
                    "analyst_notes": case.analyst_notes,
                    "created_at": case.created_at,
                    "updated_at": case.updated_at,
                },
                source_fact_ids=["title", "case_type", "status", "severity"],
            ),
            ReportSection(
                id="scope_and_affected_assets",
                title="Scope and Affected Assets",
                required=True,
                status=self._section_status(bool(case.affected_users or case.affected_assets), "scope_and_affected_assets", gap_section_ids),
                content={
                    "affected_users": case.affected_users,
                    "affected_assets": case.affected_assets,
                },
                source_fact_ids=["affected_users", "affected_assets"],
            ),
            ReportSection(
                id="attack_timeline",
                title="Attack Timeline",
                required=True,
                status=self._section_status(bool(sorted_timeline), "attack_timeline", gap_section_ids),
                content={
                    "events": [event.model_dump(mode="json") for event in sorted_timeline],
                },
                source_fact_ids=[event.event_id for event in sorted_timeline],
            ),
            ReportSection(
                id="mitre_attack_mapping",
                title="MITRE ATT&CK Mapping",
                required=True,
                status=self._section_status(bool(case.attack_mappings), "mitre_attack_mapping", gap_section_ids),
                content={"tactics": group_mappings_by_tactic(case.attack_mappings)},
                source_fact_ids=[mapping.mapping_id for mapping in case.attack_mappings],
            ),
            ReportSection(
                id="evidence_register",
                title="Evidence Register",
                required=True,
                status=self._section_status(bool(case.evidence_items), "evidence_register", gap_section_ids),
                content={
                    "evidence": [item.model_dump(mode="json") for item in case.evidence_items],
                },
                source_fact_ids=[item.evidence_id for item in case.evidence_items],
            ),
            ReportSection(
                id="containment_and_response_actions",
                title="Containment and Response Actions",
                required=True,
                status=self._section_status(bool(case.containment_actions), "containment_and_response_actions", gap_section_ids),
                content={
                    "actions": [action.model_dump(mode="json") for action in case.containment_actions],
                },
                source_fact_ids=[action.action_id for action in case.containment_actions],
            ),
            ReportSection(
                id="recommendations",
                title="Recommendations",
                required=True,
                status=self._section_status(bool(case.recommendations), "recommendations", gap_section_ids),
                content={
                    "recommendations": [item.model_dump(mode="json") for item in case.recommendations],
                },
                source_fact_ids=[item.action_id for item in case.recommendations],
            ),
        ]

        sections.append(
            ReportSection(
                id="evidence_gaps_and_limitations",
                title="Evidence Gaps and Limitations",
                required=True,
                status="partial" if gaps else "complete",
                content={
                    "gaps": [gap.model_dump(mode="json") for gap in gaps],
                    "limitations": limitations,
                },
                source_fact_ids=[gap.gap_id for gap in gaps],
            )
        )

        return sections

    def _build_limitations(self, case: StructuredCase, gaps: list[ReportGap]) -> list[str]:
        limitations = list(dict.fromkeys(case.limitations))
        if not case.evidence_items:
            limitations.append("No evidence items were provided for this case.")
        if gaps:
            limitations.append("This deterministic report is incomplete until the listed gaps are resolved or accepted by an analyst.")
        return list(dict.fromkeys(limitations))

    @staticmethod
    def _section_status(
        has_content: bool,
        section_id: str,
        gap_section_ids: set[str],
    ) -> ReportSectionStatus:
        if not has_content:
            return "missing"
        if section_id in gap_section_ids:
            return "partial"
        return "complete"

    @staticmethod
    def _report_status(
        gaps: list[ReportGap],
        candidate_findings: int,
        unknown_findings: int,
    ) -> str:
        if gaps:
            return "incomplete"
        if candidate_findings or unknown_findings:
            return "draft"
        return "ready_for_review"


def structured_case_from_record_data(
    *,
    case_id: str,
    title: str,
    status: str,
    severity: str,
    data: dict[str, Any],
    created_at: datetime | None,
    updated_at: datetime | None,
) -> StructuredCase:
    payload = dict(data or {})
    payload.setdefault("case_id", case_id)
    payload.setdefault("title", title)
    payload.setdefault("status", status)
    payload.setdefault("severity", severity)
    payload.setdefault("created_at", created_at)
    payload.setdefault("updated_at", updated_at)
    return StructuredCase(**payload)
