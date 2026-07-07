from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.services.report_request_helpers import (
    build_document_query,
    build_upload_evidence_registry,
    hash_upload_and_rewind,
)
from app.schemas.report import (
    GenerateReportRequest,
    ReportResumeRequest,
    ReportWorkflowResponse,
    ReviewStatusUpdate,
)
from app.services.report_workflow import ReportWorkflowResult, ReportWorkflowService
from app.dependencies import get_report_workflow_service
from app.services.typhoon_ocr_reader import extract_markdown_from_upload

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/generate", response_model=ReportWorkflowResponse)
async def generate_report(
    request: GenerateReportRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResult:
    return await service.generate_report(request)

@router.post("/generate-file", response_model=ReportWorkflowResponse)
async def generate_report_file(
    file: UploadFile = File(...),
    query: str = Form(""),
    report_type: str = Form("overview"),
    legal: bool = Form(False),
    force_generate: bool = Form(False),
    page_num: str | None = Form(None),
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResult:
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
        payload = GenerateReportRequest(
            query=document_query,
            report_type=report_type,  # type: ignore[arg-type]
            legal=legal,
            force_generate=force_generate,
            evidence_registry=evidence_registry,
        )
        return await service.generate_report(payload)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[RAG] Error generating OCR report: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resume", response_model=ReportWorkflowResponse)
async def resume_report(
    request: ReportResumeRequest,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResult:
    return await service.resume_report(request)


@router.get("/{report_id}", response_model=ReportWorkflowResponse)
async def get_report(
    report_id: str,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResult:
    return await service.get_report(report_id)


@router.patch("/{report_id}/review-status", response_model=ReportWorkflowResponse)
async def update_report_review_status(
    report_id: str,
    request: ReviewStatusUpdate,
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> ReportWorkflowResult:
    return await service.update_review_status(report_id, request)
