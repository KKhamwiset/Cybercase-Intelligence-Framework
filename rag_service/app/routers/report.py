from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request

from RAG import CyberCaseReport, EvidenceReference, ReportGenerator, ReportWorkflowResponse
from RAG.GraphRAG.pipeline.thanoy_client import get_legal_advice
from routers.context_store import load_retrieval_context
from schemas.report import ReportRequest, ReportResumeRequest, ReviewStatusRequest

router = APIRouter(tags=["reports"])

REPORT_CONTEXT_WAIT_MESSAGE = (
    "Report generation is waiting for RAG context. Run the case through the RAG "
    "query or resume API first, then call report generation with the returned "
    "retrieval_context_id."
)


@router.post("/generate-report", response_model=ReportWorkflowResponse)
async def generate_report(request: ReportRequest, req: Request):
    report_gen: ReportGenerator | None = req.app.state.report_gen
    if not report_gen:
        raise HTTPException(status_code=503, detail="Report Generator not available")

    if not load_retrieval_context(req, request.retrieval_context_id):
        return _report_context_wait_response(request)

    preview_pack = report_gen.preview_case_fact_pack(
        request.query,
        legal=request.legal,
        evidence_registry=request.evidence_registry,
    )
    if _needs_report_followup(preview_pack) and not request.force_generate:
        return _start_report_followup(request, req, preview_pack)

    return await _complete_report_generation(request, req)


@router.post("/resume-report", response_model=ReportWorkflowResponse)
async def resume_report(request: ReportResumeRequest, req: Request):
    report_sessions: dict = req.app.state.report_sessions
    pending = report_sessions.pop(request.session_id, None)
    if not pending:
        raise HTTPException(status_code=404, detail="Report session not found")

    original = ReportRequest.model_validate(pending["request"])
    combined_query = original.query
    if request.answer.strip():
        combined_query = (
            f"{original.query}\n\n"
            "Follow-up answer supplied for preliminary report:\n"
            f"{request.answer.strip()}"
        )
    update_fields = {"query": combined_query, "force_generate": True}
    resumed_request = original.model_copy(update=update_fields)
    return await _complete_report_generation(resumed_request, req)


@router.get("/reports/{report_id}", response_model=ReportWorkflowResponse)
async def get_report(report_id: str, req: Request):
    report = _get_stored_report(report_id, req)
    report_gen: ReportGenerator | None = req.app.state.report_gen
    answer = report_gen.render_report_markdown(report) if report_gen else report.case_summary
    return ReportWorkflowResponse(
        status="completed",
        answer=answer,
        report_id=report.report_id,
        report=report,
        case_fact_pack=report.case_fact_pack,
        completeness=report.case_information_completeness,
        missing_information=report.case_fact_pack.missing_information,
    )


@router.patch("/reports/{report_id}/review-status", response_model=ReportWorkflowResponse)
async def update_report_review_status(
    report_id: str, request: ReviewStatusRequest, req: Request
):
    report = _get_stored_report(report_id, req)
    report.review_status = request.review_status
    report.case_fact_pack.review_status = request.review_status
    req.app.state.report_store[report_id] = report
    report_gen: ReportGenerator | None = req.app.state.report_gen
    answer = report_gen.render_report_markdown(report) if report_gen else report.case_summary
    return ReportWorkflowResponse(
        status="completed",
        answer=answer,
        report_id=report.report_id,
        report=report,
        case_fact_pack=report.case_fact_pack,
        completeness=report.case_information_completeness,
        missing_information=report.case_fact_pack.missing_information,
    )


async def _complete_report_generation(
    request: ReportRequest, req: Request
) -> ReportWorkflowResponse:
    report_gen: ReportGenerator | None = req.app.state.report_gen

    if not report_gen:
        raise HTTPException(status_code=503, detail="Report Generator not available")

    try:
        cached_context = load_retrieval_context(req, request.retrieval_context_id)
        if not cached_context:
            return _report_context_wait_response(request)

        print(f"[REPORT] Formatting report from RAG context: {request.retrieval_context_id}")
        rag_result = cached_context["rag_result"]
        context = cached_context["context"]

        report = report_gen.generate(
            request.query,
            context,
            rag_result=rag_result,
            report_type=request.report_type,
            legal=request.legal,
            evidence_registry=request.evidence_registry,
            force_generate=request.force_generate,
        )
        if request.legal:
            await _apply_thanoy_legal_advice(report)

        req.app.state.report_store[report.report_id] = report
        return ReportWorkflowResponse(
            status="completed",
            answer=report_gen.render_report_markdown(report),
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


async def _apply_thanoy_legal_advice(report: CyberCaseReport) -> None:
    advice = await get_legal_advice(report.executive_case_summary or report.case_summary)
    if not advice:
        return

    registry = report.case_fact_pack.evidence_registry
    legal_evidence_id = _next_report_evidence_id(registry)
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

    case_evidence_id = _primary_report_evidence_id(report)
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


def _primary_report_evidence_id(report: CyberCaseReport) -> str:
    for evidence in report.case_fact_pack.evidence_registry:
        if evidence.source_type in {"user_input", "uploaded_file", "log"}:
            return evidence.evidence_id
    if report.case_fact_pack.evidence_registry:
        return report.case_fact_pack.evidence_registry[0].evidence_id
    return ""


def _next_report_evidence_id(registry: list[EvidenceReference]) -> str:
    used = {item.evidence_id for item in registry}
    index = 1
    while f"E-{index:03d}" in used:
        index += 1
    return f"E-{index:03d}"


def _needs_report_followup(case_fact_pack) -> bool:
    return case_fact_pack.completeness.status == "Incomplete - follow-up required"


def _start_report_followup(
    request: ReportRequest, req: Request, case_fact_pack
) -> ReportWorkflowResponse:
    followup_question = _build_report_followup_question(case_fact_pack)
    session_id = str(uuid.uuid4())

    req.app.state.report_sessions[session_id] = {
        "request": request.model_dump(mode="json"),
    }
    return ReportWorkflowResponse(
        status="followup",
        followup_question=followup_question,
        session_id=session_id,
        case_fact_pack=case_fact_pack,
        completeness=case_fact_pack.completeness,
        missing_information=case_fact_pack.missing_information,
        retrieval_context_id=request.retrieval_context_id,
    )


def _report_context_wait_response(request: ReportRequest) -> ReportWorkflowResponse:
    return ReportWorkflowResponse(
        status="followup",
        followup_question=REPORT_CONTEXT_WAIT_MESSAGE,
        retrieval_context_id=request.retrieval_context_id,
        missing_information=["retrieval_context_id"],
    )


def _build_report_followup_question(case_fact_pack) -> str:
    if not case_fact_pack.missing_information:
        return "Could you provide any additional evidence or timeline details before report generation?"
    first_missing = case_fact_pack.missing_information[0]
    return (
        "The preliminary report is incomplete. Please provide the "
        f"{first_missing}, if known. You can answer 'unknown' if unavailable."
    )


def _get_stored_report(report_id: str, req: Request) -> CyberCaseReport:
    report = req.app.state.report_store.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report
