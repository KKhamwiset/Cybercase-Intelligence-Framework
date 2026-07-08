from __future__ import annotations

from fastapi import APIRouter, Depends
from app.schemas.report import (
    ReportWorkflowResponse,
    ReviewStatusUpdate,
    ReportRegistryItem,
)
from app.services.report_workflow import ReportWorkflowResult, ReportWorkflowService
from app.dependencies import get_report_workflow_service

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
