from __future__ import annotations

import sys
from pathlib import Path

from ..config import ANTHROPIC_API_KEY, LLM_MAX_TOKENS, LLM_MODEL

def _add_backend_root_to_path() -> None:
    for parent in Path(__file__).resolve().parents:
        reporting_path = parent / "backend" / "app" / "services" / "reporting"
        if reporting_path.exists():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            return

_add_backend_root_to_path()

from backend.app.services.reporting import (  # noqa: E402
    COMPLETENESS_THRESHOLD,
    EVIDENCE_ID_PATTERN,
    INCOMPLETE_LABEL,
    INCOMPLETE_TITLE,
    LEGAL_DISCLAIMER,
    REPORT_TYPES,
    SUFFICIENT_LABEL,
    TECHNIQUE_ID_PATTERN,
    CaseFact,
    CaseFactPack,
    CaseInformationCompleteness,
    CompletenessField,
    CyberCaseReport,
    EvidenceReference,
    Indicator,
    LegalRelevanceAssessment,
    MitreAssessment,
    ReportEntity,
    ReportEvidencePacket,
    ReportGenerator,
    ReportRelationship,
    ReportWorkflowResponse,
    TimelineEvent,
)
from backend.app.services.reporting.schemas import (  # noqa: E402
    Confidence,
    EvidenceStatus,
    IndicatorType,
    ReportType,
    ReviewStatus,
    SourceType,
    WorkflowStatus,
)

__all__ = [
    "ANTHROPIC_API_KEY",
    "LLM_MAX_TOKENS",
    "LLM_MODEL",
    "COMPLETENESS_THRESHOLD",
    "EVIDENCE_ID_PATTERN",
    "INCOMPLETE_LABEL",
    "INCOMPLETE_TITLE",
    "LEGAL_DISCLAIMER",
    "REPORT_TYPES",
    "SUFFICIENT_LABEL",
    "TECHNIQUE_ID_PATTERN",
    "CaseFact",
    "CaseFactPack",
    "CaseInformationCompleteness",
    "CompletenessField",
    "Confidence",
    "CyberCaseReport",
    "EvidenceReference",
    "EvidenceStatus",
    "Indicator",
    "IndicatorType",
    "LegalRelevanceAssessment",
    "MitreAssessment",
    "ReportEntity",
    "ReportEvidencePacket",
    "ReportGenerator",
    "ReportRelationship",
    "ReportType",
    "ReportWorkflowResponse",
    "ReviewStatus",
    "SourceType",
    "TimelineEvent",
    "WorkflowStatus",
]
