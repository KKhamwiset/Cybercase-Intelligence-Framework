from __future__ import annotations

from typing import Any

from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    GenerateReportRequest,
    ReportCompletedResponse,
    ReportFollowUpResponse,
    ReportResumeRequest,
    ReviewStatusUpdate,
)
from app.services.rag_client import RagServiceClient

ReportWorkflowResult = ReportCompletedResponse | ReportFollowUpResponse


def canonicalize_report_workflow_response(payload: dict[str, Any]) -> ReportWorkflowResult:
    status = payload.get("status")
    if status == "completed":
        report = _optional_report(payload.get("report"))
        if report is None:
            raise ValueError("Completed report response requires a report payload")
        return ReportCompletedResponse(
            status="completed",
            report_id=payload.get("report_id") or report.report_id,
            report=report,
            answer=payload.get("answer", ""),
        )

    if status == "followup":
        case_fact_pack = _optional_case_fact_pack(payload.get("case_fact_pack"))
        completeness = _optional_completeness(payload.get("completeness"))
        if completeness is None and case_fact_pack is not None:
            completeness = case_fact_pack.completeness
        missing_information = payload.get("missing_information")
        if missing_information is None and case_fact_pack is not None:
            missing_information = case_fact_pack.missing_information
        missing_information = list(missing_information or [])
        if completeness is None:
            completeness = CaseInformationCompleteness(
                percentage=0,
                status="Incomplete - follow-up required",
                missing_fields=missing_information,
                fields=[],
            )

        return ReportFollowUpResponse(
            status="followup",
            followup_question=payload.get("followup_question", ""),
            session_id=payload.get("session_id", ""),
            retrieval_context_id=payload.get("retrieval_context_id", ""),
            completeness=completeness,
            missing_information=missing_information,
        )

    raise ValueError(f"Unsupported report workflow status: {status!r}")


class ReportWorkflowService:
    def __init__(self, client: RagServiceClient | None = None) -> None:
        self.client = client or RagServiceClient()

    async def generate_report(
        self, request: GenerateReportRequest
    ) -> ReportWorkflowResult:
        payload = await self.client.post_json(
            "/generate-report",
            request.model_dump(mode="json"),
        )
        return canonicalize_report_workflow_response(payload)

    async def resume_report(self, request: ReportResumeRequest) -> ReportWorkflowResult:
        payload = await self.client.post_json(
            "/resume-report",
            request.model_dump(mode="json"),
        )
        return canonicalize_report_workflow_response(payload)

    async def get_report(self, report_id: str) -> ReportWorkflowResult:
        payload = await self.client.get_json(f"/reports/{report_id}")
        return canonicalize_report_workflow_response(payload)

    async def update_review_status(
        self,
        report_id: str,
        request: ReviewStatusUpdate,
    ) -> ReportWorkflowResult:
        payload = await self.client.patch_json(
            f"/reports/{report_id}/review-status",
            request.model_dump(mode="json"),
        )
        return canonicalize_report_workflow_response(payload)


def _optional_report(value: Any) -> CyberCaseReport | None:
    if value is None:
        return None
    if isinstance(value, CyberCaseReport):
        return value
    return CyberCaseReport.model_validate(value)


def _optional_case_fact_pack(value: Any) -> CaseFactPack | None:
    if value is None:
        return None
    if isinstance(value, CaseFactPack):
        return value
    return CaseFactPack.model_validate(value)


def _optional_completeness(value: Any) -> CaseInformationCompleteness | None:
    if value is None:
        return None
    if isinstance(value, CaseInformationCompleteness):
        return value
    return CaseInformationCompleteness.model_validate(value)


__all__ = [
    "ReportWorkflowResult",
    "ReportWorkflowService",
    "canonicalize_report_workflow_response",
]
