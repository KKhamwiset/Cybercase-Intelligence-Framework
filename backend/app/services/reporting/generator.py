from __future__ import annotations

import os
from typing import Any

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover - deterministic fallback works without LLM libs.
    ChatAnthropic = None  # type: ignore[assignment]

try:
    from RAG.GraphRAG.config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL
except ImportError:  # pragma: no cover - backend-only import path.
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
from .builder import ReportBuilderMixin
from .evidence import ReportEvidenceMixin
from .fact_pack import DeterministicFactPackMixin
from .llm_extractor import LLMFactPackMixin
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
    LLMFactPackMixin,
    ReportValidationMixin,
    ReportMarkdownRendererMixin,
    ReportBuilderMixin,
    DeterministicFactPackMixin,
    ReportEvidenceMixin,
    ReportUtilityMixin,
):
    """Build evidence-traceable preliminary legal relevance reports."""
    def __init__(self) -> None:
        self.llm = None
        self.fact_pack_llm = None

        if not ANTHROPIC_API_KEY or ChatAnthropic is None:
            print(
                "[REPORT] Warning: ANTHROPIC_API_KEY not set. "
                "Case Fact Pack extraction will use deterministic fallback."
            )
            return

        self.llm = ChatAnthropic(
            model_name=LLM_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0,
            max_tokens_to_sample=LLM_MAX_TOKENS,
        )
        self.fact_pack_llm = self.llm.with_structured_output(CaseFactPack)

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

        deterministic_pack = self._build_deterministic_case_fact_pack(
            query=query,
            evidence_registry=registry,
            base_evidence_ids=base_evidence_ids,
            mitre_evidence_ids=mitre_evidence_ids,
            allowed_techniques=allowed_techniques,
            legal=legal,
        )
        case_fact_pack = self._extract_case_fact_pack_with_llm(
            query=query,
            deterministic_pack=deterministic_pack,
            allowed_techniques=allowed_techniques,
            legal=legal,
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
