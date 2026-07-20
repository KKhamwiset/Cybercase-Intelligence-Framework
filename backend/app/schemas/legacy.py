from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    ReportCompletedResponse,
    ReportErrorResponse,
    ReportFollowUpResponse,
    WorkflowStatus,
)


class LegacyReportWorkflowResponse(BaseModel):
    status: WorkflowStatus
    answer: str = ""
    followup_question: str = ""
    session_id: str = ""
    error_code: str = ""
    message: str = ""
    retrieval_context_id: str = ""
    report_id: str | None = None
    report: CyberCaseReport | None = None
    case_fact_pack: CaseFactPack | None = None
    completeness: CaseInformationCompleteness | None = None
    missing_information: list[str] = Field(default_factory=list)


def legacy_report_response_from_payload(
    payload: dict[str, Any] | ReportCompletedResponse | ReportFollowUpResponse,
) -> LegacyReportWorkflowResponse:
    if isinstance(payload, LegacyReportWorkflowResponse):
        return payload
    if isinstance(payload, (ReportCompletedResponse, ReportFollowUpResponse, ReportErrorResponse)):
        data = payload.model_dump(mode="json")
    else:
        data = dict(payload)

    report = data.get("report")
    if report is not None and not isinstance(report, CyberCaseReport):
        report = CyberCaseReport.model_validate(report)

    case_fact_pack = data.get("case_fact_pack")
    if case_fact_pack is None and report is not None:
        case_fact_pack = report.case_fact_pack
    elif case_fact_pack is not None and not isinstance(case_fact_pack, CaseFactPack):
        case_fact_pack = CaseFactPack.model_validate(case_fact_pack)

    completeness = data.get("completeness")
    if completeness is None and report is not None:
        completeness = report.case_information_completeness
    elif completeness is not None and not isinstance(
        completeness, CaseInformationCompleteness
    ):
        completeness = CaseInformationCompleteness.model_validate(completeness)

    missing_information = data.get("missing_information")
    if missing_information is None and case_fact_pack is not None:
        missing_information = case_fact_pack.missing_information

    report_id = data.get("report_id")
    if report_id is None and report is not None:
        report_id = report.report_id

    return LegacyReportWorkflowResponse(
        status=data["status"],
        answer=data.get("answer", ""),
        followup_question=data.get("followup_question", ""),
        session_id=data.get("session_id", ""),
        error_code=data.get("error_code", ""),
        message=data.get("message", ""),
        retrieval_context_id=data.get("retrieval_context_id") or "",
        report_id=report_id,
        report=report,
        case_fact_pack=case_fact_pack,
        completeness=completeness,
        missing_information=list(missing_information or []),
    )


__all__ = [
    "LegacyReportWorkflowResponse",
    "legacy_report_response_from_payload",
]
