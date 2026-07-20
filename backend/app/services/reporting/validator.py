from __future__ import annotations

import json
from typing import Any

from .schemas import (
    EVIDENCE_ID_PATTERN,
    LEGAL_DISCLAIMER,
    CaseFactPack,
    CyberCaseReport,
    ReportEntity,
)


class ReportValidationMixin:
    def validate_report(
        self,
        report: CyberCaseReport,
        allowed_techniques: list[ReportEntity],
        legal: bool,
    ) -> None:
        known_evidence_ids = {
            evidence.evidence_id for evidence in report.case_fact_pack.evidence_registry
        }
        cited_ids = self._collect_report_evidence_ids(report)
        unknown_ids = cited_ids - known_evidence_ids
        if unknown_ids:
            raise ValueError(
                "Report cites unknown evidence IDs: " + ", ".join(sorted(unknown_ids))
            )

        allowed_technique_ids = {
            entity.attack_id
            for entity in allowed_techniques
            if self._is_attack_technique_id(entity.attack_id)
        }
        for assessment in report.mitre_attack_assessment:
            if assessment.technique_id not in allowed_technique_ids:
                raise ValueError(
                    f"MITRE technique {assessment.technique_id} was not present in retrieved MITRE data"
                )

        if not legal and report.legal_assessments:
            raise ValueError("Legal assessment must be absent when legal=false")
        if legal:
            legal_text = json.dumps(
                [item.model_dump() for item in report.legal_assessments],
                ensure_ascii=False,
            )
            if LEGAL_DISCLAIMER not in legal_text:
                raise ValueError("Legal disclaimer missing when legal=true")


    def validate_case_fact_pack(
        self,
        case_fact_pack: CaseFactPack,
        allowed_techniques: list[ReportEntity],
        legal: bool,
    ) -> None:
        allowed_ids = {entity.attack_id for entity in allowed_techniques}
        for assessment in case_fact_pack.mitre_assessments:
            if assessment.technique_id not in allowed_ids:
                raise ValueError(
                    f"MITRE technique {assessment.technique_id} is not in retrieved MITRE data"
                )
        if not legal and case_fact_pack.legal_assessments:
            raise ValueError("legal_assessments must be empty when legal=false")
        if legal and any(
            LEGAL_DISCLAIMER not in item.disclaimer
            for item in case_fact_pack.legal_assessments
            if item.enabled
        ):
            raise ValueError("Legal disclaimer missing from Case Fact Pack")

    def _collect_report_evidence_ids(self, report: CyberCaseReport) -> set[str]:
        ids: set[str] = set()
        typed_items: list[Any] = [
            *report.case_fact_pack.facts,
            *report.case_fact_pack.indicators,
            *report.case_fact_pack.timeline,
            *report.case_fact_pack.mitre_assessments,
            *report.case_fact_pack.legal_assessments,
            *report.evidence_and_indicators_table,
            *report.incident_timeline,
            *report.mitre_attack_assessment,
            *report.legal_assessments,
        ]
        for item in typed_items:
            ids.update(getattr(item, "evidence_ids", []))
        text_fields = [
            report.executive_case_summary,
            *report.evidence_still_required,
            *report.investigation_next_steps,
            *report.limitations_and_disclaimers,
        ]
        for text in text_fields:
            ids.update(EVIDENCE_ID_PATTERN.findall(text or ""))
        return ids
