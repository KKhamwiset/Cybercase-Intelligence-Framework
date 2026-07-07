from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import CaseRecord
from app.models.report import ReportRecord, ReportSessionRecord
from app.schemas.report import (
    CaseFactPack,
    CyberCaseReport,
    GenerateReportRequest,
    ReportCompletedResponse,
    ReportErrorResponse,
    ReportFollowUpResponse,
    ReportResumeRequest,
    ReviewStatusUpdate,
    EvidenceReference,
    ReportRegistryItem,
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


def build_evidence_registry_from_case(case: CaseRecord) -> list[EvidenceReference]:
    registry = []
    incident_summary = case.data.get("incident_summary", "")
    if incident_summary.strip():
        registry.append(
            EvidenceReference(
                evidence_id="E-001",
                source_type="user_input",
                source_name="Submitted case text",
                excerpt=incident_summary.strip()[:1200],
            )
        )
    
    next_id = 2
    for item in case.data.get("evidence_items", []):
        ev_id = item.get("evidence_id")
        if not ev_id:
            ev_id = f"E-{next_id:03d}"
            next_id += 1
        
        # Avoid duplicate E-001 if it was already used
        if ev_id == "E-001" and incident_summary.strip():
            ev_id = f"E-{next_id:03d}"
            next_id += 1
            
        registry.append(
            EvidenceReference(
                evidence_id=ev_id,
                source_type=item.get("source_type", "user_input"),
                source_name=item.get("title", "Evidence item"),
                excerpt=item.get("description", "")[:1200],
            )
        )
    return registry


class ReportWorkflowService:
    def __init__(
        self,
        report_gen: ReportGenerator | None = None,
        report_store: dict | None = None,  # Kept for compatibility
        report_sessions: dict | None = None,  # Kept for compatibility
        client: RagServiceClient | None = None,
        db: AsyncSession | None = None,
    ) -> None:
        self.report_gen = report_gen
        self.client = client or RagServiceClient()
        self.db = db

    async def generate_report(
        self, case_id: str, request: GenerateReportRequest
    ) -> ReportWorkflowResult:
        if not self.report_gen:
            raise HTTPException(status_code=503, detail="Report Generator not available")

        # 1. Load case from DB
        stmt = select(CaseRecord).where(CaseRecord.case_id == case_id)
        result = await self.db.execute(stmt)
        case = result.scalars().first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # 2. Build canonical report input from case data
        query = case.data.get("incident_summary", "")
        if not query.strip():
            query = f"Incident investigation for case {case_id}"

        evidence_registry = build_evidence_registry_from_case(case)

        # 3. Call RAG service internally to perform /query and obtain retrieval_context_id
        try:
            rag_payload = {"query": query, "use_agent": False}
            rag_res = await self.client.post_json("/query", rag_payload)
            retrieval_context_id = rag_res.get("retrieval_context_id", "")
        except Exception as exc:
            print(f"[RAG] Error calling query internally: {exc}")
            retrieval_context_id = ""

        # Override request parameters internally
        request = request.model_copy(
            update={
                "query": query,
                "evidence_registry": evidence_registry,
                "retrieval_context_id": retrieval_context_id,
            }
        )

        # 4. Fetch retrieval context snapshot
        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{retrieval_context_id}")
        except Exception:
            return self._report_context_wait_response(request)

        # 5. Preview fact pack to check if follow-up is needed
        preview_pack = self.report_gen.preview_case_fact_pack(
            request.query,
            legal=request.legal,
            evidence_registry=request.evidence_registry,
        )
        if self._needs_report_followup(preview_pack) and not request.force_generate:
            return await self._start_report_followup_db(case_id, request, preview_pack)

        return await self._complete_report_generation_db(case_id, request, snapshot)

    async def resume_report(
        self, case_id: str, request: ReportResumeRequest
    ) -> ReportWorkflowResult:
        # 1. Load active session from DB and verify ownership
        stmt = select(ReportSessionRecord).where(ReportSessionRecord.session_id == request.session_id)
        res = await self.db.execute(stmt)
        session_record = res.scalars().first()
        if not session_record:
            raise HTTPException(status_code=404, detail="Report session not found")

        if session_record.case_id != case_id:
            raise HTTPException(status_code=403, detail="Report session does not belong to this case")

        # Load original request
        original = GenerateReportRequest.model_validate(session_record.request_payload_json)

        # 2. Merge answer into the query/incident_summary
        combined_query = original.query
        if request.answer.strip():
            combined_query = (
                f"{original.query}\n\n"
                "Follow-up answer supplied for preliminary report:\n"
                f"{request.answer.strip()}"
            )
        update_fields = {"query": combined_query, "force_generate": True}
        resumed_request = original.model_copy(update=update_fields)

        # 3. Call RAG service internally to perform /query and obtain a new retrieval_context_id
        try:
            rag_payload = {"query": combined_query, "use_agent": False}
            rag_res = await self.client.post_json("/query", rag_payload)
            new_retrieval_context_id = rag_res.get("retrieval_context_id", "")
            resumed_request = resumed_request.model_copy(
                update={"retrieval_context_id": new_retrieval_context_id}
            )
        except Exception as exc:
            print(f"[RAG] Error calling query internally during resume: {exc}")
            new_retrieval_context_id = resumed_request.retrieval_context_id

        # 4. Fetch retrieval context snapshot
        try:
            snapshot = await self.client.get_json(f"/retrieval-contexts/{new_retrieval_context_id}")
        except Exception:
            return self._report_context_wait_response(resumed_request)

        # 5. Complete generation and delete session
        return await self._complete_report_generation_db(case_id, resumed_request, snapshot)

    async def get_report(self, report_id: str) -> ReportWorkflowResult:
        stmt = select(ReportRecord).where(ReportRecord.report_id == report_id)
        result = await self.db.execute(stmt)
        report_record = result.scalars().first()
        if not report_record:
            raise HTTPException(status_code=404, detail="Report not found")

        report = CyberCaseReport.model_validate(report_record.report_payload_json)
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

    async def get_latest_case_report(self, case_id: str) -> ReportWorkflowResult:
        stmt = (
            select(ReportRecord)
            .where(ReportRecord.case_id == case_id)
            .order_by(ReportRecord.created_at.desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        report_record = result.scalars().first()
        if not report_record:
            raise HTTPException(status_code=404, detail="No report found for this case")

        report = CyberCaseReport.model_validate(report_record.report_payload_json)
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

    async def list_reports(self) -> list[ReportRegistryItem]:
        stmt = (
            select(ReportRecord, CaseRecord)
            .join(CaseRecord, ReportRecord.case_id == CaseRecord.case_id)
            .order_by(ReportRecord.created_at.desc())
        )
        res = await self.db.execute(stmt)
        items = res.all()

        summaries = []
        for report_record, case_record in items:
            report = CyberCaseReport.model_validate(report_record.report_payload_json)
            exec_summary = report.executive_case_summary or report.case_summary or ""
            short_summary = exec_summary[:200] + "..." if len(exec_summary) > 200 else exec_summary

            summaries.append(
                ReportRegistryItem(
                    report_id=report_record.report_id,
                    case_id=report_record.case_id,
                    case_title=case_record.title,
                    case_status=case_record.status,
                    severity=case_record.severity,
                    report_type=report_record.report_type,
                    workflow_status=report_record.workflow_status,
                    review_status=report_record.review_status,
                    created_at=report_record.created_at.isoformat() if report_record.created_at else __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    updated_at=report_record.updated_at.isoformat() if report_record.updated_at else __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                    executive_summary_preview=short_summary,
                )
            )
        return summaries

    async def update_review_status(
        self,
        report_id: str,
        request: ReviewStatusUpdate,
    ) -> ReportWorkflowResult:
        stmt = select(ReportRecord).where(ReportRecord.report_id == report_id)
        result = await self.db.execute(stmt)
        report_record = result.scalars().first()
        if not report_record:
            raise HTTPException(status_code=404, detail="Report not found")

        report = CyberCaseReport.model_validate(report_record.report_payload_json)
        report.review_status = request.review_status
        report.case_fact_pack.review_status = request.review_status

        report_record.review_status = request.review_status
        report_record.report_payload_json = report.model_dump(mode="json")
        report_record.case_fact_pack_json = report.case_fact_pack.model_dump(mode="json")

        await self.db.commit()

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

    async def _start_report_followup_db(
        self, case_id: str, request: GenerateReportRequest, case_fact_pack: CaseFactPack
    ) -> ReportFollowUpResponse:
        followup_question = self._build_report_followup_question(case_fact_pack)
        session_id = str(uuid.uuid4())

        # Persist session in DB
        session_record = ReportSessionRecord(
            session_id=session_id,
            case_id=case_id,
            request_payload_json=request.model_dump(mode="json"),
        )
        self.db.add(session_record)
        await self.db.commit()

        return ReportFollowUpResponse(
            status="followup",
            followup_question=followup_question,
            session_id=session_id,
            completeness=case_fact_pack.completeness,
            missing_information=case_fact_pack.missing_information,
            retrieval_context_id=request.retrieval_context_id,
        )

    async def _complete_report_generation_db(
        self, case_id: str, request: GenerateReportRequest, snapshot: dict[str, Any]
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

            # Persist report in DB
            report_record = ReportRecord(
                report_id=report.report_id,
                case_id=case_id,
                report_type=request.report_type,
                workflow_status="completed",
                review_status=report.review_status,
                report_payload_json=report.model_dump(mode="json"),
                case_fact_pack_json=report.case_fact_pack.model_dump(mode="json"),
            )
            self.db.add(report_record)

            # Also clean up any active follow-up sessions for this case since report is now complete!
            stmt = delete(ReportSessionRecord).where(ReportSessionRecord.case_id == case_id)
            await self.db.execute(stmt)

            await self.db.commit()

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
