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
        primary_evidence = self._primary_case_evidence_id(case_fact_pack)
        title = (
            INCOMPLETE_TITLE
            if completeness.percentage < COMPLETENESS_THRESHOLD
            else "Evidence-Traceable Preliminary Legal Relevance Report"
        )

        fact_sentences = [fact.statement for fact in case_fact_pack.facts[:4]]
        fact_summary = " ".join(fact_sentences) if fact_sentences else "No supported case facts were extracted."
        executive_summary = (
            f"Preliminary assessment based on reported and confirmed evidence metadata "
            f"{self._format_evidence_citations([primary_evidence])}: {fact_summary} "
            "This report organizes evidence and gaps for investigator/legal review; "
            "it does not determine guilt, admissibility, or final legal conclusions."
        )

        next_steps = self._build_next_steps(case_fact_pack)
        required = self._build_evidence_required(case_fact_pack)
        limitations = list(case_fact_pack.limitations)
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
            case_summary=executive_summary,
            detected_indicators=[
                f"{indicator.indicator_type.upper()}: {indicator.value} "
                f"{self._format_evidence_citations(indicator.evidence_ids)}"
                for indicator in case_fact_pack.indicators
            ],
            mitre_mapping=[
                f"{assessment.technique_id} {assessment.technique_name} "
                f"{self._format_evidence_citations(assessment.evidence_ids)}"
                for assessment in case_fact_pack.mitre_assessments
            ],
            mapping_justification="; ".join(
                assessment.justification
                for assessment in case_fact_pack.mitre_assessments
            )
            or "No MITRE ATT&CK technique is sufficiently supported by retrieved MITRE data.",
            evidence_to_investigate=required,
            preliminary_recommendations=next_steps,
            system_limitations=" ".join(limitations),
        )
        return report

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
        return required or ["No additional required evidence was identified for a preliminary report."]

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
