from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException

from app.schemas.report import (
    CaseFactPack,
    CaseInformationCompleteness,
    CyberCaseReport,
    GenerateReportRequest,
    ReportCompletedResponse,
    ReportErrorResponse,
    ReportFollowUpResponse,
    ReportResumeRequest,
    ReviewStatusUpdate,
    EvidenceReference,
)
from app.services.rag_client import RagServiceClient
from app.services.reporting.generator import ReportGenerator
from app.services.reporting.thanoy_client import get_legal_advice

ReportWorkflowResult = ReportCompletedResponse | ReportFollowUpResponse

REPORT_CONTEXT_WAIT_MESSAGE = (
    "Report generation is waiting for RAG context. Run the case through the RAG "
    "query or resume API first, then call report generation with the returned "
    "retrieval_context_id."
)

class ReportWorkflowService:
    def __init__(
        self,
        report_gen: ReportGenerator | None = None,
        report_store: dict | None = None,
        report_sessions: dict | None = None,
        client: RagServiceClient | None = None,
    ) -> None:
        self.report_gen = report_gen
        self.report_store = report_store if report_store is not None else {}
        self.report_sessions = report_sessions if report_sessions is not None else {}
        self.client = client or RagServiceClient()

    async def generate_report(self, request: GenerateReportRequest) -> ReportWorkflowResult:
        if not self.report_gen:
            raise HTTPException(status_code=503, detail="Report Generator not available")

        # 1. Fetch retrieval context snapshot
        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{request.retrieval_context_id}")
        except Exception:
            return self._report_context_wait_response(request)

        # 2. Preview fact pack to check if follow-up is needed
        preview_pack = self.report_gen.preview_case_fact_pack(
            request.query,
            legal=request.legal,
            evidence_registry=request.evidence_registry,
        )
        if self._needs_report_followup(preview_pack) and not request.force_generate:
            return self._start_report_followup(request, preview_pack)

        return await self._complete_report_generation(request, snapshot)

    async def resume_report(self, request: ReportResumeRequest) -> ReportWorkflowResult:
        pending = self.report_sessions.pop(request.session_id, None)
        if not pending:
            raise HTTPException(status_code=404, detail="Report session not found")

        original = GenerateReportRequest.model_validate(pending["request"])
        combined_query = original.query
        if request.answer.strip():
            combined_query = (
                f"{original.query}\n\n"
                "Follow-up answer supplied for preliminary report:\n"
                f"{request.answer.strip()}"
            )
        update_fields = {"query": combined_query, "force_generate": True}
        resumed_request = original.model_copy(update=update_fields)

        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{resumed_request.retrieval_context_id}")
        except Exception:
            return self._report_context_wait_response(resumed_request)

        return await self._complete_report_generation(resumed_request, snapshot)

    async def get_report(self, report_id: str) -> ReportWorkflowResult:
        report = self._get_stored_report(report_id)
        answer = self.report_gen.render_report_markdown(report) if self.report_gen else report.case_summary
        return ReportCompletedResponse(
            status="completed",
            answer=answer,
            report_id=report.report_id,
            report=report,
            case_fact_pack=report.case_fact_pack,
            completeness=report.case_information_completeness,
            missing_information=report.case_fact_pack.missing_information,
        )

    async def update_review_status(
        self,
        report_id: str,
        request: ReviewStatusUpdate,
    ) -> ReportWorkflowResult:
        report = self._get_stored_report(report_id)
        report.review_status = request.review_status
        report.case_fact_pack.review_status = request.review_status
        self.report_store[report_id] = report

        answer = self.report_gen.render_report_markdown(report) if self.report_gen else report.case_summary
        return ReportCompletedResponse(
            status="completed",
            answer=answer,
            report_id=report.report_id,
            report=report,
            case_fact_pack=report.case_fact_pack,
            completeness=report.case_information_completeness,
            missing_information=report.case_fact_pack.missing_information,
        )

    async def _complete_report_generation(
        self, request: GenerateReportRequest, snapshot: dict[str, Any]
    ) -> ReportCompletedResponse:
        if not self.report_gen:
            raise HTTPException(status_code=503, detail="Report Generator not available")

        try:
            print(f"[REPORT] Formatting report locally from RAG context: {request.retrieval_context_id}")
            rag_result = snapshot.get("rag_result", {})
            context = snapshot.get("context", "")

            report = self.report_gen.generate(
                request.query,
                context,
                rag_result=rag_result,
                report_type=request.report_type,
                legal=request.legal,
                evidence_registry=request.evidence_registry,
                force_generate=request.force_generate,
            )
            if request.legal:
                await self._apply_thanoy_legal_advice(report)

            self.report_store[report.report_id] = report
            return ReportCompletedResponse(
                status="completed",
                answer=self.report_gen.render_report_markdown(report),
                report_id=report.report_id,
                report=report,
                case_fact_pack=report.case_fact_pack,
                completeness=report.case_information_completeness,
                missing_information=report.case_fact_pack.missing_information,
                retrieval_context_id=request.retrieval_context_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except Exception as e:
            print(f"[REPORT] Error: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

    def _needs_report_followup(self, case_fact_pack: CaseFactPack) -> bool:
        return case_fact_pack.completeness.status == "Incomplete - follow-up required"

    def _start_report_followup(
        self, request: GenerateReportRequest, case_fact_pack: CaseFactPack
    ) -> ReportFollowUpResponse:
        followup_question = self._build_report_followup_question(case_fact_pack)
        session_id = str(uuid.uuid4())

        self.report_sessions[session_id] = {
            "request": request.model_dump(mode="json"),
        }
        return ReportFollowUpResponse(
            status="followup",
            followup_question=followup_question,
            session_id=session_id,
            case_fact_pack=case_fact_pack,
            completeness=case_fact_pack.completeness,
            missing_information=case_fact_pack.missing_information,
            retrieval_context_id=request.retrieval_context_id,
        )

    def _report_context_wait_response(self, request: GenerateReportRequest) -> ReportErrorResponse:
        return ReportErrorResponse(
            status="context_expired",
            error_code="retrieval_context_expired",
            message="Report generation is waiting for RAG context. Run the case through the RAG query or resume API first, then call report generation with the returned retrieval_context_id."
        )

    def _build_report_followup_question(self, case_fact_pack: CaseFactPack) -> str:
        if not case_fact_pack.missing_information:
            return "Could you provide any additional evidence or timeline details before report generation?"
        first_missing = case_fact_pack.missing_information[0]
        return (
            "The preliminary report is incomplete. Please provide the "
            f"{first_missing}, if known. You can answer 'unknown' if unavailable."
        )

    def _get_stored_report(self, report_id: str) -> CyberCaseReport:
        report = self.report_store.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    async def _apply_thanoy_legal_advice(self, report: CyberCaseReport) -> None:
        advice = await get_legal_advice(report.executive_case_summary or report.case_summary)
        if not advice:
            return

        registry = report.case_fact_pack.evidence_registry
        legal_evidence_id = self._next_report_evidence_id(registry)
        registry.append(
            EvidenceReference(
                evidence_id=legal_evidence_id,
                source_type="legal_source",
                source_name="Thanoy legal AI response",
                excerpt=advice[:1200],
            )
        )

        existing = (
            report.legal_assessments[0]
            if report.legal_assessments
            else report.case_fact_pack.legal_assessments[0]
            if report.case_fact_pack.legal_assessments
            else None
        )
        if not existing:
            return

        case_evidence_id = self._primary_report_evidence_id(report)
        evidence_ids = [item for item in (case_evidence_id, legal_evidence_id) if item]
        assessment = existing.model_copy(
            update={
                "provision_reference": "Thanoy legal AI preliminary assessment",
                "preliminary_relevance": advice,
                "status": "inferred",
                "evidence_ids": evidence_ids,
            }
        )
        report.legal_assessments = [assessment]
        report.case_fact_pack.legal_assessments = [assessment]

    def _primary_report_evidence_id(self, report: CyberCaseReport) -> str:
        for evidence in report.case_fact_pack.evidence_registry:
            if evidence.source_type in {"user_input", "uploaded_file", "log"}:
                return evidence.evidence_id
        if report.case_fact_pack.evidence_registry:
            return report.case_fact_pack.evidence_registry[0].evidence_id
        return ""

    def _next_report_evidence_id(self, registry: list[EvidenceReference]) -> str:
        used = {item.evidence_id for item in registry}
        index = 1
        while f"E-{index:03d}" in used:
            index += 1
        return f"E-{index:03d}"

__all__ = [
    "ReportWorkflowResult",
    "ReportWorkflowService",
]
