import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends

from app.schemas.legacy import (
    LegacyReportWorkflowResponse,
    legacy_report_response_from_payload,
)
from app.schemas.report import (
    EvidenceReference,
    ReportRequest,
    ReportResumeRequest,
    ReviewStatusUpdate,
)
from app.services.rag_client import RagServiceClient
from app.services.typhoon_ocr_reader import extract_markdown_from_upload
from app.dependencies import get_report_workflow_service
from app.services.report_request_helpers import (
    build_document_query,
    build_upload_evidence_registry,
    hash_upload_and_rewind,
)
from app.services.report_workflow import ReportWorkflowService

router = APIRouter(prefix="/rag", tags=["reports"])



@router.post("/generate-report", response_model=LegacyReportWorkflowResponse)
async def generate_report(
    request: ReportRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service)
):
    result = await service.generate_report(request)
    return legacy_report_response_from_payload(result.model_dump(mode="json"))


@router.post("/generate-report-file", response_model=LegacyReportWorkflowResponse)
async def generate_report_file(
    file: UploadFile = File(...),
    query: str = Form(""),
    report_type: str = Form("overview"),
    legal: bool = Form(False),
    force_generate: bool = Form(False),
    page_num: str | None = Form(None),
    service: ReportWorkflowService = Depends(get_report_workflow_service)
):
    try:
        file_hash_sha256 = await hash_upload_and_rewind(file)
        extracted_markdown = await extract_markdown_from_upload(file, page_num=page_num)
        document_query = build_document_query(extracted_markdown, query)
        evidence_registry = build_upload_evidence_registry(
            query=query,
            file=file,
            extracted_markdown=extracted_markdown,
            file_hash_sha256=file_hash_sha256,
            page_num=page_num,
        )
        payload = ReportRequest(
            query=document_query,
            report_type=report_type,  # type: ignore[arg-type]
            legal=legal,
            force_generate=force_generate,
            evidence_registry=evidence_registry,
        )
        result = await service.generate_report(payload)
        return legacy_report_response_from_payload(result.model_dump(mode="json"))
    except HTTPException:
        raise
    except Exception as e:
        print(f"[RAG] Error generating OCR report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume-report", response_model=LegacyReportWorkflowResponse)
async def resume_report(
    request: ReportResumeRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service)
):
    result = await service.resume_report(request)
    return legacy_report_response_from_payload(result.model_dump(mode="json"))


@router.get("/reports/{report_id}", response_model=LegacyReportWorkflowResponse)
async def get_report(
    report_id: str,
    service: ReportWorkflowService = Depends(get_report_workflow_service)
):
    result = await service.get_report(report_id)
    return legacy_report_response_from_payload(result.model_dump(mode="json"))


@router.patch(
    "/reports/{report_id}/review-status",
    response_model=LegacyReportWorkflowResponse,
)
async def update_report_review_status(
    report_id: str,
    request: ReviewStatusUpdate,
    service: ReportWorkflowService = Depends(get_report_workflow_service)
):
    result = await service.update_review_status(report_id, request)
    return legacy_report_response_from_payload(result.model_dump(mode="json"))
