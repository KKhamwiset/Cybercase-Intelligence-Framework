from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io

from app.schemas.report import (
    ReportWorkflowResponse,
    ReviewStatusUpdate,
    ReportRegistryItem,
)
from app.services.report_workflow import ReportWorkflowResult, ReportWorkflowService
from app.dependencies import get_report_workflow_service
from app.services.reporting.pdf_generator import generate_pdf_from_markdown

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportRegistryItem])
async def list_reports(
    service: ReportWorkflowService = Depends(get_report_workflow_service),
) -> list[ReportRegistryItem]:
    return await service.list_reports()


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


@router.get("/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = "md",
    service: ReportWorkflowService = Depends(get_report_workflow_service),
):
    result = await service.get_report(report_id)
    if result.status != "completed":
        raise HTTPException(status_code=400, detail="Report is not completed yet.")
    
    if format == "md":
        content = result.answer
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="cybercase-report-{report_id}.md"'
            }
        )
    elif format == "pdf":
        content = result.answer
        pdf_bytes = generate_pdf_from_markdown(content, title=result.report.title)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="cybercase-report-{report_id}.pdf"'
            }
        )
    elif format == "docx":
        # TODO: Implement DOCX export if requested in the future.
        raise HTTPException(
            status_code=501, 
            detail="DOCX export is not implemented yet."
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export format: {format}")

