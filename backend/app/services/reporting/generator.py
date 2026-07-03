from __future__ import annotations

from typing import Any

from .builder import ReportBuilderMixin
from .evidence import ReportEvidenceMixin
from .fact_pack import DeterministicFactPackMixin
from .renderer import ReportMarkdownRendererMixin
from .schemas import (
    COMPLETENESS_THRESHOLD,
    CaseFactPack,
    CyberCaseReport,
    EvidenceReference,
)
from .utils import ReportUtilityMixin
from .validator import ReportValidationMixin


class ReportGenerator(
    ReportValidationMixin,
    ReportMarkdownRendererMixin,
    ReportBuilderMixin,
    DeterministicFactPackMixin,
    ReportEvidenceMixin,
    ReportUtilityMixin,
):
    """Build evidence-traceable preliminary reports from RAG-provided context."""

    def __init__(self, use_local: bool = False) -> None:
        self.use_local = use_local

    def preview_case_fact_pack(
        self,
        query: str,
        legal: bool = False,
        evidence_registry: list[EvidenceReference] | None = None,
    ) -> CaseFactPack:
        registry, base_evidence_ids, _ = self.build_evidence_registry(
            query=query,
            provided_evidence=evidence_registry,
            mitre_entities=[],
        )
        return self._build_deterministic_case_fact_pack(
            query=query,
            evidence_registry=registry,
            base_evidence_ids=base_evidence_ids,
            mitre_evidence_ids={},
            allowed_techniques=[],
            legal=legal,
        )

    def generate(
        self,
        query: str,
        context: str,
        rag_result: Any | None = None,
        report_type: str = "overview",
        legal: bool = False,
        evidence_registry: list[EvidenceReference] | None = None,
        force_generate: bool = False,
    ) -> CyberCaseReport:
        packet = self.build_evidence_packet(
            query=query,
            context=context,
            rag_result=rag_result,
            report_type=report_type,
        )
        allowed_techniques = packet.ttp_candidates
        registry, base_evidence_ids, mitre_evidence_ids = self.build_evidence_registry(
            query=query,
            provided_evidence=evidence_registry,
            mitre_entities=allowed_techniques,
        )

        case_fact_pack = self._build_deterministic_case_fact_pack(
            query=query,
            evidence_registry=registry,
            base_evidence_ids=base_evidence_ids,
            mitre_evidence_ids=mitre_evidence_ids,
            allowed_techniques=allowed_techniques,
            legal=legal,
        )
        self._append_unique(
            case_fact_pack.limitations,
            "Report generated from a predefined evidence/MITRE template using RAG-provided context.",
        )

        if force_generate and case_fact_pack.completeness_percentage < COMPLETENESS_THRESHOLD:
            self._append_unique(
                case_fact_pack.limitations,
                "Generated at user request despite incomplete case information.",
            )

        report = self.build_evidence_locked_report(
            case_fact_pack=case_fact_pack,
            report_type=self._normalize_report_type(report_type),
            legal=legal,
        )
        self.validate_report(report, allowed_techniques=allowed_techniques, legal=legal)
        return report
