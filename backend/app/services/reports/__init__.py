"""Incident Report Generation & PDF Export."""

from app.services.reports.report_generation import (
    AdmittedMitreRow,
    AnthropicReportAdapter,
    ReportInputSnapshot,
    ReportModelAdapter,
    ReportModelResponse,
    ReportProviderFailure,
    ReportRunResult,
    ReportSourceMessage,
    ReportValidationError,
    run_report_generation,
    source_snapshot_hash,
    validate_structured_report,
)
from app.services.reports.report_pdf import render_chat_report_pdf
from app.services.reports.report_prompt import REPORT_SYSTEM_PROMPT
from app.services.reports.report_provider_schema import (
    ProviderStructuredReport,
    provider_report_to_structured_report,
)
from app.services.reports.report_service import (
    ChatReportService,
    ReportGenerationConflict,
    ReportNotFound,
    ReportService,
)

ReportGenerationError = ReportProviderFailure
generate_report_payload = run_report_generation
build_report_pdf_bytes = render_chat_report_pdf

__all__ = [
    "AdmittedMitreRow",
    "AnthropicReportAdapter",
    "ReportInputSnapshot",
    "ReportModelAdapter",
    "ReportModelResponse",
    "ReportProviderFailure",
    "ReportRunResult",
    "ReportSourceMessage",
    "ReportValidationError",
    "ReportGenerationError",
    "generate_report_payload",
    "run_report_generation",
    "source_snapshot_hash",
    "validate_structured_report",
    "build_report_pdf_bytes",
    "render_chat_report_pdf",
    "REPORT_SYSTEM_PROMPT",
    "ProviderStructuredReport",
    "provider_report_to_structured_report",
    "ReportService",
    "ChatReportService",
    "ReportGenerationConflict",
    "ReportNotFound",
]
