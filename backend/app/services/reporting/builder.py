from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .schemas import (
    COMPLETENESS_THRESHOLD,
    INCOMPLETE_TITLE,
    LEGAL_DISCLAIMER,
    CaseFactPack,
    CyberCaseReport,
    ReportType,
    ReviewStatus,
)


NON_LEGAL_REPORT_TITLE = "Evidence-Grounded Preliminary Cyber Incident Report"
AI_ASSISTED_LIMITATION = (
    "This report is AI-assisted preliminary investigation support and requires analyst review."
)


class ReportBuilderMixin:
    def build_evidence_locked_report(
        self,
        case_fact_pack: CaseFactPack,
        report_type: ReportType,
        legal: bool,
    ) -> CyberCaseReport:
        review_status: ReviewStatus = "ai_generated"
        case_fact_pack.review_status = review_status
        completeness = case_fact_pack.completeness
        title = self._build_report_title(completeness.percentage, legal)
        executive_summary = self._build_executive_case_summary(case_fact_pack)

        next_steps = self._build_next_steps(case_fact_pack)
        required = self._build_evidence_required(case_fact_pack)
        limitations = list(case_fact_pack.limitations)
        self._append_unique(limitations, AI_ASSISTED_LIMITATION)
        if not legal:
            self._append_unique(
                limitations,
                "Preliminary legal relevance was not requested, so no legal assessment is included.",
            )
        else:
            self._append_unique(limitations, LEGAL_DISCLAIMER)

        report = CyberCaseReport(
            report_id=str(uuid.uuid4()),
            title=title,
            report_type=report_type,
            executive_case_summary=executive_summary,
            case_information_completeness=completeness,
            evidence_and_indicators_table=case_fact_pack.indicators,
            incident_timeline=case_fact_pack.timeline,
            mitre_attack_assessment=case_fact_pack.mitre_assessments,
            evidence_still_required=required,
            investigation_next_steps=next_steps,
            legal_assessments=case_fact_pack.legal_assessments if legal else [],
            limitations_and_disclaimers=limitations,
            review_status=review_status,
            case_fact_pack=case_fact_pack,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        return report

    @staticmethod
    def _build_report_title(completeness_percentage: int, legal: bool) -> str:
        if not legal:
            return NON_LEGAL_REPORT_TITLE
        if completeness_percentage < COMPLETENESS_THRESHOLD:
            return INCOMPLETE_TITLE
        return "Evidence-Traceable Preliminary Legal Relevance Report"

    def _build_executive_case_summary(self, case_fact_pack: CaseFactPack) -> str:
        indicators = case_fact_pack.indicators
        timeline = case_fact_pack.timeline
        mitre_assessments = case_fact_pack.mitre_assessments
        completeness = case_fact_pack.completeness

        parts = [
            (
                "This preliminary report summarizes submitted case information and "
                "evidence metadata for analyst review."
            ),
            f"Case readiness is {completeness.percentage}% ({completeness.status}).",
        ]

        if indicators:
            indicator_preview = ", ".join(
                f"{item.indicator_type.upper()} {item.value}" for item in indicators[:3]
            )
            parts.append(
                f"{len(indicators)} indicator(s) were extracted, including {indicator_preview}."
            )
        else:
            parts.append("No explicit indicators were extracted from the submitted case information.")

        if timeline:
            timestamp_preview = [
                item.timestamp for item in timeline[:3] if item.timestamp
            ]
            if timestamp_preview:
                parts.append(
                    f"Timeline evidence includes {len(timeline)} reported event(s) around "
                    f"{', '.join(timestamp_preview)}."
                )
            else:
                parts.append(
                    f"Timeline evidence includes {len(timeline)} reported event(s) without exact timestamps."
                )
        else:
            parts.append("No reliable incident timeline was extracted.")

        if mitre_assessments:
            technique_preview = ", ".join(
                f"{item.technique_id} {item.technique_name}"
                for item in mitre_assessments[:3]
            )
            parts.append(f"MITRE ATT&CK candidate mapping includes {technique_preview}.")
        else:
            parts.append("No MITRE ATT&CK candidate was supported by retrieved MITRE data.")

        return " ".join(parts)

    def _build_evidence_required(self, case_fact_pack: CaseFactPack) -> list[str]:
        required = [
            f"Provide {item}." for item in case_fact_pack.missing_information
        ]
        if not case_fact_pack.indicators:
            required.append("Collect source indicators such as IPs, domains, URLs, hashes, email headers, or log excerpts.")
        if not case_fact_pack.timeline:
            required.append("Collect timestamps or a reliable sequence of observed events.")
        if not case_fact_pack.mitre_assessments:
            required.append("Collect technical behavior evidence that can support or reject MITRE ATT&CK mappings.")
        return required or [
            "No additional required evidence was identified for this preliminary report. Analyst review is still recommended."
        ]

    def _build_next_steps(self, case_fact_pack: CaseFactPack) -> list[str]:
        steps = [
            "Review each evidence ID against the original source before distributing the report.",
            "Confirm whether reported facts are confirmed, inferred, or still unknown.",
        ]
        if case_fact_pack.indicators:
            steps.append("Validate reported indicators against logs, endpoint data, network telemetry, or source documents.")
        if case_fact_pack.mitre_assessments:
            steps.append("Have an analyst confirm each MITRE ATT&CK mapping against the observed behavior.")
        if case_fact_pack.legal_assessments:
            steps.append("Have a qualified legal reviewer assess any preliminary legal relevance.")
        return steps
